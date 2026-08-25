from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import resolve_branch_from_warehouse, validate_user_branch_access
from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults
from retailedge.operating_context import get_effective_operating_context


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
	"""Resolve one guided-entry Branch/Stock Location pair without broad data loading.

	An explicitly selected Stock Location remains authoritative. When neither Branch
	nor Stock Location is supplied, the session Operating Branch guides the new
	draft. Existing documents and explicit selections are never overwritten by the
	operating context.
	"""
	user = frappe.session.user
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	warehouse = str(warehouse or "").strip()
	preference = str(preference or "default").strip().lower()

	if not company or (not branch and not warehouse):
		operating = get_effective_operating_context(company=company)
		company = company or str(operating.get("company") or "").strip()
		if not branch and not warehouse:
			branch = str(operating.get("branch") or "").strip()

	if not company:
		frappe.throw(_("Company is required to resolve Branch and Stock Location."))
	_assert_read_permission("Company", company)

	if warehouse:
		_assert_read_permission("Warehouse", warehouse)
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))

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
					_("Stock Location {0} is not configured for Branch {1}.").format(warehouse, branch)
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
		"source": "operating_context" if branch and not warehouse else ("branch_profile" if candidate else "branch"),
	}


def _assert_read_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)
