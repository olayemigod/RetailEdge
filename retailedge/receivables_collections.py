from __future__ import annotations

from typing import Any

import frappe

ACTIVE_DUNNING_STATUSES = {"Draft", "Unresolved"}
ACTIVE_PAYMENT_REQUEST_STATUSES = {"Requested", "Initiated", "Partially Paid", "Failed"}
MAX_COLLECTION_ROWS = 2000


def enrich_receivable_rows(rows: list[dict[str, Any]], *, company: str) -> dict[str, Any]:
	"""Add read-only native collections state to already-permitted receivable rows."""
	invoice_names = [str(row.get("invoice") or "") for row in rows if row.get("invoice")]
	payment_requests = _payment_request_map(invoice_names)
	dunnings = _active_dunning_map(invoice_names, company=company)
	dunning_installed = bool(frappe.db.exists("DocType", "Dunning"))
	dunning_create_allowed = bool(dunning_installed and frappe.has_permission("Dunning", "create"))

	payment_request_count = 0
	dunning_ready_count = 0
	active_dunning_count = 0
	for row in rows:
		invoice = str(row.get("invoice") or "")
		payment_request = payment_requests.get(invoice) or {}
		dunning = dunnings.get(invoice) or {}
		overdue = int(row.get("overdue_days") or 0) > 0 and float(row.get("outstanding") or 0) > 0
		dunning_ready = bool(overdue and not dunning and dunning_create_allowed)

		if payment_request:
			payment_request_count += 1
		if dunning:
			active_dunning_count += 1
		if dunning_ready:
			dunning_ready_count += 1

		row.update(
			{
				"payment_request": payment_request.get("name", ""),
				"payment_request_status": payment_request.get("status", ""),
				"dunning": dunning.get("name", ""),
				"dunning_status": dunning.get("status", ""),
				"dunning_ready": dunning_ready,
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
			"dunning_readable": _can_read_doctype("Dunning"),
			"dunning_create_allowed": dunning_create_allowed,
			"payment_request_count": payment_request_count,
			"active_dunning_count": active_dunning_count,
			"dunning_ready_count": dunning_ready_count,
			"read_only_enrichment": True,
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
			"docstatus": 1,
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


def _active_dunning_map(invoice_names: list[str], *, company: str) -> dict[str, dict[str, Any]]:
	if not invoice_names or not company or not _can_read_doctype("Dunning"):
		return {}
	# Parent Dunning names are permission-filtered first. Child rows are then read
	# only from those permitted parents; Overdue Payment has no standalone roles.
	parents = frappe.get_list(
		"Dunning",
		filters={
			"company": company,
			"docstatus": ["<", 2],
			"status": ["in", sorted(ACTIVE_DUNNING_STATUSES)],
		},
		fields=["name", "status", "creation"],
		order_by="creation desc",
		limit=MAX_COLLECTION_ROWS,
	)
	if not parents:
		return {}

	invoice_set = set(invoice_names)
	result: dict[str, dict[str, Any]] = {}
	for parent in parents:
		doc = frappe.get_doc("Dunning", parent.name)
		doc.check_permission("read")
		for payment in doc.get("overdue_payments") or []:
			invoice = str(payment.get("sales_invoice") or "")
			if invoice in invoice_set and invoice not in result:
				result[invoice] = {"name": doc.name, "status": doc.status or ""}
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
