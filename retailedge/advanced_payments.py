from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.accounts.doctype.payment_entry.payment_entry import get_party_details

from retailedge.branch_context import has_field, validate_user_branch_access
from retailedge.guided_payment import get_simple_payment_mode_details
from retailedge.operating_context import get_operating_context

PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
SALES_INVOICE_DOCTYPE = "Sales Invoice"
CUSTOMER_DOCTYPE = "Customer"
MAX_ADVANCE_ROWS = 100


def _assert_read(doctype: str, name: str | None = None) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _assert_create_payment_entry() -> None:
	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Payment Entries."), frappe.PermissionError)


def _payment_branch_field() -> str | None:
	if has_field(PAYMENT_ENTRY_DOCTYPE, "retailedge_branch"):
		return "retailedge_branch"
	if has_field(PAYMENT_ENTRY_DOCTYPE, "branch"):
		return "branch"
	return None


def _require_payment_branch_field(branch: str | None) -> str | None:
	field = _payment_branch_field()
	if branch and not field:
		frappe.throw(
			_(
				"Payment Entry branch attribution is unavailable. Run the site migration before using a Branch-scoped advance workflow."
			)
		)
	return field


def _invoice_branch(invoice: Any) -> str:
	return str(getattr(invoice, "retailedge_branch", None) or getattr(invoice, "branch", None) or "")


def _normalise_limit(limit: int | str | None) -> int:
	return max(1, min(cint(limit) or 50, MAX_ADVANCE_ROWS))


def _resolve_advance_scope(company: str | None, branch: str | None) -> tuple[str, str]:
	operating = get_operating_context() or {}
	operating_company = str(operating.get("company") or "").strip()
	operating_branch = str(operating.get("branch") or "").strip()
	resolved_company = str(company or operating_company or frappe.defaults.get_user_default("Company") or "").strip()
	if not resolved_company:
		frappe.throw(_("Choose an Operating Company before viewing customer advances."))
	_assert_read("Company", resolved_company)

	resolved_branch = str(branch or "").strip()
	if not resolved_branch and (not company or resolved_company == operating_company):
		resolved_branch = operating_branch
	if resolved_branch:
		validate_user_branch_access(
			resolved_branch,
			user=frappe.session.user,
			company=resolved_company,
			throw=True,
		)
	return resolved_company, resolved_branch


@frappe.whitelist()
def get_customer_advance_context(
	customer: str | None = None,
	company: str | None = None,
	branch: str | None = None,
	limit: int = 50,
) -> dict[str, Any]:
	"""Return an operational view of authoritative ERPNext customer advances.

	The balance is never maintained by the product. Submitted Payment Entry
	``unallocated_amount`` remains the source of truth.
	"""
	_assert_read(PAYMENT_ENTRY_DOCTYPE)
	company, branch = _resolve_advance_scope(company, branch)
	if customer:
		_assert_read(CUSTOMER_DOCTYPE, customer)

	rows = list_customer_advances(customer=customer, company=company, branch=branch or None, limit=limit)
	return {
		"customer": customer or "",
		"company": company,
		"branch": branch,
		"currency": _company_currency(company),
		"available_advance": sum(flt(row.get("unallocated_amount")) for row in rows),
		"advance_count": len(rows),
		"advances": rows,
		"source_of_truth": PAYMENT_ENTRY_DOCTYPE,
		"accounting_policy": "erpnext-native",
	}


@frappe.whitelist()
def list_customer_advances(
	customer: str | None = None,
	company: str | None = None,
	branch: str | None = None,
	limit: int = 50,
) -> list[dict[str, Any]]:
	"""List submitted Receive Payment Entries that still have unapplied value."""
	_assert_read(PAYMENT_ENTRY_DOCTYPE)
	company, branch = _resolve_advance_scope(company, branch)
	if customer:
		_assert_read(CUSTOMER_DOCTYPE, customer)

	filters: dict[str, Any] = {
		"docstatus": 1,
		"payment_type": "Receive",
		"party_type": CUSTOMER_DOCTYPE,
		"unallocated_amount": [">", 0],
		"company": company,
	}
	if customer:
		filters["party"] = customer

	branch_field = _require_payment_branch_field(branch)
	if branch and branch_field:
		filters[branch_field] = branch

	fields = [
		"name",
		"posting_date",
		"company",
		"party",
		"paid_amount",
		"received_amount",
		"unallocated_amount",
		"paid_to",
		"mode_of_payment",
		"reference_no",
		"reference_date",
		"modified",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="posting_date asc, name asc",
		limit_page_length=_normalise_limit(limit),
	)
	return [
		{
			"name": row.name,
			"posting_date": row.posting_date,
			"company": row.company,
			"customer": row.party,
			"paid_amount": flt(row.paid_amount),
			"received_amount": flt(row.received_amount),
			"unallocated_amount": flt(row.unallocated_amount),
			"paid_to": row.paid_to,
			"mode_of_payment": row.mode_of_payment,
			"reference_no": row.reference_no,
			"reference_date": row.reference_date,
			"branch": getattr(row, branch_field, "") if branch_field else "",
			"route": f"/app/payment-entry/{row.name}",
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def create_customer_advance_draft(values: dict | str | None = None) -> dict[str, Any]:
	"""Create an unallocated draft ERPNext customer receipt.

	The draft intentionally has no invoice references. ERPNext Payment Entry
	validation remains responsible for account completion, exchange rates, totals
	and the authoritative unallocated amount. This method never submits the
	Payment Entry and never changes a Sales Invoice.
	"""
	_assert_create_payment_entry()
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})
	if values.get("references"):
		frappe.throw(
			_(
				"Customer Advance must not include invoice allocations. Use Receive Customer Payment for an allocated receipt."
			)
		)

	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read("Company", company)
	company_currency = _company_currency(company)
	if not company_currency:
		frappe.throw(_("Company {0} has no default currency configured.").format(company))

	branch = str(values.get("branch") or "").strip()
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)
	branch_field = _require_payment_branch_field(branch)

	customer = str(values.get("customer") or values.get("party") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required."))
	_assert_read(CUSTOMER_DOCTYPE, customer)

	posting_date = getdate(values.get("posting_date") or nowdate())
	party_details = get_party_details(company, CUSTOMER_DOCTYPE, customer, posting_date)
	party_account = party_details.get("party_account")
	party_currency = party_details.get("party_account_currency")
	if not party_account:
		frappe.throw(_("No receivable account could be resolved for {0}.").format(customer))
	_assert_read("Account", party_account)

	mode_of_payment = str(values.get("mode_of_payment") or "").strip()
	if not mode_of_payment:
		frappe.throw(_("Mode of Payment is required."))
	mode_details = get_simple_payment_mode_details("receive-customer-payment", company, mode_of_payment)
	bank_account = mode_details["account"]
	bank_currency = mode_details["account_currency"]
	if party_currency != company_currency or bank_currency != company_currency:
		frappe.throw(
			_(
				"Customer Advance currently supports company-currency payments only. Use the full Payment Entry form for multi-currency payments."
			)
		)

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))

	doc = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)
	doc.payment_type = "Receive"
	doc.company = company
	doc.posting_date = posting_date
	doc.party_type = CUSTOMER_DOCTYPE
	doc.party = customer
	doc.mode_of_payment = mode_of_payment
	doc.paid_amount = amount
	doc.received_amount = amount
	doc.paid_from = party_account
	doc.paid_to = bank_account

	if branch and branch_field:
		setattr(doc, branch_field, branch)

	if mode_details["reference_required"]:
		reference_no = str(values.get("reference_no") or "").strip()
		if not reference_no:
			frappe.throw(_("Reference No is required for Bank payments."))
		doc.reference_no = reference_no
		doc.reference_date = getdate(values.get("reference_date") or posting_date)

	if values.get("remarks"):
		doc.custom_remarks = 1
		doc.remarks = str(values.get("remarks")).strip()

	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"payment_type": doc.payment_type,
		"party_type": doc.party_type,
		"customer": doc.party,
		"company": doc.company,
		"branch": getattr(doc, branch_field, "") if branch_field else "",
		"paid_amount": flt(doc.paid_amount),
		"unallocated_amount": getattr(doc, "unallocated_amount", None),
		"advance_payment": True,
		"allocation_status": "Unallocated",
		"source_of_truth": PAYMENT_ENTRY_DOCTYPE,
		"route": f"/app/payment-entry/{doc.name}",
	}


@frappe.whitelist()
def get_sales_invoice_advance_context(sales_invoice: str, limit: int = 50) -> dict[str, Any]:
	"""Return advances eligible by customer/company/currency/branch context.

	This endpoint is read-only. Applying an advance must use ERPNext's supported
	advance/reconciliation workflow; submitted invoices are never mutated directly.
	"""
	_assert_read(SALES_INVOICE_DOCTYPE, sales_invoice)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice)
	if invoice.docstatus == 2:
		frappe.throw(_("Cancelled Sales Invoices cannot receive advance allocations."))
	if not invoice.customer:
		frappe.throw(_("Sales Invoice {0} has no Customer.").format(sales_invoice))

	branch = _invoice_branch(invoice)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=invoice.company,
			throw=True,
		)

	advances = list_customer_advances(
		customer=invoice.customer,
		company=invoice.company,
		branch=branch or None,
		limit=limit,
	)
	invoice_currency = str(getattr(invoice, "currency", None) or "")
	company_currency = _company_currency(invoice.company)
	currency_supported = not invoice_currency or invoice_currency == company_currency

	return {
		"sales_invoice": invoice.name,
		"docstatus": invoice.docstatus,
		"customer": invoice.customer,
		"company": invoice.company,
		"branch": branch,
		"currency": invoice_currency,
		"company_currency": company_currency,
		"outstanding_amount": flt(getattr(invoice, "outstanding_amount", 0)),
		"eligible_advances": advances if currency_supported else [],
		"available_advance": sum(flt(row.get("unallocated_amount")) for row in advances)
		if currency_supported
		else 0.0,
		"currency_supported": currency_supported,
		"application_write_enabled": False,
		"application_policy": "Use ERPNext advance/reconciliation workflow; never mutate submitted Sales Invoice.",
	}


def _company_currency(company: str | None) -> str:
	if not company:
		return ""
	return str(frappe.db.get_value("Company", company, "default_currency") or "")
