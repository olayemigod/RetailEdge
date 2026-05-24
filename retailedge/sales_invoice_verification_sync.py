from __future__ import annotations

from typing import Iterable

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, now_datetime

from retailedge.cashier_context import get_shift_cash_snapshot
from retailedge.daily_sales_audit import _get_actual_closing_cash_amount
from retailedge.invoice_payment_audit import get_sales_invoice_payment_rows


VERIFICATION_STATUSES = (
	"Unverified",
	"Cash Verified by Shift",
	"Bank Verified",
	"Partially Verified",
	"Needs Review",
	"Amount Mismatch",
	"Duplicate Suspected",
	"Rejected",
)
VERIFICATION_SOURCES = (
	"Cash Shift Verification",
	"Bank Transaction Matching",
	"ERPNext Bank Reconciliation",
	"Manual Review",
)
SALES_INVOICE_VERIFICATION_FIELDS = (
	"retailedge_payment_verification_status",
	"retailedge_payment_verification_source",
	"retailedge_verified_amount",
	"retailedge_unverified_amount",
	"retailedge_payment_variance",
	"retailedge_verified_by",
	"retailedge_verified_on",
	"retailedge_verification_reference",
	"retailedge_verification_note",
	"retailedge_last_sync_on",
)
OPENING_SHIFT_FIELD_CANDIDATES = ("pos_opening_shift", "opening_shift", "linked_pos_opening_shift")
COMPANY_FIELD_CANDIDATES = ("company",)
POS_PROFILE_FIELD_CANDIDATES = ("pos_profile",)
CASHIER_FIELD_CANDIDATES = ("cashier", "owner")
BRANCH_FIELD_CANDIDATES = ("branch", "retailedge_branch")


def ensure_sales_invoice_verification_custom_fields():
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return {}

	custom_fields = {
		"Sales Invoice": [
			{
				"fieldname": "retailedge_payment_verification_section",
				"label": "RetailEdge Payment Verification",
				"fieldtype": "Section Break",
				"insert_after": "payments_tab",
			},
			{
				"fieldname": "retailedge_payment_verification_status",
				"label": "RetailEdge Payment Verification Status",
				"fieldtype": "Select",
				"options": "\n".join(VERIFICATION_STATUSES),
				"default": "Unverified",
				"read_only": 1,
				"in_standard_filter": 1,
				"insert_after": "retailedge_payment_verification_section",
			},
			{
				"fieldname": "retailedge_payment_verification_source",
				"label": "RetailEdge Verification Source",
				"fieldtype": "Select",
				"options": "\n".join(VERIFICATION_SOURCES),
				"read_only": 1,
				"insert_after": "retailedge_payment_verification_status",
			},
			{
				"fieldname": "retailedge_verified_amount",
				"label": "RetailEdge Verified Amount",
				"fieldtype": "Currency",
				"read_only": 1,
				"insert_after": "retailedge_payment_verification_source",
			},
			{
				"fieldname": "retailedge_unverified_amount",
				"label": "RetailEdge Unverified Amount",
				"fieldtype": "Currency",
				"read_only": 1,
				"insert_after": "retailedge_verified_amount",
			},
			{
				"fieldname": "retailedge_payment_variance",
				"label": "RetailEdge Payment Variance",
				"fieldtype": "Currency",
				"read_only": 1,
				"insert_after": "retailedge_unverified_amount",
			},
			{
				"fieldname": "retailedge_verified_by",
				"label": "RetailEdge Verified By",
				"fieldtype": "Link",
				"options": "User",
				"read_only": 1,
				"insert_after": "retailedge_payment_variance",
			},
			{
				"fieldname": "retailedge_verified_on",
				"label": "RetailEdge Verified On",
				"fieldtype": "Datetime",
				"read_only": 1,
				"insert_after": "retailedge_verified_by",
			},
			{
				"fieldname": "retailedge_verification_reference",
				"label": "RetailEdge Verification Reference",
				"fieldtype": "Data",
				"read_only": 1,
				"insert_after": "retailedge_verified_on",
			},
			{
				"fieldname": "retailedge_verification_note",
				"label": "RetailEdge Verification Note",
				"fieldtype": "Small Text",
				"read_only": 1,
				"insert_after": "retailedge_verification_reference",
			},
			{
				"fieldname": "retailedge_last_sync_on",
				"label": "RetailEdge Last Verification Sync On",
				"fieldtype": "Datetime",
				"read_only": 1,
				"insert_after": "retailedge_verification_note",
			},
		]
	}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	return custom_fields


def get_sales_invoice_verification_fields():
	return list(SALES_INVOICE_VERIFICATION_FIELDS)


def sales_invoice_has_verification_fields():
	try:
		meta = frappe.get_meta("Sales Invoice")
	except Exception:
		return False
	return all(meta.has_field(fieldname) for fieldname in SALES_INVOICE_VERIFICATION_FIELDS)


def assert_sales_invoice_verification_fields():
	if sales_invoice_has_verification_fields():
		return
	frappe.throw(
		"RetailEdge Sales Invoice verification fields are missing. Run bench migrate for the site before syncing verification status."
	)


def sync_sales_invoice_payment_verification(
	invoice_name,
	status,
	source,
	verified_amount=None,
	unverified_amount=None,
	variance=None,
	reference=None,
	note=None,
	verified_by=None,
	verified_on=None,
	commit=False,
):
	assert_sales_invoice_verification_fields()
	if status not in VERIFICATION_STATUSES:
		frappe.throw(f"Unsupported RetailEdge verification status: {status}")
	if source and source not in VERIFICATION_SOURCES:
		frappe.throw(f"Unsupported RetailEdge verification source: {source}")
	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(f"Sales Invoice {invoice_name} was not found.")

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	expected_amount = _get_invoice_expected_amount(invoice)
	resolved_verified_amount = flt(verified_amount if verified_amount is not None else expected_amount)
	resolved_unverified_amount = (
		flt(unverified_amount)
		if unverified_amount is not None
		else max(expected_amount - resolved_verified_amount, 0.0)
	)
	values = {
		"retailedge_payment_verification_status": status,
		"retailedge_payment_verification_source": source or "",
		"retailedge_verified_amount": resolved_verified_amount,
		"retailedge_unverified_amount": resolved_unverified_amount,
		"retailedge_payment_variance": flt(variance),
		"retailedge_verified_by": verified_by or frappe.session.user,
		"retailedge_verified_on": verified_on or now_datetime(),
		"retailedge_verification_reference": reference or "",
		"retailedge_verification_note": note or "",
		"retailedge_last_sync_on": now_datetime(),
	}
	frappe.db.set_value("Sales Invoice", invoice_name, values, update_modified=False)
	if commit:
		frappe.db.commit()
	return {
		"sales_invoice": invoice_name,
		"status": values["retailedge_payment_verification_status"],
		"source": values["retailedge_payment_verification_source"],
		"verified_amount": values["retailedge_verified_amount"],
		"unverified_amount": values["retailedge_unverified_amount"],
		"variance": values["retailedge_payment_variance"],
		"reference": values["retailedge_verification_reference"],
		"note": values["retailedge_verification_note"],
		"verified_by": values["retailedge_verified_by"],
		"verified_on": values["retailedge_verified_on"],
		"last_sync_on": values["retailedge_last_sync_on"],
	}


def reset_sales_invoice_payment_verification(invoice_name, note=None):
	assert_sales_invoice_verification_fields()
	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(f"Sales Invoice {invoice_name} was not found.")
	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	expected_amount = _get_invoice_expected_amount(invoice)
	return sync_sales_invoice_payment_verification(
		invoice_name=invoice_name,
		status="Unverified",
		source="",
		verified_amount=0,
		unverified_amount=expected_amount,
		variance=0,
		reference="",
		note=note,
		verified_by=None,
		verified_on=None,
	)


def sync_cash_verified_sales_invoices_for_shift(opening_shift=None, closing_shift=None, daily_sales_audit=None, dry_run=True, force=False):
	assert_sales_invoice_verification_fields()
	context = _resolve_cash_sync_context(opening_shift=opening_shift, closing_shift=closing_shift, daily_sales_audit=daily_sales_audit)
	approval_ready = _is_cash_sync_approved(context, force=force)
	reference = _build_cash_reference(context)
	note = _build_cash_note(context, approval_ready=approval_ready, force=force)
	invoices = []
	eligible_count = synced_count = skipped_count = 0

	for invoice in _get_candidate_shift_invoices(context):
		payment_rows = get_sales_invoice_payment_rows(invoice)
		cash_rows = [row for row in payment_rows if row.get("payment_category") == "Cash" and flt(row.get("base_amount")) > 0]
		non_cash_rows = [row for row in payment_rows if row.get("payment_category") != "Cash" and flt(row.get("base_amount")) > 0]
		old_status = getattr(invoice, "retailedge_payment_verification_status", None) or "Unverified"
		row_result = {
			"sales_invoice": invoice.name,
			"customer": getattr(invoice, "customer", None),
			"posting_date": getattr(invoice, "posting_date", None),
			"grand_total": flt(getattr(invoice, "grand_total", 0)),
			"cash_amount": sum(flt(row.get("base_amount")) for row in cash_rows),
			"old_verification_status": old_status,
			"new_verification_status": "Cash Verified by Shift",
			"action": "Skipped",
			"reason": None,
		}
		if getattr(invoice, "docstatus", 0) != 1:
			row_result["reason"] = "Only submitted Sales Invoices are eligible."
			skipped_count += 1
			invoices.append(row_result)
			continue
		if not cash_rows:
			row_result["reason"] = "Invoice has no cash payment rows."
			skipped_count += 1
			invoices.append(row_result)
			continue
		if non_cash_rows:
			row_result["reason"] = "Invoice contains non-cash payment rows and is excluded from cash-only verification sync."
			skipped_count += 1
			invoices.append(row_result)
			continue
		eligible_count += 1
		if not approval_ready:
			row_result["action"] = "Skipped"
			row_result["reason"] = "Cash shift is not yet balanced or approved."
			skipped_count += 1
			invoices.append(row_result)
			continue
		if dry_run:
			row_result["action"] = "Would Sync"
			row_result["reason"] = note
			invoices.append(row_result)
			continue
		sync_sales_invoice_payment_verification(
			invoice_name=invoice.name,
			status="Cash Verified by Shift",
			source="Cash Shift Verification",
			verified_amount=row_result["cash_amount"],
			unverified_amount=max(_get_invoice_expected_amount(invoice) - row_result["cash_amount"], 0.0),
			variance=context["cash_variance"],
			reference=reference,
			note=note,
		)
		row_result["action"] = "Synced"
		row_result["reason"] = note
		invoices.append(row_result)
		synced_count += 1

	return {
		"opening_shift": context.get("opening_shift"),
		"closing_shift": context.get("closing_shift"),
		"daily_sales_audit": context.get("daily_sales_audit"),
		"cash_sales": context["cash_sales"],
		"opening_cash": context["opening_cash"],
		"included_cashier_expenses": context["included_cashier_expenses"],
		"expected_cash": context["expected_cash"],
		"actual_closing_cash": context["actual_closing_cash"],
		"cash_variance": context["cash_variance"],
		"eligible_invoice_count": eligible_count,
		"synced_invoice_count": synced_count,
		"skipped_invoice_count": skipped_count,
		"dry_run": bool(dry_run),
		"invoices": invoices,
	}


def sync_bank_verified_sales_invoice_from_bank_transaction(
	invoice_name,
	bank_transaction_name,
	verified_amount,
	reference=None,
	note=None,
	dry_run=True,
):
	assert_sales_invoice_verification_fields()
	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(f"Sales Invoice {invoice_name} was not found.")
	if not frappe.db.exists("Bank Transaction", bank_transaction_name):
		frappe.throw(f"Bank Transaction {bank_transaction_name} was not found.")

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	old_status = getattr(invoice, "retailedge_payment_verification_status", None) or "Unverified"
	payload = {
		"sales_invoice": invoice_name,
		"bank_transaction": bank_transaction_name,
		"old_verification_status": old_status,
		"new_verification_status": "Bank Verified",
		"verified_amount": flt(verified_amount),
		"reference": reference or bank_transaction_name,
		"note": note,
		"dry_run": bool(dry_run),
		"action": "Would Sync" if dry_run else "Synced",
	}
	if dry_run:
		return payload

	sync_sales_invoice_payment_verification(
		invoice_name=invoice_name,
		status="Bank Verified",
		source="Bank Transaction Matching",
		verified_amount=flt(verified_amount),
		unverified_amount=max(_get_invoice_expected_amount(invoice) - flt(verified_amount), 0.0),
		variance=0,
		reference=reference or bank_transaction_name,
		note=note,
	)
	return payload


def _resolve_cash_sync_context(opening_shift=None, closing_shift=None, daily_sales_audit=None):
	context = {
		"opening_shift": opening_shift,
		"closing_shift": closing_shift,
		"daily_sales_audit": daily_sales_audit,
		"company": None,
		"branch": None,
		"pos_profile": None,
		"cashier": None,
		"shift_date": None,
		"opening_cash": 0.0,
		"cash_sales": 0.0,
		"included_cashier_expenses": 0.0,
		"expected_cash": 0.0,
		"actual_closing_cash": 0.0,
		"cash_variance": 0.0,
		"audit_status": None,
	}
	audit_doc = None
	if daily_sales_audit:
		audit_doc = frappe.get_doc("RetailEdge Daily Sales Audit", daily_sales_audit)
	elif opening_shift or closing_shift:
		filters = {}
		if opening_shift:
			filters["pos_opening_shift"] = opening_shift
		if closing_shift:
			filters["pos_closing_shift"] = closing_shift
		audit_name = frappe.db.get_value("RetailEdge Daily Sales Audit", filters, "name") if filters else None
		if audit_name:
			audit_doc = frappe.get_doc("RetailEdge Daily Sales Audit", audit_name)

	if audit_doc:
		context.update(
			{
				"opening_shift": getattr(audit_doc, "pos_opening_shift", None) or context["opening_shift"],
				"closing_shift": getattr(audit_doc, "pos_closing_shift", None) or context["closing_shift"],
				"daily_sales_audit": audit_doc.name,
				"company": getattr(audit_doc, "company", None),
				"branch": getattr(audit_doc, "branch", None),
				"pos_profile": getattr(audit_doc, "pos_profile", None),
				"cashier": getattr(audit_doc, "cashier", None),
				"shift_date": getattr(audit_doc, "audit_date", None),
				"opening_cash": flt(getattr(audit_doc, "opening_cash_amount", 0)),
				"cash_sales": flt(getattr(audit_doc, "cash_sales_amount", 0)),
				"included_cashier_expenses": flt(getattr(audit_doc, "cashier_expense_amount", 0)),
				"expected_cash": flt(getattr(audit_doc, "expected_cash_amount", 0)),
				"actual_closing_cash": flt(getattr(audit_doc, "actual_closing_cash_amount", 0)),
				"cash_variance": flt(getattr(audit_doc, "cash_variance_amount", 0)),
				"audit_status": getattr(audit_doc, "audit_status", None),
			}
		)
		return context

	snapshot = get_shift_cash_snapshot(opening_shift=opening_shift, pos_profile=None, company=None)
	actual = _get_actual_closing_cash_amount(pos_closing_shift=closing_shift, pos_opening_shift=opening_shift)
	context["opening_cash"] = flt(snapshot.get("opening_cash"))
	context["cash_sales"] = flt(snapshot.get("cash_sales"))
	context["included_cashier_expenses"] = flt(snapshot.get("prior_expenses"))
	context["expected_cash"] = context["opening_cash"] + context["cash_sales"] - context["included_cashier_expenses"]
	context["actual_closing_cash"] = flt(actual.get("amount"))
	context["cash_variance"] = context["actual_closing_cash"] - context["expected_cash"]
	return context


def _get_candidate_shift_invoices(context) -> Iterable:
	if context.get("daily_sales_audit"):
		audit_doc = frappe.get_doc("RetailEdge Daily Sales Audit", context["daily_sales_audit"])
		names = [row.sales_invoice for row in getattr(audit_doc, "invoice_lines", []) or [] if getattr(row, "sales_invoice", None)]
		if names:
			return [frappe.get_doc("Sales Invoice", name) for name in names if frappe.db.exists("Sales Invoice", name)]

	meta = frappe.get_meta("Sales Invoice")
	filters = {"docstatus": 1}
	if meta.has_field("is_pos"):
		filters["is_pos"] = 1
	if context.get("opening_shift"):
		for fieldname in OPENING_SHIFT_FIELD_CANDIDATES:
			if meta.has_field(fieldname):
				filters[fieldname] = context["opening_shift"]
				break
	if context.get("company"):
		for fieldname in COMPANY_FIELD_CANDIDATES:
			if meta.has_field(fieldname):
				filters[fieldname] = context["company"]
				break
	if context.get("pos_profile"):
		for fieldname in POS_PROFILE_FIELD_CANDIDATES:
			if meta.has_field(fieldname):
				filters[fieldname] = context["pos_profile"]
				break
	if context.get("cashier"):
		for fieldname in CASHIER_FIELD_CANDIDATES:
			if meta.has_field(fieldname):
				filters[fieldname] = context["cashier"]
				break
	if context.get("branch"):
		for fieldname in BRANCH_FIELD_CANDIDATES:
			if meta.has_field(fieldname):
				filters[fieldname] = context["branch"]
				break
	if context.get("shift_date") and meta.has_field("posting_date"):
		filters["posting_date"] = context["shift_date"]

	rows = frappe.get_all("Sales Invoice", filters=filters, fields=["name"], limit_page_length=0, order_by="posting_date asc, creation asc")
	return [frappe.get_doc("Sales Invoice", row.name) for row in rows]


def _is_cash_sync_approved(context, force=False):
	if force:
		return True
	status = context.get("audit_status")
	if status in {"Balanced", "Approved"}:
		return True
	if not context.get("closing_shift"):
		return False
	return False


def _build_cash_reference(context):
	parts = [context.get("opening_shift"), context.get("closing_shift"), context.get("daily_sales_audit")]
	return " | ".join(part for part in parts if part)


def _build_cash_note(context, approval_ready, force=False):
	if force and not approval_ready:
		return "RetailEdge cash verification sync was forced by an authorized reviewer."
	variance = flt(context.get("cash_variance"))
	status = context.get("audit_status")
	if not approval_ready:
		return "RetailEdge cash verification is pending until the shift is balanced or approved."
	if variance and status == "Approved":
		return f"RetailEdge cash verification synced after approved variance of {variance:.2f}."
	return "RetailEdge cash verification synced from approved shift cash controls."


def _get_invoice_expected_amount(invoice):
	return flt(getattr(invoice, "rounded_total", None) or getattr(invoice, "grand_total", 0))
