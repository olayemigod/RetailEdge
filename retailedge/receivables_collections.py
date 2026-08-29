from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe.utils import getdate, today

ACTIVE_DUNNING_STATUSES = {"Draft", "Unresolved"}
ACTIVE_PAYMENT_REQUEST_STATUSES = {"Draft", "Requested", "Initiated", "Partially Paid", "Failed"}
MAX_COLLECTION_ROWS = 2000


def enrich_receivable_rows(rows: list[dict[str, Any]], *, company: str) -> dict[str, Any]:
	"""Add native collections state and governed draft-handoff readiness to permitted rows."""
	invoice_names = [str(row.get("invoice") or "") for row in rows if row.get("invoice")]
	payment_requests = _payment_request_map(invoice_names)
	dunnings = _active_dunning_map(invoice_names, company=company)
	dunning_eligible = _dunning_eligible_invoice_names(invoice_names)
	payment_request_create_allowed = _can_create_doctype("Payment Request")
	dunning_create_allowed = _can_create_doctype("Dunning")

	payment_request_count = 0
	payment_request_ready_count = 0
	dunning_ready_count = 0
	active_dunning_count = 0
	for row in rows:
		invoice = str(row.get("invoice") or "")
		payment_request = payment_requests.get(invoice) or {}
		dunning = dunnings.get(invoice) or {}
		outstanding = float(row.get("outstanding") or 0)
		overdue = int(row.get("overdue_days") or 0) > 0 and outstanding > 0
		payment_request_ready = bool(outstanding > 0 and not payment_request and payment_request_create_allowed)
		dunning_ready = bool(
			invoice in dunning_eligible and not dunning and dunning_create_allowed
		)

		if payment_request:
			payment_request_count += 1
		if payment_request_ready:
			payment_request_ready_count += 1
		if dunning:
			active_dunning_count += 1
		if dunning_ready:
			dunning_ready_count += 1

		row.update(
			{
				"payment_request": payment_request.get("name", ""),
				"payment_request_status": payment_request.get("status", ""),
				"payment_request_ready": payment_request_ready,
				"payment_request_action": _("Prepare Payment Request") if payment_request_ready else "",
				"dunning": dunning.get("name", ""),
				"dunning_status": dunning.get("status", ""),
				"dunning_ready": dunning_ready,
				"dunning_action": _("Prepare Dunning") if dunning_ready else "",
				"collection_status": _collection_status(
					overdue=overdue,
					payment_request=payment_request,
					dunning=dunning,
					dunning_ready=dunning_ready,
				),
			}
		)

	return {
		"rows": rows,
		"metadata": {
			"payment_request_readable": _can_read_doctype("Payment Request"),
			"payment_request_create_allowed": payment_request_create_allowed,
			"dunning_readable": _can_read_doctype("Dunning"),
			"dunning_create_allowed": dunning_create_allowed,
			"payment_request_count": payment_request_count,
			"payment_request_ready_count": payment_request_ready_count,
			"active_dunning_count": active_dunning_count,
			"dunning_ready_count": dunning_ready_count,
			"read_only_enrichment": True,
			"draft_handoffs_only": True,
			"automatic_submit": False,
		},
	}


def _payment_request_map(invoice_names: list[str]) -> dict[str, dict[str, Any]]:
	if not invoice_names or not _can_read_doctype("Payment Request"):
		return {}
	rows = frappe.get_list(
		"Payment Request",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": ["in", invoice_names],
			"docstatus": ["<", 2],
			"status": ["in", sorted(ACTIVE_PAYMENT_REQUEST_STATUSES)],
		},
		fields=["name", "reference_name", "status", "creation"],
		order_by="creation desc",
		limit=MAX_COLLECTION_ROWS,
	)
	result: dict[str, dict[str, Any]] = {}
	for row in rows:
		invoice = str(row.reference_name or "")
		if invoice and invoice not in result:
			result[invoice] = {"name": row.name, "status": row.status or ""}
	return result


def _dunning_eligible_invoice_names(invoice_names: list[str]) -> set[str]:
	"""Mirror ERPNext Dunning eligibility for already-permitted Sales Invoices."""
	if not invoice_names:
		return set()
	rows = frappe.get_all(
		"Payment Schedule",
		filters={
			"parenttype": "Sales Invoice",
			"parentfield": "payment_schedule",
			"parent": ["in", invoice_names],
		},
		fields=["parent", "due_date", "outstanding"],
		limit=MAX_COLLECTION_ROWS,
	)
	if not rows:
		return set()

	today_date = getdate(today())
	return {
		str(row.parent)
		for row in rows
		if row.parent and float(row.outstanding or 0) > 0 and row.due_date and getdate(row.due_date) < today_date
	}


def _active_dunning_map(invoice_names: list[str], *, company: str) -> dict[str, dict[str, Any]]:
	if not invoice_names or not company or not _can_read_doctype("Dunning"):
		return {}

	# Overdue Payment is a child table with no standalone permission model. Read it
	# only to discover candidate Dunning parents for the already-permitted invoice
	# set, then apply normal permission-filtered Dunning reads before exposing data.
	candidate_links = frappe.get_all(
		"Overdue Payment",
		filters={
			"parenttype": "Dunning",
			"parentfield": "overdue_payments",
			"sales_invoice": ["in", invoice_names],
		},
		fields=["parent", "sales_invoice"],
		limit=MAX_COLLECTION_ROWS,
	)
	if not candidate_links:
		return {}

	invoices_by_parent: dict[str, set[str]] = defaultdict(set)
	for link in candidate_links:
		parent = str(link.parent or "")
		invoice = str(link.sales_invoice or "")
		if parent and invoice:
			invoices_by_parent[parent].add(invoice)
	if not invoices_by_parent:
		return {}

	parents = frappe.get_list(
		"Dunning",
		filters={
			"name": ["in", list(invoices_by_parent)],
			"company": company,
			"docstatus": ["<", 2],
			"status": ["in", sorted(ACTIVE_DUNNING_STATUSES)],
		},
		fields=["name", "status", "creation"],
		order_by="creation desc",
		limit=MAX_COLLECTION_ROWS,
	)

	result: dict[str, dict[str, Any]] = {}
	for parent in parents:
		for invoice in invoices_by_parent.get(str(parent.name or ""), set()):
			if invoice not in result:
				result[invoice] = {"name": parent.name, "status": parent.status or ""}
	return result


def _collection_status(
	*,
	overdue: bool,
	payment_request: dict[str, Any],
	dunning: dict[str, Any],
	dunning_ready: bool,
) -> str:
	if dunning:
		return f"Dunning {dunning.get('status') or 'Open'}"
	if payment_request:
		return f"Payment {payment_request.get('status') or 'Requested'}"
	if dunning_ready:
		return "Dunning Ready"
	if overdue:
		return "Overdue"
	return "Current"


def _can_read_doctype(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "read"))


def _can_create_doctype(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "create"))
