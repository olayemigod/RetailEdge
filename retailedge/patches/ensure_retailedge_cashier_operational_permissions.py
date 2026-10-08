from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property


PERMLEVEL = 0
CASHIER_ROLES = (
	"RetailEdgeCashier",
	"RetailEdge Cashier",
)

READ_SELECT_DOCTYPES = (
	"Branch",
	"POS Profile",
	"Warehouse",
	"Mode of Payment",
	"Customer",
	"Item",
	"UOM",
	"Price List",
	"Item Price",
)

SALES_INVOICE_PERMISSIONS = (
	"read",
	"create",
	"write",
	"submit",
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
	"""Grant the RetailEdge cashier only the native permissions required for daily cashier operations."""
	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue

		for doctype in READ_SELECT_DOCTYPES:
			_grant(doctype, role, ("read", "select"))

		_grant("Sales Invoice", role, SALES_INVOICE_PERMISSIONS)
