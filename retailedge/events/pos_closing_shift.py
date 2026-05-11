from __future__ import annotations

import frappe


def on_pos_closing_shift_save(doc, method=None):
	update_cashier_expenses_with_closing_shift(doc)


def on_pos_closing_shift_submit(doc, method=None):
	update_cashier_expenses_with_closing_shift(doc)


def update_cashier_expenses_with_closing_shift(doc):
	try:
		opening_shift = None
		for fieldname in ("pos_opening_shift", "opening_shift", "linked_pos_opening_shift"):
			if getattr(doc, fieldname, None):
				opening_shift = getattr(doc, fieldname)
				break

		if not opening_shift:
			return

		expenses = frappe.get_all(
			"RetailEdge Cashier Expense",
			filters={
				"linked_pos_opening_shift": opening_shift,
				"docstatus": ["!=", 2],
			},
			fields=["name", "linked_pos_closing_shift"],
			limit_page_length=0,
		)

		for expense in expenses:
			if getattr(expense, "linked_pos_closing_shift", None):
				continue
			frappe.db.set_value(
				"RetailEdge Cashier Expense",
				expense.name,
				"linked_pos_closing_shift",
				doc.name,
				update_modified=False,
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "RetailEdge POS Closing Shift link update failed")
