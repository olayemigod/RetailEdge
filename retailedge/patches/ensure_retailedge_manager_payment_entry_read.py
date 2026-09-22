from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property

MANAGER_ROLES = (
	"RetailEdgeManager",
	"RetailEdge Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Branch Manager",
)
DOCTYPE = "Payment Entry"
PERMLEVEL = 0


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
	"""Give RetailEdge managers read-only Payment Entry visibility.

	Payment & Settlement Analysis and Payment Management both expose ERPNext
	Payment Entry information. The product must not bypass ERPNext document
	permission, so manager roles receive only the minimum read permission here.
	Write/create/submit/cancel/amend authority remains unchanged.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	for role in MANAGER_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		if not _has_custom_permission(role):
			add_permission(DOCTYPE, role, PERMLEVEL)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "read", 1)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "select", 1)
		update_permission_property(DOCTYPE, role, PERMLEVEL, "report", 1)
