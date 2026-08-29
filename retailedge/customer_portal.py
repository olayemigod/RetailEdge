from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from frappe.utils.user import is_website_user

from erpnext.controllers.website_list_for_contact import get_parents_for_user

MAX_PORTAL_ROWS = 200

PORTAL_SECTIONS: tuple[dict[str, str], ...] = (
	{"key": "quotations", "doctype": "Quotation", "route": "/quotations", "label": "Quotations"},
	{"key": "orders", "doctype": "Sales Order", "route": "/orders", "label": "Orders"},
	{"key": "invoices", "doctype": "Sales Invoice", "route": "/invoices", "label": "Invoices"},
	{"key": "shipments", "doctype": "Delivery Note", "route": "/shipments", "label": "Shipments"},
	{"key": "projects", "doctype": "Project", "route": "/project", "label": "Projects"},
)


def _assert_customer_portal_user() -> list[str]:
	if frappe.session.user == "Guest" or not is_website_user():
		frappe.throw(_("Please sign in with your customer account."), frappe.PermissionError)
	if "Customer" not in frappe.get_roles(frappe.session.user):
		frappe.throw(_("Customer Portal access requires the Customer role."), frappe.PermissionError)
	customers = [str(name) for name in get_parents_for_user("Customer") if name]
	if not customers:
		frappe.throw(_("Your account is not linked to a Customer record."), frappe.PermissionError)
	return customers


def _customer_filter(doctype: str, customers: list[str]) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if doctype == "Quotation":
		filters.update({"quotation_to": "Customer", "party_name": ["in", customers]})
	else:
		filters["customer"] = ["in", customers]
	return filters


def _safe_list(
	doctype: str,
	customers: list[str],
	*,
	fields: list[str],
	filters: dict[str, Any] | None = None,
	order_by: str = "modified desc",
	limit: int = MAX_PORTAL_ROWS,
) -> list[Any]:
	if not frappe.db.exists("DocType", doctype):
		return []
	merged = _customer_filter(doctype, customers)
	merged.update(filters or {})
	# ERPNext's website transaction controller uses the same customer boundary
	# before bypassing Desk permissions for Website Users. Keep this query
	# strictly server-derived from Portal User -> Customer links.
	return frappe.get_list(
		doctype,
		filters=merged,
		fields=fields,
		order_by=order_by,
		limit_page_length=max(1, min(int(limit or MAX_PORTAL_ROWS), MAX_PORTAL_ROWS)),
		ignore_permissions=True,
	)


def _recent_rows(doctype: str, customers: list[str], limit: int = 5) -> list[dict[str, Any]]:
	meta = frappe.get_meta(doctype)
	fields = ["name", "modified"]
	for fieldname in (
		"status",
		"transaction_date",
		"posting_date",
		"due_date",
		"grand_total",
		"currency",
		"outstanding_amount",
		"project_name",
		"percent_complete",
	):
		if meta.has_field(fieldname):
			fields.append(fieldname)
	filters: dict[str, Any] = {}
	if meta.has_field("docstatus") and doctype not in {"Project"}:
		filters["docstatus"] = ["<", 2]
	rows = _safe_list(doctype, customers, fields=fields, filters=filters, limit=limit)
	result = []
	for row in rows:
		outstanding = flt(getattr(row, "outstanding_amount", 0))
		due_date = getattr(row, "due_date", None)
		is_overdue = bool(doctype == "Sales Invoice" and outstanding > 0 and due_date and getdate(due_date) < getdate(today()))
		result.append(
			{
				"name": row.name,
				"status": getattr(row, "status", "") or "",
				"date": getattr(row, "transaction_date", None) or getattr(row, "posting_date", None),
				"due_date": due_date,
				"is_overdue": is_overdue,
				"grand_total": flt(getattr(row, "grand_total", 0)),
				"outstanding_amount": outstanding,
				"currency": getattr(row, "currency", "") or "",
				"project_name": getattr(row, "project_name", "") or "",
				"percent_complete": flt(getattr(row, "percent_complete", 0)),
			}
		)
	return result


def _invoice_summary(customers: list[str]) -> dict[str, Any]:
	rows = _safe_list(
		"Sales Invoice",
		customers,
		fields=["name", "grand_total", "outstanding_amount", "currency", "status", "due_date"],
		filters={"docstatus": 1, "is_return": 0},
	)
	today_date = getdate(today())
	overdue_rows = [row for row in rows if flt(row.outstanding_amount) > 0 and row.due_date and getdate(row.due_date) < today_date]
	return {
		"count": len(rows),
		"outstanding": sum(flt(row.outstanding_amount) for row in rows),
		"overdue_count": len(overdue_rows),
		"overdue_amount": sum(flt(row.outstanding_amount) for row in overdue_rows),
		"billed": sum(flt(row.grand_total) for row in rows),
		"currency": next((str(row.currency or "") for row in rows if row.currency), ""),
		"overdue_basis": "Submitted Sales Invoice due date plus positive outstanding amount.",
	}


def _payment_summary(customers: list[str]) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Payment Entry"):
		return {"count": 0, "received": 0.0, "recent": []}
	rows = frappe.get_list(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": ["in", customers],
		},
		fields=[
			"name",
			"posting_date",
			"party",
			"mode_of_payment",
			"reference_no",
			"base_received_amount",
			"received_amount",
			"paid_from_account_currency",
		],
		order_by="posting_date desc, name desc",
		limit_page_length=MAX_PORTAL_ROWS,
		ignore_permissions=True,
	)
	recent = []
	for row in rows[:5]:
		recent.append(
			{
				"name": row.name,
				"posting_date": row.posting_date,
				"party": row.party or "",
				"mode_of_payment": row.mode_of_payment or "",
				"reference_no": row.reference_no or "",
				"amount": flt(row.base_received_amount or row.received_amount),
				"currency": row.paid_from_account_currency or "",
			}
		)
	return {
		"count": len(rows),
		"received": sum(flt(row.base_received_amount or row.received_amount) for row in rows),
		"recent": recent,
		"scope_note": _("Submitted incoming payments linked to your Customer account. This is payment history, not a wallet balance."),
	}


def _document_count(doctype: str, customers: list[str], submitted_only: bool = False) -> int:
	meta = frappe.get_meta(doctype)
	filters: dict[str, Any] = {}
	if submitted_only and meta.has_field("docstatus"):
		filters["docstatus"] = 1
	return len(_safe_list(doctype, customers, fields=["name"], filters=filters))


def get_customer_portal_context() -> dict[str, Any]:
	customers = _assert_customer_portal_user()
	invoice_summary = _invoice_summary(customers)
	payment_summary = _payment_summary(customers)
	sections = []
	for spec in PORTAL_SECTIONS:
		doctype = spec["doctype"]
		sections.append(
			{
				**spec,
				"count": _document_count(doctype, customers, submitted_only=doctype != "Project"),
				"recent": _recent_rows(doctype, customers),
			}
		)
	return {
		"customer_names": customers,
		"customer_label": customers[0] if len(customers) == 1 else _("Your Accounts"),
		"user": frappe.session.user,
		"user_full_name": frappe.get_user().get_fullname(),
		"invoice_summary": invoice_summary,
		"payment_summary": payment_summary,
		"sections": sections,
		"routes": {
			"quotations": "/quotations",
			"orders": "/orders",
			"invoices": "/invoices",
			"shipments": "/shipments",
			"projects": "/project",
		},
		"security": {
			"customer_source": "ERPNext Portal User links",
			"customer_filter_server_derived": True,
			"native_document_pages": True,
			"payment_history_read_only": True,
			"cross_customer_selection": False,
		},
	}
