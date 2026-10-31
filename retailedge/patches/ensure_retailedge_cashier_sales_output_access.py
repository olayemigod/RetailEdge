from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property


PERMLEVEL = 0
CASHIER_ROLES = (
	"RetailEdgeCashier",
	"RetailEdge Cashier",
)
OUTPUT_PAGE = "document-output-sharing"


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


def _grant_sales_invoice_print(role: str) -> None:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	_ensure_permission_row("Sales Invoice", role)
	update_permission_property("Sales Invoice", role, PERMLEVEL, "print", 1)


def _ensure_output_page_role(role: str) -> None:
	if not frappe.db.exists("Page", OUTPUT_PAGE):
		return
	page = frappe.get_doc("Page", OUTPUT_PAGE)
	if any(str(row.role or "").strip() == role for row in page.roles or []):
		return
	page.append("roles", {"role": role})
	page.flags.ignore_permissions = True
	page.flags.do_not_update_json = True
	page.save(ignore_permissions=True)
	page.clear_cache()


def execute():
	"""Reconcile cashier receipt/output access without bypassing Frappe permissions."""
	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		_grant_sales_invoice_print(role)
		_ensure_output_page_role(role)

	frappe.clear_cache()
