from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import resolve_branch_from_warehouse, validate_user_branch_access
from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults


WAREHOUSE_PREFERENCES: dict[str, tuple[str, ...]] = {
	"sales": ("default_source_warehouse", "default_warehouse", "default_target_warehouse"),
	"purchase": ("default_target_warehouse", "default_warehouse", "default_source_warehouse"),
	"source": ("default_source_warehouse", "default_warehouse"),
	"target": ("default_target_warehouse", "default_warehouse"),
	"default": ("default_warehouse", "default_source_warehouse", "default_target_warehouse"),
}


@frappe.whitelist()
def resolve_branch_warehouse_selection(
	company: str,
	branch: str = "",
	warehouse: str = "",
	preference: str = "default",
) -> dict[str, Any]:
	"""Resolve one guided-entry Branch/Warehouse pair without broad data loading.

	Warehouse is authoritative when explicitly selected: its configured branch is
	resolved and returned. When Branch is selected without Warehouse, only the
	branch profile's preferred warehouse is considered; we deliberately do not
	scan or preload all warehouses.
	"""
	user = frappe.session.user
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	warehouse = str(warehouse or "").strip()
	preference = str(preference or "default").strip().lower()

	if not company:
		frappe.throw(_("Company is required to resolve Branch and Warehouse."))
	_assert_read_permission("Company", company)

	if warehouse:
		_assert_read_permission("Warehouse", warehouse)
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))

		resolved = resolve_branch_from_warehouse(warehouse, company=company)
		resolved_branch = str(resolved.get("branch") or "").strip()
		if not resolved_branch:
			profile = get_branch_profile(
				company=company,
				user=user,
				warehouse=warehouse,
				active_only=True,
			)
			resolved_branch = str(getattr(profile, "branch", None) or "").strip() if profile else ""

		if resolved_branch:
			validate_user_branch_access(resolved_branch, user=user, company=company, throw=True)
			return {
				"company": company,
				"branch": resolved_branch,
				"warehouse": warehouse,
				"source": "warehouse",
			}

		if branch:
			validate_user_branch_access(branch, user=user, company=company, throw=True)
			profile = get_branch_profile(
				company=company,
				branch=branch,
				user=user,
				warehouse=warehouse,
				active_only=True,
			)
			if not profile:
				frappe.throw(
					_("Warehouse {0} is not configured for Branch {1}.").format(warehouse, branch)
				)
		return {
			"company": company,
			"branch": branch,
			"warehouse": warehouse,
			"source": "warehouse_without_branch_field",
		}

	if not branch:
		return {"company": company, "branch": "", "warehouse": "", "source": "empty"}

	validate_user_branch_access(branch, user=user, company=company, throw=True)
	defaults = get_branch_profile_defaults(company=company, branch=branch, user=user)
	candidate = ""
	for fieldname in WAREHOUSE_PREFERENCES.get(preference, WAREHOUSE_PREFERENCES["default"]):
		value = str(defaults.get(fieldname) or "").strip()
		if value:
			candidate = value
			break

	if candidate:
		_assert_read_permission("Warehouse", candidate)
		warehouse_company = frappe.db.get_value("Warehouse", candidate, "company")
		if warehouse_company and warehouse_company != company:
			candidate = ""

	return {
		"company": company,
		"branch": branch,
		"warehouse": candidate,
		"source": "branch_profile" if candidate else "branch",
	}


def _assert_read_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)
