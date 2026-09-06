from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	has_field,
)
from retailedge.branch_profile import get_branch_profile_defaults
from retailedge.operating_context import get_operational_branch_scope

MAX_FILTER_RESULTS = 20
PROFILE_WAREHOUSE_FIELDS = (
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def branch_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict[str, Any] | str | None,
):
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		return []
	_assert_company_read(company)

	query_filters: list[list[Any]] = [["Branch", "name", "like", f"%{txt or ''}%"]]
	if has_field("Branch", "company"):
		query_filters.append(["Branch", "company", "=", company])

	user = frappe.session.user
	scope = get_operational_branch_scope(company, user=user)
	if scope.get("restricted"):
		allowed = list(scope.get("allowed_branches") or [])
		if not allowed:
			return []
		query_filters.append(["Branch", "name", "in", allowed])

	return frappe.get_list(
		"Branch",
		filters=query_filters,
		fields=["name"],
		limit_start=max(int(start or 0), 0),
		limit_page_length=_page_len(page_len),
		order_by="name asc",
		as_list=True,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def warehouse_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict[str, Any] | str | None,
):
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if not company:
		return []
	_assert_company_read(company)

	user = frappe.session.user
	scope = get_operational_branch_scope(company, user=user)
	restricted = bool(scope.get("restricted"))
	allowed_branches = list(scope.get("allowed_branches") or [])
	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	query_filters: list[list[Any]] = [
		["Warehouse", "company", "=", company],
		["Warehouse", "is_group", "=", 0],
		["Warehouse", "name", "like", f"%{txt or ''}%"],
	]

	if branch:
		if restricted and branch not in allowed_branches:
			frappe.throw(
				_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
				frappe.PermissionError,
			)
		if branch_field:
			query_filters.append(["Warehouse", branch_field, "=", branch])
		else:
			allowed_names = _profile_warehouses(company=company, branch=branch, user=user)
			if not allowed_names:
				return []
			query_filters.append(["Warehouse", "name", "in", sorted(allowed_names)])
	elif restricted:
		if not allowed_branches:
			return []
		if branch_field:
			query_filters.append(["Warehouse", branch_field, "in", allowed_branches])
		else:
			allowed_names: set[str] = set()
			for allowed_branch in allowed_branches:
				allowed_names.update(
					_profile_warehouses(company=company, branch=allowed_branch, user=user)
				)
			if not allowed_names:
				return []
			query_filters.append(["Warehouse", "name", "in", sorted(allowed_names)])

	return frappe.get_list(
		"Warehouse",
		filters=query_filters,
		fields=["name"],
		limit_start=max(int(start or 0), 0),
		limit_page_length=_page_len(page_len),
		order_by="name asc",
		as_list=True,
	)


def _profile_warehouses(*, company: str, branch: str, user: str) -> set[str]:
	defaults = get_branch_profile_defaults(company=company, branch=branch, user=user)
	return {
		str(defaults.get(fieldname)).strip()
		for fieldname in PROFILE_WAREHOUSE_FIELDS
		if defaults.get(fieldname)
	}


def _assert_company_read(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)


def _coerce_filters(filters: dict[str, Any] | str | None) -> dict[str, Any]:
	if not filters:
		return {}
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return dict(filters or {})


def _page_len(value: Any) -> int:
	try:
		resolved = int(value or MAX_FILTER_RESULTS)
	except (TypeError, ValueError):
		resolved = MAX_FILTER_RESULTS
	return max(1, min(resolved, MAX_FILTER_RESULTS))
