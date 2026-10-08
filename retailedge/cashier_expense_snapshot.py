from __future__ import annotations

import frappe
from frappe.utils import flt

from retailedge.cashier_context import get_shift_cash_snapshot


SNAPSHOT_REFRESH_ROLES = {
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdge Branch Manager",
	"RetailEdge Auditor",
	"RetailEdgeManager",
	"RetailEdgeBranchManager",
	"RetailEdgeAuditor",
}


def _can_refresh_cash_snapshot(doc, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if set(frappe.get_roles(user)).intersection(SNAPSHOT_REFRESH_ROLES):
		return True
	try:
		return bool(doc.has_permission("write"))
	except Exception:
		return False


def refresh_cashier_expense_cash_snapshot(expense_name: str) -> dict[str, object]:
	"""Recompute only the derived shift-cash snapshot stored on a Cashier Expense.

	This deliberately avoids ``doc.save()`` so a submitted/posted expense and its
	accounting truth are not mutated through the normal document lifecycle. Only
	operational snapshot fields are updated.
	"""
	if not expense_name:
		frappe.throw("Cashier Expense is required.")

	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	if not _can_refresh_cash_snapshot(doc):
		frappe.throw(
			"You do not have permission to refresh this cashier expense cash snapshot.",
			frappe.PermissionError,
		)

	snapshot = get_shift_cash_snapshot(
		opening_shift=getattr(doc, "linked_pos_opening_shift", None),
		company=getattr(doc, "company", None),
		pos_profile=getattr(doc, "pos_profile", None),
		user=getattr(doc, "cashier", None),
		expense_name=doc.name,
	)
	available_before = flt(snapshot.get("available_before", 0))
	values = {
		"shift_opening_cash_amount": flt(snapshot.get("opening_cash", 0)),
		"shift_cash_sales_amount": flt(snapshot.get("cash_sales", 0)),
		"prior_shift_expense_amount": flt(snapshot.get("prior_expenses", 0)),
		"available_shift_cash_before_expense": available_before,
		"available_shift_cash_after_expense": available_before - flt(getattr(doc, "amount", 0)),
		"cash_balance_source": snapshot.get("source"),
		# Write this unconditionally so a previously stored warning is cleared when
		# the resolver now proves the cash position safely.
		"cash_control_message": snapshot.get("message"),
	}
	frappe.db.set_value(
		"RetailEdge Cashier Expense",
		doc.name,
		values,
		update_modified=False,
	)
	return {
		"expense_name": doc.name,
		**values,
	}
