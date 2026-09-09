from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.advanced_payments import (
	CUSTOMER_DOCTYPE,
	PAYMENT_ENTRY_DOCTYPE,
	SALES_INVOICE_DOCTYPE,
	_company_currency,
	_invoice_branch,
	_payment_branch_field,
)
from retailedge.branch_context import user_has_global_branch_access, validate_user_branch_access

MAX_DRAFT_ROWS = 50


def _assert_permission(doctype: str, ptype: str, doc: Any | None = None) -> None:
	if not frappe.has_permission(doctype, ptype, doc=doc):
		frappe.throw(
			_("You do not have {0} permission for {1}.").format(_(ptype), _(doctype)),
			frappe.PermissionError,
		)


def _get_payment_entry(name: str) -> Any:
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Payment Entry is required."))
	if not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, name):
		frappe.throw(_("Payment Entry {0} does not exist.").format(name))
	doc = frappe.get_doc(PAYMENT_ENTRY_DOCTYPE, name)
	_assert_permission(PAYMENT_ENTRY_DOCTYPE, "read", doc)
	return doc


def _payment_branch(doc: Any) -> str:
	field = _payment_branch_field()
	return str(getattr(doc, field, None) or "") if field else ""


def _validate_payment_branch(doc: Any) -> str:
	branch = _payment_branch(doc)
	global_access = user_has_global_branch_access(user=frappe.session.user)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=doc.company,
			throw=True,
		)
	elif not global_access:
		frappe.throw(
			_("Payment Entry {0} has no Branch attribution for your restricted access.").format(doc.name),
			frappe.PermissionError,
		)
	return branch


def _validate_selected_context(
	doc: Any,
	branch: str,
	company: str | None = None,
	customer: str | None = None,
	selected_branch: str | None = None,
) -> None:
	company = str(company or "").strip()
	customer = str(customer or "").strip()
	selected_branch = str(selected_branch or "").strip()
	if company and str(getattr(doc, "company", "") or "") != company:
		frappe.throw(_("Payment Entry does not belong to the selected Company."), frappe.PermissionError)
	if customer and str(getattr(doc, "party", "") or "") != customer:
		frappe.throw(_("Payment Entry does not belong to the selected Customer."), frappe.PermissionError)
	if selected_branch and branch != selected_branch:
		frappe.throw(_("Payment Entry does not belong to the selected Branch."), frappe.PermissionError)


def _reference_preview(doc: Any, payment_branch: str) -> tuple[dict[str, Any] | None, list[str]]:
	blockers: list[str] = []
	references = list(getattr(doc, "references", None) or [])
	if not references:
		return None, blockers
	if len(references) != 1:
		blockers.append(_("Payments allocated to multiple documents require Advanced ERPNext review."))
		return None, blockers

	row = references[0]
	if str(getattr(row, "reference_doctype", "") or "") != SALES_INVOICE_DOCTYPE:
		blockers.append(_("Only a single Sales Invoice allocation is supported by standard EdgeSuite submission."))
		return None, blockers

	invoice_name = str(getattr(row, "reference_name", "") or "").strip()
	allocated_amount = flt(getattr(row, "allocated_amount", 0))
	if not invoice_name or allocated_amount <= 0:
		blockers.append(_("The Sales Invoice allocation is incomplete. Use Advanced ERPNext review."))
		return None, blockers
	if not frappe.db.exists(SALES_INVOICE_DOCTYPE, invoice_name):
		blockers.append(_("Referenced Sales Invoice {0} no longer exists.").format(invoice_name))
		return {"sales_invoice": invoice_name, "allocated_amount": allocated_amount}, blockers

	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	_assert_permission(SALES_INVOICE_DOCTYPE, "read", invoice)
	invoice_branch = _invoice_branch(invoice)
	if invoice_branch:
		validate_user_branch_access(
			invoice_branch,
			user=frappe.session.user,
			company=invoice.company,
			throw=True,
		)
	if cint(getattr(invoice, "docstatus", 0)) != 1:
		blockers.append(_("Referenced Sales Invoice {0} is not submitted.").format(invoice_name))
	if cint(getattr(invoice, "is_return", 0)):
		blockers.append(_("Return Sales Invoices require Advanced ERPNext review."))
	if str(getattr(invoice, "company", "") or "") != str(getattr(doc, "company", "") or ""):
		blockers.append(_("Payment Entry and Sales Invoice must belong to the same Company."))
	if str(getattr(invoice, "customer", "") or "") != str(getattr(doc, "party", "") or ""):
		blockers.append(_("Payment Entry and Sales Invoice must belong to the same Customer."))
	if invoice_branch and payment_branch and invoice_branch != payment_branch:
		blockers.append(_("Payment Entry and Sales Invoice must belong to the same Branch."))

	company_currency = _company_currency(str(getattr(doc, "company", "") or ""))
	invoice_currency = str(getattr(invoice, "currency", "") or company_currency)
	if invoice_currency != company_currency:
		blockers.append(_("Multi-currency Sales Invoice receipts require Advanced ERPNext review."))
	outstanding = flt(getattr(invoice, "outstanding_amount", 0))
	if outstanding <= 0:
		blockers.append(_("Sales Invoice {0} no longer has a positive outstanding amount.").format(invoice_name))
	elif allocated_amount > outstanding + 0.005:
		blockers.append(_("The draft allocation exceeds the current Sales Invoice outstanding amount."))

	return {
		"sales_invoice": invoice_name,
		"allocated_amount": allocated_amount,
		"invoice_outstanding_amount": outstanding,
	}, blockers


def _standard_submit_blockers(doc: Any, payment_branch: str) -> tuple[list[str], dict[str, Any] | None]:
	blockers: list[str] = []
	if cint(getattr(doc, "docstatus", 0)) != 0:
		blockers.append(_("Only draft Payment Entries can use standard EdgeSuite submission."))
	if str(getattr(doc, "payment_type", "") or "") != "Receive":
		blockers.append(_("Only Receive Payment Entries are supported. Use Advanced ERPNext for Pay or Internal Transfer."))
	if str(getattr(doc, "party_type", "") or "") != CUSTOMER_DOCTYPE:
		blockers.append(_("Only Customer Payment Entries are supported by this workflow."))
	if not str(getattr(doc, "company", "") or "") or not str(getattr(doc, "party", "") or ""):
		blockers.append(_("Payment Entry Company and Customer are required."))
	if flt(getattr(doc, "paid_amount", 0)) <= 0 or flt(getattr(doc, "received_amount", 0)) <= 0:
		blockers.append(_("Payment amount must be greater than zero."))
	if not str(getattr(doc, "paid_from", "") or "") or not str(getattr(doc, "paid_to", "") or ""):
		blockers.append(_("Payment accounts are incomplete. Use Advanced ERPNext review."))

	company = str(getattr(doc, "company", "") or "")
	company_currency = _company_currency(company) if company else ""
	paid_from_currency = str(getattr(doc, "paid_from_account_currency", "") or company_currency)
	paid_to_currency = str(getattr(doc, "paid_to_account_currency", "") or company_currency)
	if not company_currency or paid_from_currency != company_currency or paid_to_currency != company_currency:
		blockers.append(_("Multi-currency Payment Entries require Advanced ERPNext review."))
	if getattr(doc, "book_advance_payments_in_separate_party_account", 0):
		blockers.append(_("Separate party-account advances require Advanced ERPNext review."))
	if list(getattr(doc, "deductions", None) or []) or abs(flt(getattr(doc, "difference_amount", 0))) > 0.005:
		blockers.append(_("Payments with deductions or exchange differences require Advanced ERPNext review."))

	reference, reference_blockers = _reference_preview(doc, payment_branch)
	blockers.extend(reference_blockers)
	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc):
		blockers.append(_("You do not have permission to submit this Payment Entry."))
	return blockers, reference


def _build_preview(
	doc: Any,
	company: str | None = None,
	customer: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	payment_branch = _validate_payment_branch(doc)
	_validate_selected_context(doc, payment_branch, company=company, customer=customer, selected_branch=branch)
	blockers, reference = _standard_submit_blockers(doc, payment_branch)
	allocated_amount = flt(reference.get("allocated_amount")) if reference else 0
	received_amount = flt(getattr(doc, "received_amount", 0))
	return {
		"payment_entry": doc.name,
		"payment_entry_modified": str(getattr(doc, "modified", "") or ""),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": payment_branch,
		"customer": str(getattr(doc, "party", "") or ""),
		"posting_date": str(getattr(doc, "posting_date", "") or ""),
		"mode_of_payment": str(getattr(doc, "mode_of_payment", "") or ""),
		"paid_from": str(getattr(doc, "paid_from", "") or ""),
		"paid_to": str(getattr(doc, "paid_to", "") or ""),
		"currency": _company_currency(str(getattr(doc, "company", "") or "")),
		"received_amount": received_amount,
		"allocated_amount": allocated_amount,
		"unallocated_amount": max(received_amount - allocated_amount, 0),
		"sales_invoice": reference.get("sales_invoice") if reference else "",
		"invoice_outstanding_amount": reference.get("invoice_outstanding_amount") if reference else None,
		"payment_kind": "Invoice Receipt" if reference else "Customer Advance",
		"docstatus": cint(getattr(doc, "docstatus", 0)),
		"status": "Draft" if cint(getattr(doc, "docstatus", 0)) == 0 else str(getattr(doc, "status", "") or "Submitted"),
		"blockers": blockers,
		"can_submit": not blockers,
		"persistence": "none",
		"source_of_truth": "ERPNext Payment Entry",
		"route": f"/app/payment-entry/{doc.name}",
	}


@frappe.whitelist()
def get_customer_payment_submit_preview(
	payment_entry: str,
	company: str | None = None,
	customer: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Return a read-only review of one standard draft customer receipt."""
	doc = _get_payment_entry(payment_entry)
	return _build_preview(doc, company=company, customer=customer, branch=branch)


@frappe.whitelist()
def list_standard_customer_payment_drafts(
	company: str,
	customer: str,
	branch: str | None = None,
	limit: int | str = 25,
) -> list[dict[str, Any]]:
	"""List only permission-visible draft customer receipts in the selected operating scope."""
	company = str(company or "").strip()
	customer = str(customer or "").strip()
	branch = str(branch or "").strip()
	if not company or not customer:
		frappe.throw(_("Choose Company and Customer before reviewing draft payments."))
	_assert_permission("Company", "read", frappe.get_doc("Company", company))
	_assert_permission(CUSTOMER_DOCTYPE, "read", frappe.get_doc(CUSTOMER_DOCTYPE, customer))

	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)
	elif not user_has_global_branch_access(user=frappe.session.user):
		frappe.throw(_("Choose a Branch before reviewing draft payments for restricted access."), frappe.PermissionError)

	filters: dict[str, Any] = {
		"docstatus": 0,
		"payment_type": "Receive",
		"party_type": CUSTOMER_DOCTYPE,
		"company": company,
		"party": customer,
	}
	branch_field = _payment_branch_field()
	if branch:
		if not branch_field:
			frappe.throw(_("Payment Entry branch attribution is unavailable. Run the site migration before using Branch-scoped payment submission."))
		filters[branch_field] = branch

	rows = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=["name"],
		order_by="modified desc",
		limit_page_length=max(1, min(cint(limit) or 25, MAX_DRAFT_ROWS)),
	)
	return [
		_build_preview(
			_get_payment_entry(row.name),
			company=company,
			customer=customer,
			branch=branch or None,
		)
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def submit_standard_customer_payment(
	payment_entry: str,
	expected_payment_entry_modified: str | None = None,
	company: str | None = None,
	customer: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed standard customer Payment Entry through native ERPNext."""
	payment_entry = str(payment_entry or "").strip()
	if not payment_entry:
		frappe.throw(_("Payment Entry is required."))
	if not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, payment_entry):
		frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry))

	frappe.db.sql(
		"SELECT name FROM `tabPayment Entry` WHERE name = %s FOR UPDATE",
		(payment_entry,),
	)
	doc = _get_payment_entry(payment_entry)
	payment_branch = _validate_payment_branch(doc)
	_validate_selected_context(doc, payment_branch, company=company, customer=customer, selected_branch=branch)

	expected_modified = str(expected_payment_entry_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(_("Payment Entry {0} changed after the review. Refresh before submitting.").format(doc.name))

	blockers, reference = _standard_submit_blockers(doc, payment_branch)
	if blockers:
		frappe.throw("<br>".join(blockers))

	# ERPNext remains authoritative for Payment Entry posting, GL/Payment Ledger
	# side effects, Sales Invoice outstanding and customer advance balances.
	doc.submit()
	if cint(getattr(doc, "docstatus", 0)) != 1:
		frappe.throw(_("ERPNext did not submit Payment Entry {0}.").format(doc.name))
	doc.reload()

	invoice_name = reference.get("sales_invoice") if reference else ""
	invoice_outstanding = (
		flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"))
		if invoice_name
		else None
	)
	return {
		"doctype": PAYMENT_ENTRY_DOCTYPE,
		"name": doc.name,
		"docstatus": cint(getattr(doc, "docstatus", 0)),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": payment_branch,
		"customer": str(getattr(doc, "party", "") or ""),
		"sales_invoice": invoice_name,
		"received_amount": flt(getattr(doc, "received_amount", 0)),
		"unallocated_amount": flt(getattr(doc, "unallocated_amount", 0)),
		"invoice_outstanding_amount": invoice_outstanding,
		"status": str(getattr(doc, "status", "") or "Submitted"),
		"source_of_truth": "ERPNext Payment Entry submit",
		"route": f"/app/payment-entry/{doc.name}",
	}
