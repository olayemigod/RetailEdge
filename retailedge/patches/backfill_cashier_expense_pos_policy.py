from __future__ import annotations

import frappe


def execute():
	if not frappe.db.exists("DocType", "RetailEdge Settings"):
		return

	mode = frappe.db.get_single_value("RetailEdge Settings", "cashier_expense_posting_mode")
	if not mode:
		legacy = frappe.db.get_single_value(
			"RetailEdge Settings",
			"require_cashier_expense_approval_before_posting",
		)
		mode = "Controlled Posting" if legacy in (None, "", 1, "1") else "Direct Posting"
		frappe.db.set_single_value("RetailEdge Settings", "cashier_expense_posting_mode", mode)

	if not frappe.db.exists("DocType", "RetailEdge Cashier Expense"):
		return

	fields = {df.fieldname for df in frappe.get_meta("RetailEdge Cashier Expense").fields}
	required = {"entry_source", "cash_source", "cash_movement_status", "posting_mode_applied"}
	if not required.issubset(fields):
		return

	frappe.db.sql(
		"""
		UPDATE `tabRetailEdge Cashier Expense`
		SET entry_source = 'RetailEdge'
		WHERE IFNULL(entry_source, '') = ''
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabRetailEdge Cashier Expense`
		SET cash_source = 'POS Till'
		WHERE IFNULL(cash_source, '') = ''
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabRetailEdge Cashier Expense`
		SET posting_mode_applied = %s
		WHERE IFNULL(posting_mode_applied, '') = ''
		""",
		(mode,),
	)
	frappe.db.sql(
		"""
		UPDATE `tabRetailEdge Cashier Expense`
		SET cash_movement_status = CASE
			WHEN docstatus = 2 OR expense_status = 'Cancelled' THEN 'Reversed'
			WHEN docstatus = 1 THEN 'Disbursed'
			ELSE 'Not Disbursed'
		END
		WHERE IFNULL(cash_movement_status, '') = ''
		"""
	)
