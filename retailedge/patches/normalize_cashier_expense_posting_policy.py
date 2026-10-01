from __future__ import annotations

import frappe


def execute():
	"""Remove the historical unsupported Payment Entry Cashier Expense posting option."""
	if not frappe.db.exists("DocType", "RetailEdge Settings"):
		return
	value = frappe.db.get_single_value("RetailEdge Settings", "cashier_expense_posting_document_type")
	if str(value or "").strip() != "Journal Entry":
		frappe.db.set_single_value(
			"RetailEdge Settings",
			"cashier_expense_posting_document_type",
			"Journal Entry",
			update_modified=False,
		)
