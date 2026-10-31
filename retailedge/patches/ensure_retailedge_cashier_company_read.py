from __future__ import annotations

import frappe
from frappe.permissions import add_permission, update_permission_property

from retailedge.patches.ensure_retailedge_cashier_operational_permissions import (
	execute as ensure_cashier_operational_permissions,
)


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
	"""Reconcile the cashier Company read and governed operational baseline.

	This callable is retained as the recurring post-migrate cashier permission
	reconciliation hook. Frappe runs migration patches before ``after_migrate``;
	on a clean install the RetailEdge roles can therefore be created only after
	the one-time operational permission patch was already consumed. Re-running
	the idempotent operational baseline here ensures clean installs and upgrades
	converge after role setup without granting generic accounting authority.

	Existing User Permissions and RetailEdge Branch Assignments continue to narrow
	operational context where configured. The delegated baseline remains bounded
	to the documented cashier master reads and selling-document permissions.
	"""
	if frappe.db.exists("DocType", DOCTYPE):
		for role in CASHIER_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			if not _has_custom_permission(role):
				add_permission(DOCTYPE, role, PERMLEVEL)
			update_permission_property(DOCTYPE, role, PERMLEVEL, "read", 1)
			update_permission_property(DOCTYPE, role, PERMLEVEL, "select", 1)

	# This function is already wired immediately after ensure_retailedge_roles in
	# hooks.after_migrate, so the delegated repair always sees the canonical roles.
	ensure_cashier_operational_permissions()
