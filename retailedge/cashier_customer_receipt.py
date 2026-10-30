from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.accounts.doctype.mode_of_payment.mode_of_payment import validate_enabled_mode_of_payment

from retailedge.advanced_payments import _company_currency, _invoice_branch, _payment_branch_field
from retailedge.branch_context import validate_user_branch_access
from retailedge.operating_context import get_operating_context, get_operational_branch_scope
from retailedge.setup_roles import user_has_retailedge_role


CASHIER_ROLE = "RetailEdgeCashier"
SALES_INVOICE_DOCTYPE = "Sales Invoice"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
MODE_OF_PAYMENT_DOCTYPE = "Mode of Payment"
MODE_OF_PAYMENT_ACCOUNT_DOCTYPE = "Mode of Payment Account"
MAX_MODE_RESULTS = 20
OUTSTANDING_TOLERANCE = 0.005


def _coerce_values(values: dict[str, Any] | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})


def _assert_cashier() -> str:
	user = str(getattr(frappe.session, "user", "") or "").strip()
	if not user or user == "Guest" or not user_has_retailedge_role(CASHIER_ROLE, user=user):
		frappe.throw(
			_("Receive Payment is available only to an authorised RetailEdge cashier."),
			frappe.PermissionError,
		)
	return user


def _active_payment_entry_workflow() -> str:
	return str(
		frappe.db.get_value(
			"Workflow",
			{"document_type": PAYMENT_ENTRY_DOCTYPE, "is_active": 1},
			"name",
		)
		or ""
	).strip()


def _assert_direct_post_allowed() -> None:
	workflow = _active_payment_entry_workflow()
	if workflow:
		frappe.throw(
			_(
				"Customer payments are controlled by approval workflow {0}. "
				"Use the approved payment process instead of cashier direct posting."
			).format(workflow)
		)


def _assert_invoice_scope(invoice: Any) -> tuple[str, str]:
	company = str(getattr(invoice, "company", "") or "").strip()
	if not company:
		frappe.throw(_("Sales Invoice {0} has no Company.").format(invoice.name))

	operating = get_operating_context() or {}
	active_company = str(operating.get("company") or "").strip()
	active_branch = str(operating.get("branch") or "").strip()
	if active_company and active_company != company:
		frappe.throw(
			_("Sales Invoice {0} does not belong to your Working Company.").format(invoice.name),
			frappe.PermissionError,
		)

	branch = str(_invoice_branch(invoice) or "").strip()
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=company,
			throw=True,
		)
	elif scope.get("restricted"):
		frappe.throw(
			_("Sales Invoice {0} has no Branch attribution for your restricted access.").format(invoice.name),
			frappe.PermissionError,
		)

	if active_branch and branch != active_branch:
		frappe.throw(
			_("Sales Invoice {0} does not belong to your Working Branch.").format(invoice.name),
			frappe.PermissionError,
		)
	return company, branch


def _get_receivable_invoice(sales_invoice: str) -> tuple[Any, str, str, str]:
	_assert_cashier()
	sales_invoice = str(sales_invoice or "").strip()
	if not sales_invoice or not frappe.db.exists(SALES_INVOICE_DOCTYPE, sales_invoice):
		frappe.throw(_("Sales Invoice {0} is not available.").format(sales_invoice or ""))

	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "read", doc=invoice):
		frappe.throw(
			_("You do not have permission to receive payment for Sales Invoice {0}.").format(sales_invoice),
			frappe.PermissionError,
		)
	if cint(getattr(invoice, "docstatus", 0)) != 1:
		frappe.throw(_("Only submitted Sales Invoices can receive a customer payment."))
	if cint(getattr(invoice, "is_return", 0)):
		frappe.throw(_("Return / Credit Note invoices cannot use cashier Receive Payment."))
	if flt(getattr(invoice, "outstanding_amount", 0)) <= OUTSTANDING_TOLERANCE:
		frappe.throw(_("Sales Invoice {0} has no amount left to receive.").format(sales_invoice))

	company, branch = _assert_invoice_scope(invoice)
	company_currency = str(_company_currency(company) or "").strip()
	invoice_currency = str(getattr(invoice, "currency", "") or company_currency).strip()
	party_account_currency = str(
		getattr(invoice, "party_account_currency", "") or company_currency
	).strip()
	if not company_currency or invoice_currency != company_currency or party_account_currency != company_currency:
		frappe.throw(
			_("This invoice requires multi-currency payment handling and cannot use cashier Receive Payment.")
		)

	payment_terms_template = str(getattr(invoice, "payment_terms_template", "") or "").strip()
	if payment_terms_template and frappe.db.get_value(
		"Payment Terms Template",
		payment_terms_template,
		"allocate_payment_based_on_payment_terms",
	):
		frappe.throw(
			_("This invoice uses payment-term allocation and requires the managed payment process.")
		)
	return invoice, company, branch, company_currency


def _mode_account(mode_of_payment: str, company: str) -> dict[str, Any] | None:
	mode_of_payment = str(mode_of_payment or "").strip()
	if not mode_of_payment or not frappe.db.exists(MODE_OF_PAYMENT_DOCTYPE, mode_of_payment):
		return None
	if not cint(frappe.get_cached_value(MODE_OF_PAYMENT_DOCTYPE, mode_of_payment, "enabled")):
		return None
	account = str(
		frappe.db.get_value(
			MODE_OF_PAYMENT_ACCOUNT_DOCTYPE,
			{"parent": mode_of_payment, "company": company},
			"default_account",
		)
		or ""
	).strip()
	if not account:
		return None
	row = frappe.db.get_value(
		"Account",
		account,
		["company", "account_type", "account_currency", "is_group", "disabled"],
		as_dict=True,
	)
	if not row:
		return None
	if str(row.company or "") != company or cint(row.is_group) or cint(row.disabled):
		return None
	if str(row.account_type or "") not in {"Bank", "Cash"}:
		return None
	return {
		"mode_of_payment": mode_of_payment,
		"account": account,
		"account_type": str(row.account_type or ""),
		"account_currency": str(row.account_currency or ""),
	}


def _resolve_mode(mode_of_payment: str, company: str, company_currency: str) -> dict[str, Any]:
	validate_enabled_mode_of_payment(mode_of_payment)
	mode = _mode_account(mode_of_payment, company)
	if not mode:
		frappe.throw(
			_("Mode of Payment {0} is not configured with an active Bank or Cash account for this Company.").format(
				mode_of_payment
			)
		)
	if mode["account_currency"] != company_currency:
		frappe.throw(
			_("Mode of Payment {0} uses a different account currency and cannot be used for this receipt.").format(
				mode_of_payment
			)
		)
	return mode


def _receipt_values(
	invoice: Any,
	company: str,
	branch: str,
	company_currency: str,
	values: dict[str, Any] | str | None,
) -> dict[str, Any]:
	provided = _coerce_values(values)
	amount = flt(provided.get("amount"))
	outstanding = flt(getattr(invoice, "outstanding_amount", 0))
	if amount <= 0:
		frappe.throw(_("Payment Amount must be greater than zero."))
	if amount > outstanding + OUTSTANDING_TOLERANCE:
		frappe.throw(
			_("Payment Amount cannot exceed the current Invoice Outstanding of {0} {1}.").format(
				company_currency,
				outstanding,
			)
		)

	posting_date = getdate(provided.get("posting_date") or nowdate())
	mode_of_payment = str(provided.get("mode_of_payment") or "").strip()
	if not mode_of_payment:
		frappe.throw(_("Mode of Payment is required."))
	mode = _resolve_mode(mode_of_payment, company, company_currency)

	reference_no = str(provided.get("reference_no") or "").strip()
	reference_date = provided.get("reference_date") or posting_date
	if mode["account_type"] == "Bank" and not reference_no:
		frappe.throw(_("Reference No is required for Bank payments."))

	return {
		"company": company,
		"branch": branch,
		"posting_date": posting_date,
		"mode_of_payment": mode_of_payment,
		"mode": mode,
		"amount": amount,
		"reference_no": reference_no,
		"reference_date": getdate(reference_date),
		"outstanding": outstanding,
		"remaining": max(outstanding - amount, 0),
	}


def _preview_payload(invoice: Any, branch: str, currency: str, receipt: dict[str, Any]) -> dict[str, Any]:
	return {
		"sales_invoice": invoice.name,
		"customer": str(getattr(invoice, "customer", "") or ""),
		"customer_name": str(getattr(invoice, "customer_name", "") or getattr(invoice, "customer", "") or ""),
		"company": str(getattr(invoice, "company", "") or ""),
		"branch": branch,
		"currency": currency,
		"invoice_status": str(getattr(invoice, "status", "") or "Submitted"),
		"invoice_total": flt(getattr(invoice, "grand_total", 0)),
		"invoice_outstanding": receipt["outstanding"],
		"posting_date": str(receipt["posting_date"]),
		"mode_of_payment": receipt["mode_of_payment"],
		"payment_account_type": receipt["mode"]["account_type"],
		"reference_required": receipt["mode"]["account_type"] == "Bank",
		"reference_no": receipt["reference_no"],
		"reference_date": str(receipt["reference_date"]),
		"payment_amount": receipt["amount"],
		"remaining_after_payment": receipt["remaining"],
		"expected_invoice_modified": str(getattr(invoice, "modified", "") or ""),
		"expected_outstanding_amount": receipt["outstanding"],
		"source_of_truth": "ERPNext Payment Entry",
		"can_post": True,
	}


def _build_payment_entry(invoice: Any, branch: str, receipt: dict[str, Any]):
	payment = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)
	payment.payment_type = "Receive"
	payment.company = invoice.company
	payment.posting_date = receipt["posting_date"]
	payment.party_type = "Customer"
	payment.party = invoice.customer
	payment.mode_of_payment = receipt["mode_of_payment"]
	payment.paid_from = invoice.debit_to
	payment.paid_to = receipt["mode"]["account"]
	payment.paid_amount = receipt["amount"]
	payment.received_amount = receipt["amount"]
	payment.reference_no = receipt["reference_no"] or invoice.name
	payment.reference_date = receipt["reference_date"]
	payment.custom_remarks = 1
	payment.remarks = _("Customer payment recorded against Sales Invoice {0} through RetailEdge cashier receipt.").format(
		invoice.name
	)
	branch_field = _payment_branch_field()
	if branch and branch_field:
		payment.set(branch_field, branch)
	payment.append(
		"references",
		{
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": invoice.name,
			"due_date": getattr(invoice, "due_date", None),
			"total_amount": flt(getattr(invoice, "grand_total", 0)),
			"outstanding_amount": receipt["outstanding"],
			"allocated_amount": receipt["amount"],
		},
	)
	return payment


def _post_native_payment(payment: Any) -> None:
	previous_ignore_account_permission = getattr(frappe.flags, "ignore_account_permission", False)
	try:
		# This exception is deliberately narrow: the cashier does not receive generic
		# Account or Payment Entry authority. Native Payment Entry validation, hooks,
		# GL/Payment Ledger posting and transaction rollback remain authoritative.
		frappe.flags.ignore_account_permission = True
		payment.flags.ignore_permissions = True
		payment.insert(ignore_permissions=True)
		payment.submit()
	finally:
		frappe.flags.ignore_account_permission = previous_ignore_account_permission


@frappe.whitelist()
def get_cashier_customer_receipt_context(sales_invoice: str) -> dict[str, Any]:
	invoice, company, branch, currency = _get_receivable_invoice(sales_invoice)
	return {
		"sales_invoice": invoice.name,
		"customer": str(getattr(invoice, "customer", "") or ""),
		"customer_name": str(getattr(invoice, "customer_name", "") or getattr(invoice, "customer", "") or ""),
		"company": company,
		"branch": branch,
		"currency": currency,
		"invoice_status": str(getattr(invoice, "status", "") or "Submitted"),
		"invoice_total": flt(getattr(invoice, "grand_total", 0)),
		"invoice_outstanding": flt(getattr(invoice, "outstanding_amount", 0)),
		"defaults": {
			"posting_date": nowdate(),
			"mode_of_payment": "",
			"amount": flt(getattr(invoice, "outstanding_amount", 0)),
			"reference_no": "",
			"reference_date": nowdate(),
		},
		"limits": {"max_mode_results": MAX_MODE_RESULTS},
		"source_of_truth": "ERPNext Payment Entry",
	}


@frappe.whitelist()
def search_cashier_customer_receipt_modes(
	sales_invoice: str,
	txt: str = "",
	limit: int | str = MAX_MODE_RESULTS,
) -> list[dict[str, Any]]:
	_invoice, company, _branch, currency = _get_receivable_invoice(sales_invoice)
	query = str(txt or "").strip()
	limit_value = max(1, min(cint(limit) or MAX_MODE_RESULTS, MAX_MODE_RESULTS))
	filters: dict[str, Any] = {"enabled": 1}
	if query:
		filters["name"] = ["like", f"%{query}%"]
	rows = frappe.get_list(
		MODE_OF_PAYMENT_DOCTYPE,
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_MODE_RESULTS * 3,
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		mode = _mode_account(row.name, company)
		if not mode or mode["account_currency"] != currency:
			continue
		result.append(
			{
				"value": row.name,
				"label": row.name,
				"description": _("{0} payment").format(mode["account_type"]),
			}
		)
		if len(result) >= limit_value:
			break
	return result


@frappe.whitelist()
def get_cashier_customer_receipt_mode_details(
	sales_invoice: str,
	mode_of_payment: str,
) -> dict[str, Any]:
	_invoice, company, _branch, currency = _get_receivable_invoice(sales_invoice)
	mode = _resolve_mode(mode_of_payment, company, currency)
	return {
		"mode_of_payment": mode_of_payment,
		"account_type": mode["account_type"],
		"reference_required": mode["account_type"] == "Bank",
	}


@frappe.whitelist()
def preview_cashier_customer_receipt(
	sales_invoice: str,
	values: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	invoice, company, branch, currency = _get_receivable_invoice(sales_invoice)
	_assert_direct_post_allowed()
	receipt = _receipt_values(invoice, company, branch, currency, values)
	return _preview_payload(invoice, branch, currency, receipt)


@frappe.whitelist(methods=["POST"])
def post_cashier_customer_receipt(
	sales_invoice: str,
	values: dict[str, Any] | str | None = None,
	expected_invoice_modified: str | None = None,
	expected_outstanding_amount: float | str | None = None,
) -> dict[str, Any]:
	_assert_cashier()
	sales_invoice = str(sales_invoice or "").strip()
	if not sales_invoice:
		frappe.throw(_("Sales Invoice is required."))

	frappe.db.sql(
		"SELECT name FROM `tabSales Invoice` WHERE name = %s FOR UPDATE",
		(sales_invoice,),
	)
	invoice, company, branch, currency = _get_receivable_invoice(sales_invoice)
	_assert_direct_post_allowed()

	expected_modified = str(expected_invoice_modified or "").strip()
	current_modified = str(getattr(invoice, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("Sales Invoice {0} changed after your payment review. Refresh before posting the payment.").format(
				invoice.name
			)
		)

	expected_outstanding = flt(expected_outstanding_amount)
	current_outstanding = flt(getattr(invoice, "outstanding_amount", 0))
	if expected_outstanding <= 0 or abs(expected_outstanding - current_outstanding) > OUTSTANDING_TOLERANCE:
		frappe.throw(
			_("Sales Invoice {0} outstanding amount changed after your review. Refresh before posting the payment.").format(
				invoice.name
			)
		)

	receipt = _receipt_values(invoice, company, branch, currency, values)
	payment = _build_payment_entry(invoice, branch, receipt)
	_post_native_payment(payment)
	if cint(getattr(payment, "docstatus", 0)) != 1:
		frappe.throw(_("The customer payment was not posted. Refresh and try again."))

	invoice.reload()
	return {
		"sales_invoice": invoice.name,
		"payment_reference": payment.name,
		"payment_amount": receipt["amount"],
		"currency": currency,
		"invoice_outstanding": flt(getattr(invoice, "outstanding_amount", 0)),
		"status": str(getattr(payment, "status", "") or "Submitted"),
		"source_of_truth": "ERPNext Payment Entry",
		"posting_status": "Posted",
	}
