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

MONETARY_SNAPSHOT_FIELDS = (
	"shift_opening_cash_amount",
	"shift_cash_sales_amount",
	"prior_shift_expense_amount",
	"available_shift_cash_before_expense",
	"available_shift_cash_after_expense",
)


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
	"""Refresh derived Cashier Expense cash context without rewriting history.

	Draft expenses may recompute their full cash snapshot because they are still
	editable. Submitted/cancelled expenses preserve the monetary snapshot captured
	at the time of entry; only diagnostic source/warning metadata may be refreshed.
	This avoids making historical cash availability drift as later shift sales or
	expenses are recorded, and never touches accounting/posting/status fields.
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

	values = {
		"cash_balance_source": snapshot.get("source"),
		# Write this unconditionally so a stale warning can clear when the resolver
		# now proves the cash context safely.
		"cash_control_message": snapshot.get("message"),
	}
	monetary_snapshot_preserved = int(getattr(doc, "docstatus", 0) or 0) != 0
	if not monetary_snapshot_preserved:
		available_before = flt(snapshot.get("available_before", 0))
		values.update(
			{
				"shift_opening_cash_amount": flt(snapshot.get("opening_cash", 0)),
				"shift_cash_sales_amount": flt(snapshot.get("cash_sales", 0)),
				"prior_shift_expense_amount": flt(snapshot.get("prior_expenses", 0)),
				"available_shift_cash_before_expense": available_before,
				"available_shift_cash_after_expense": available_before - flt(getattr(doc, "amount", 0)),
			}
		)

	frappe.db.set_value(
		"RetailEdge Cashier Expense",
		doc.name,
		values,
		update_modified=False,
	)

	result = {
		"expense_name": doc.name,
		"monetary_snapshot_preserved": monetary_snapshot_preserved,
		**values,
	}
	if monetary_snapshot_preserved:
		for fieldname in MONETARY_SNAPSHOT_FIELDS:
			result[fieldname] = flt(getattr(doc, fieldname, 0))
	return result
