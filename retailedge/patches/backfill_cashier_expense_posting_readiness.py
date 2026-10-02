from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from retailedge.cashier_expense_posting import build_cashier_expense_posting_preview


EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
PAGE_LENGTH = 200


def execute():
	"""Backfill stored posting-readiness state without creating accounting entries."""
	if not frappe.db.exists("DocType", EXPENSE_DOCTYPE):
		return

	meta = frappe.get_meta(EXPENSE_DOCTYPE)
	required_fields = {
		"posting_ready",
		"posting_block_reason",
		"resolved_debit_account",
		"resolved_credit_account",
		"resolved_posting_cost_center",
		"posting_preview",
	}
	if not required_fields.issubset({field.fieldname for field in meta.fields}):
		return

	start = 0
	refreshed_on = now_datetime()
	while True:
		rows = frappe.get_all(
			EXPENSE_DOCTYPE,
			filters={
				"docstatus": 1,
				"expense_status": ["!=", "Cancelled"],
				"ledger_status": ["!=", "Posted"],
			},
			fields=["name"],
			order_by="name asc",
			limit_start=start,
			limit_page_length=PAGE_LENGTH,
		)
		if not rows:
			break

		for row in rows:
			doc = frappe.get_doc(EXPENSE_DOCTYPE, row.name)
			preview = build_cashier_expense_posting_preview(doc)
			values = {
				"posting_ready": 1 if preview.get("posting_ready") else 0,
				"posting_block_reason": preview.get("posting_block_reason"),
				"resolved_debit_account": preview.get("debit_account"),
				"resolved_credit_account": preview.get("credit_account"),
				"resolved_posting_cost_center": preview.get("cost_center"),
				"posting_preview": preview.get("posting_preview"),
			}
			if meta.has_field("last_readiness_refresh_on"):
				values["last_readiness_refresh_on"] = refreshed_on
			if meta.has_field("last_readiness_refresh_by"):
				values["last_readiness_refresh_by"] = frappe.session.user
			frappe.db.set_value(
				EXPENSE_DOCTYPE,
				row.name,
				values,
				update_modified=False,
			)

		start += len(rows)
