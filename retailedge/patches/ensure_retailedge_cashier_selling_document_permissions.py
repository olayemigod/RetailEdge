from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property


PERMLEVEL = 0
CASHIER_ROLES = (
	"RetailEdgeCashier",
	"RetailEdge Cashier",
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


def _ensure_permission_row(doctype: str, role: str) -> None:
	if frappe.db.exists(
		"Custom DocPerm",
		{
			"parent": doctype,
			"role": role,
			"permlevel": PERMLEVEL,
		},
	):
		return
	add_permission(doctype, role, PERMLEVEL)


def execute():
	"""Reconcile the canonical cashier role with the governed Professional Selling chain."""
	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		for doctype in SELLING_DOCUMENTS:
			if not frappe.db.exists("DocType", doctype):
				continue
			_ensure_permission_row(doctype, role)
			for property_name in SELLING_DOCUMENT_PERMISSIONS:
				update_permission_property(doctype, role, PERMLEVEL, property_name, 1)

	frappe.clear_cache()
