from __future__ import annotations

import frappe


RETAILEDGE_ACCESS_ROLES = frozenset(
	{
		"System Manager",
		"Accounts Manager",
		"Accounts User",
		"Sales Manager",
		"Sales User",
		"Stock Manager",
		"Stock User",
		"RetailEdgeCashier",
		"RetailEdgeManager",
		"RetailEdgeBranchManager",
		"RetailEdgeAuditor",
	}
)


@frappe.whitelist()
def has_app_permission() -> bool:
	"""Return whether the current Desk user may open the RetailEdge product surface."""
	user = frappe.session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True

	try:
		if RETAILEDGE_ACCESS_ROLES.intersection(frappe.get_roles(user)):
			return True
	except Exception:
		return False

	for doctype in (
		"RetailEdge Settings",
		"RetailEdge Branch Profile",
		"RetailEdge Cashier Expense",
	):
		try:
			if frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, ptype="read"):
				return True
		except Exception:
			continue
	return False
