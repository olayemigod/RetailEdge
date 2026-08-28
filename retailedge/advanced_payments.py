from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.branch_context import has_field, validate_user_branch_access
from retailedge.guided_payment import create_simple_payment_draft

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


def _invoice_branch(invoice: Any) -> str:
	return str(getattr(invoice, "retailedge_branch", None) or getattr(invoice, "branch", None) or "")


def _normalise_limit(limit: int | str | None) -> int:
	return max(1, min(cint(limit) or 50, MAX_ADVANCE_ROWS))


@frappe.whitelist()
def get_customer_advance_context(
	customer: str | None = None,
	company: str | None = None,
	branch: str | None = None,
	limit: int = 50,
) -> dict[str, Any]:
	"""Return an operational view of authoritative ERPNext customer advances.

	The balance is never maintained by RetailEdge. Submitted Payment Entry
	``unallocated_amount`` remains the source of truth.
	"""
	_assert_read(PAYMENT_ENTRY_DOCTYPE)
	if customer:
		_assert_read(CUSTOMER_DOCTYPE, customer)
	if company:
		_assert_read("Company", company)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	rows = list_customer_advances(customer=customer, company=company, branch=branch, limit=limit)
	return {
		"customer": customer or "",
		"company": company or "",
		"branch": branch or "",
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
	if customer:
		_assert_read(CUSTOMER_DOCTYPE, customer)
	if company:
		_assert_read("Company", company)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	filters: dict[str, Any] = {
		"docstatus": 1,
		"payment_type": "Receive",
		"party_type": CUSTOMER_DOCTYPE,
		"unallocated_amount": [">", 0],
	}
	if customer:
		filters["party"] = customer
	if company:
		filters["company"] = company

	branch_field = _payment_branch_field()
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
	"""Create a draft ERPNext customer Receipt with no invoice allocation.

	This deliberately delegates account resolution, currency checks and document
	validation to the existing guided Payment Entry engine. It never submits a
	Payment Entry and never changes a Sales Invoice.
	"""
	_assert_create_payment_entry()
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})
	values.pop("references", None)
	result = create_simple_payment_draft(
		"receive-customer-payment",
		{**values, "references": []},
	)
	result.update(
		{
			"advance_payment": True,
			"allocation_status": "Unallocated",
			"source_of_truth": PAYMENT_ENTRY_DOCTYPE,
		}
	)
	return result


@frappe.whitelist()
def get_sales_invoice_advance_context(sales_invoice: str, limit: int = 50) -> dict[str, Any]:
	"""Return advances eligible by customer/company/currency/branch context.

	This endpoint is read-only. Applying an advance must use ERPNext's supported
	advance/reconciliation workflow; RetailEdge must not mutate submitted invoices.
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
