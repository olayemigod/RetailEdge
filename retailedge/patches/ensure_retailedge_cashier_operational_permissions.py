from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property

PERMLEVEL = 0
CASHIER_ROLES = ("RetailEdgeCashier",)

# ERPNext get_party_account() checks Select (when no Account Read role is
# present) while calculating a Sales Invoice. A cashier may select the
# receivable account configured for an authorised Company, but must not gain
# general ledger/Account record read or accounting mutation permissions.
SELECT_ONLY_DOCTYPES = (
	"Account",
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

SELLING_DOCUMENTS = (
	"Quotation",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
)

SELLING_DOCUMENT_PERMISSIONS = (
	"read",
	"create",
	"write",
	"submit",
	"print",
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


def _ensure_permission_row(doctype: str, role: str, *, initial_permission: str = "read") -> None:
	if not _has_custom_permission(doctype, role):
		# Frappe add_permission defaults to Read. Explicitly create Select-only
		# rows without briefly granting Account document access.
		add_permission(doctype, role, PERMLEVEL, ptype=initial_permission)


def _grant(doctype: str, role: str, properties: tuple[str, ...]) -> None:
	if not frappe.db.exists("DocType", doctype):
		return
	select_only = properties == ("select",)
	_ensure_permission_row(doctype, role, initial_permission="select" if select_only else "read")
	for property_name in properties:
		update_permission_property(doctype, role, PERMLEVEL, property_name, 1)
	if select_only:
		# Reconcile older sites where add_permission() created Account Read = 1.
		# Only the RetailEdgeCashier DocPerm is changed. Other native roles and
		# user-level Account permissions remain under normal Frappe governance.
		update_permission_property(doctype, role, PERMLEVEL, "read", 0)


def execute():
	"""Grant the RetailEdge cashier the native permissions required for governed selling work."""
	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue

		for doctype in READ_SELECT_DOCTYPES:
			_grant(doctype, role, ("read", "select"))

		for doctype in SELECT_ONLY_DOCTYPES:
			_grant(doctype, role, ("select",))

		for doctype in SELLING_DOCUMENTS:
			_grant(doctype, role, SELLING_DOCUMENT_PERMISSIONS)
