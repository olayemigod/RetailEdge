from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property


PERMLEVEL = 0
CASHIER_ROLES = ("RetailEdgeCashier",)
ACCOUNT_PERMISSIONS = (
	"read",
	"select",
)
POS_SHIFT_PERMISSIONS = (
	"read",
	"create",
	"write",
	"submit",
)
POS_SHIFT_DOCTYPES = (
	"POS Opening Shift",
	"POS Closing Shift",
)


def _has_custom_permission(doctype: str, role: str) -> bool:
	return bool(
		frappe.db.exists(
			"Custom DocPerm",
			{
				"parent": doctype,
				"role": role,
				"permlevel": PERMLEVEL,
			},
		)
	)


def _ensure_permission_row(doctype: str, role: str) -> None:
	if not _has_custom_permission(doctype, role):
		add_permission(doctype, role, PERMLEVEL)


def _grant(doctype: str, role: str, properties: tuple[str, ...]) -> None:
	if not frappe.db.exists("DocType", doctype):
		return
	_ensure_permission_row(doctype, role)
	for property_name in properties:
		update_permission_property(doctype, role, PERMLEVEL, property_name, 1)


def execute():
	"""Bridge the canonical RetailEdge cashier to the installed POS runtime."""
	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue

		_grant("Account", role, ACCOUNT_PERMISSIONS)
		for doctype in POS_SHIFT_DOCTYPES:
			_grant(doctype, role, POS_SHIFT_PERMISSIONS)

	frappe.clear_cache()
