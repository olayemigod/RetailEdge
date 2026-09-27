from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property


DOCTYPE = "Company"
PERMLEVEL = 0
STOCK_MANAGER_ROLES = (
	"Stock Manager",
	"RetailEdge Stock Manager",
	"RetailEdgeStockManager",
)


def _has_custom_permission(role: str) -> bool:
	return bool(
		frappe.db.exists(
			"Custom DocPerm",
			{
				"parent": DOCTYPE,
				"role": role,
				"permlevel": PERMLEVEL,
			},
		)
	)


def execute():
	"""Give stock-manager roles the minimum Company visibility required by RetailEdge.

	ERPNext v16 gives Stock Reconciliation create/submit authority to Stock
	Manager, while Company read is granted to Stock User. RetailEdge's governed
	Stock Adjustment page must validate the selected operating Company instead of
	bypassing Company permission, so stock-manager roles receive only Company
	read/select here. No Company write/create/delete authority is granted.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	for role in STOCK_MANAGER_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		if not _has_custom_permission(role):
			add_permission(DOCTYPE, role, PERMLEVEL)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "read", 1)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "select", 1)
