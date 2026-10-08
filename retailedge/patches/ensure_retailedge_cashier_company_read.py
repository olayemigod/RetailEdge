from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property


DOCTYPE = "Company"
PERMLEVEL = 0
CASHIER_ROLES = (
	"RetailEdgeCashier",
	"RetailEdge Cashier",
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
	"""Give cashier roles only the Company visibility required for operations.

	Cashier workflows resolve and validate an operating Company before they can
	load Branch/POS context or record till activity. Keep that validation on normal
	Frappe permissions instead of bypassing Company access. Existing User
	Permissions and RetailEdge Branch Assignments continue to narrow operational
	context where configured.

	This patch grants only Company read/select. It does not grant Company writes,
	Journal Entry authority, accounting roles, or any submitted-document mutation.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		if not _has_custom_permission(role):
			add_permission(DOCTYPE, role, PERMLEVEL)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "read", 1)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "select", 1)
