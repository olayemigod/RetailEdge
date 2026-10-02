from __future__ import annotations

import frappe


@frappe.whitelist()
def can_open_expense_register() -> dict[str, int]:
	"""Return whether the current user may open the consolidated Expense Register."""
	if not frappe.session.user or frappe.session.user == "Guest":
		return {"can_open": 0}
	try:
		if not frappe.db.exists("Page", "expense-register"):
			return {"can_open": 0}
		return {"can_open": int(bool(frappe.get_doc("Page", "expense-register").is_permitted()))}
	except Exception:
		return {"can_open": 0}


# Standard Frappe Page controller. Cashier Expense data is served by the
# permission-aware Expense Register endpoints in retailedge.expense_register.
