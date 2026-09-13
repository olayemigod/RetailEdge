from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import BRANCH_FIELD_CANDIDATES, get_first_existing_field, has_field, resolve_branch_from_warehouse
from retailedge.branch_profile import (
	get_branch_profile,
	get_branch_profile_defaults,
	get_enabled_branch_profiles,
	get_exact_branch_profile,
)
from retailedge.operating_context import (
	get_effective_operating_context,
	get_operational_branch_scope,
	resolve_operational_branch,
)


WAREHOUSE_PREFERENCES: dict[str, tuple[str, ...]] = {
	"sales": ("default_source_warehouse", "default_warehouse", "default_target_warehouse"),
	"purchase": ("default_target_warehouse", "default_warehouse", "default_source_warehouse"),
	"source": ("default_source_warehouse", "default_warehouse"),
	"target": ("default_target_warehouse", "default_warehouse"),
	"default": ("default_warehouse", "default_source_warehouse", "default_target_warehouse"),
}



def get_guided_branch_names(company: str, *, user: str | None = None) -> list[str]:
	"""Return enabled Branch Setup names permitted in one Company.

	Branch Setup is the product-level Company↔Branch binding on ERPNext v16 sites.
	Operational scope remains authoritative for restricted users.
	"""
	company = str(company or "").strip()
	if not company:
		return []
	user = user or frappe.session.user
	configured = {
		str(row.get("branch") or "").strip()
		for row in get_enabled_branch_profiles(company=company)
		if str(row.get("branch") or "").strip()
	}
	if not configured:
		return []

	scope = get_operational_branch_scope(company, user=user)
	if scope.get("restricted"):
		configured &= {
			str(branch or "").strip()
			for branch in scope.get("allowed_branches") or []
			if str(branch or "").strip()
		}
	return sorted(configured)


def get_guided_branch_search_filters(company: str, *, user: str | None = None) -> dict[str, Any]:
	company = str(company or "").strip()
	if not company:
		return {"name": "__never__"}
	branches = get_guided_branch_names(company, user=user)
	filters: dict[str, Any] = {
		"name": ["in", branches] if branches else "__never__",
	}
	if has_field("Branch", "company"):
		filters["company"] = company
	return filters


def resolve_guided_branch(
	company: str,
	branch: str = "",
	*,
	user: str | None = None,
	allow_blank_unrestricted: bool = True,
) -> str:
	"""Resolve a guided-entry Branch and require enabled Branch Setup when selected."""
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	user = user or frappe.session.user
	if not company:
		frappe.throw(_("Company is required before selecting a Branch."))

	branches = get_guided_branch_names(company, user=user)
	scope = get_operational_branch_scope(company, user=user)
	if branch:
		if branch not in branches:
			frappe.throw(
				_("Branch {0} is not enabled in Branch Setup for Company {1}.").format(branch, company)
			)
		return str(
			resolve_operational_branch(company, branch, user=user).get("branch") or ""
		).strip()

	if scope.get("restricted"):
		if len(branches) == 1:
			return branches[0]
		if not branches:
			frappe.throw(
				_("No enabled Branch Setup is available for your access in Company {0}.").format(company),
				frappe.PermissionError,
			)
		return ""

	return "" if allow_blank_unrestricted else (branches[0] if len(branches) == 1 else "")


def get_guided_warehouse_search_filters(
	company: str,
	branch: str = "",
	*,
	user: str | None = None,
) -> dict[str, Any] | None:
	"""Return bounded Stock Location filters for the selected guided Branch."""
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	user = user or frappe.session.user
	if not company:
		return None

	filters: dict[str, Any] = {"is_group": 0}
	if has_field("Warehouse", "disabled"):
		filters["disabled"] = 0
	if has_field("Warehouse", "company"):
		filters["company"] = company

	configured_branches = get_guided_branch_names(company, user=user)
	if not branch:
		# Once Branch Setup exists, selecting a Branch is required before choosing a
		# Stock Location. Company-wide unrestricted operation remains compatible on
		# sites with no Branch Setup.
		return None if configured_branches else filters

	branch = resolve_guided_branch(company, branch, user=user)
	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	if branch_field:
		filters[branch_field] = branch
		return filters

	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		return None
	warehouses = _unique(
		[
			getattr(profile, "default_source_warehouse", None),
			getattr(profile, "default_warehouse", None),
			getattr(profile, "default_target_warehouse", None),
			getattr(profile, "default_returns_warehouse", None),
		]
	)
	if not warehouses:
		return None
	filters["name"] = ["in", warehouses]
	return filters


def validate_guided_branch_warehouse(
	*,
	company: str,
	branch: str,
	warehouse: str,
	user: str | None = None,
) -> None:
	"""Validate one explicit Branch/Stock Location combination server-side."""
	company = str(company or "").strip()
	branch = resolve_guided_branch(company, branch, user=user)
	warehouse = str(warehouse or "").strip()
	if not warehouse:
		return
	user = user or frappe.session.user
	_assert_read_permission("Warehouse", warehouse)
	warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "").strip()
	if warehouse_company and warehouse_company != company:
		frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))

	resolved = resolve_branch_from_warehouse(warehouse, company=company)
	warehouse_branch = str(resolved.get("branch") or "").strip()
	if warehouse_branch:
		if warehouse_branch != branch:
			frappe.throw(
				_("Stock Location {0} belongs to Branch {1}, not Branch {2}.").format(
					warehouse, warehouse_branch, branch
				)
			)
		return

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


def _unique(values: list[Any]) -> list[str]:
	result: list[str] = []
	seen: set[str] = set()
	for value in values:
		value = str(value or "").strip()
		if value and value not in seen:
			seen.add(value)
			result.append(value)
	return result


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
	used_operating_context = False

	if not company or (not branch and not warehouse):
		operating = get_effective_operating_context(company=company)
		company = company or str(operating.get("company") or "").strip()
		if not branch and not warehouse:
			branch = str(operating.get("branch") or "").strip()
			used_operating_context = bool(branch)

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
			resolved_branch = resolve_guided_branch(
				company,
				resolved_branch,
				user=user,
			)
			if branch and branch != resolved_branch:
				frappe.throw(
					_("Stock Location {0} does not belong to Branch {1}.").format(warehouse, branch)
				)
			return {
				"company": company,
				"branch": resolved_branch,
				"warehouse": warehouse,
				"source": "warehouse",
			}

		if branch:
			branch = resolve_guided_branch(company, branch, user=user)
		else:
			scope = get_operational_branch_scope(company, user=user)
			if scope["restricted"]:
				branch = resolve_operational_branch(company, "", user=user)["branch"]

		if branch:
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

	branch = resolve_guided_branch(company, branch, user=user)
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
		"source": "operating_context"
		if used_operating_context
		else ("branch_profile" if candidate else "branch"),
	}


def _assert_read_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)
