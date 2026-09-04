from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_profile import get_enabled_branch_profiles
from retailedge.operating_context import get_allowed_operating_branches, get_operational_branch_scope


NO_BRANCH_SCOPE_SENTINEL = "__never__"
DAILY_SALES_AUDIT_CONTEXT_SELECTORS = (
	"branch",
	"pos_profile",
	"cashier",
	"pos_opening_shift",
	"pos_closing_shift",
)


def get_daily_sales_audit_reader() -> str:
	return getattr(getattr(frappe, "session", None), "user", "Administrator")


def get_daily_sales_audit_branch_scope(company: str | None, *, user: str | None = None) -> dict[str, Any]:
	company = _clean(company)
	if not company:
		return {
			"company": "",
			"restricted": False,
			"allowed_branches": [],
			"source": "no_company",
		}
	return get_operational_branch_scope(company, user=user or get_daily_sales_audit_reader())


def get_daily_sales_audit_branch_options(company: str | None, *, user: str | None = None) -> list[str]:
	company = _clean(company)
	if not company:
		return []
	return list(get_allowed_operating_branches(company, user=user or get_daily_sales_audit_reader()))


def get_daily_sales_audit_allowed_pos_profiles(
	company: str | None,
	*,
	branch: str | None = None,
	user: str | None = None,
) -> list[str]:
	"""Return Branch-setup POS Profiles visible to the current operational reader."""
	company = _clean(company)
	branch = _clean(branch)
	if not company:
		return []
	reader = user or get_daily_sales_audit_reader()
	scope = get_daily_sales_audit_branch_scope(company, user=reader)
	allowed = list(scope.get("allowed_branches") or [])
	if branch:
		if scope.get("restricted") and branch not in allowed:
			_throw_branch_denied(branch)
		_assert_branch_visible(company, branch, user=reader)
		allowed_branch_set = {branch}
	elif scope.get("restricted"):
		allowed_branch_set = set(allowed)
	else:
		# Unrestricted blank-Branch reads keep legacy company-wide behaviour and
		# should not be narrowed only to configured default POS Profiles.
		return []

	if not allowed_branch_set:
		return []
	rows = get_enabled_branch_profiles(company=company)
	return list(
		dict.fromkeys(
			row.get("default_pos_profile")
			for row in rows
			if row.get("branch") in allowed_branch_set and row.get("default_pos_profile")
		)
	)


def apply_daily_sales_audit_query_branch_scope(
	doctype: str,
	filters: dict[str, Any] | None,
	*,
	branch_field: str | None,
	pos_profile_scope_field: str | None = None,
	user: str | None = None,
) -> dict[str, Any] | None:
	"""Return the Branch/POS Profile portion of a Daily Sales Audit read query.

	A selected cashier is deliberately ignored for authorization. The current
	reader is the access principal; cashier remains only a business filter.
	"""
	filters = dict(filters or {})
	company = _clean(filters.get("company"))
	branch = _clean(filters.get("branch"))
	selected_profile = _clean(filters.get("pos_profile"))
	reader = user or get_daily_sales_audit_reader()

	if not company:
		# Operational option/search reads must wait for Company context instead of
		# silently becoming cross-company queries.
		return None

	scope = get_daily_sales_audit_branch_scope(company, user=reader)
	allowed = list(scope.get("allowed_branches") or [])
	if branch:
		if scope.get("restricted") and branch not in allowed:
			_throw_branch_denied(branch)
		_assert_branch_visible(company, branch, user=reader)
		if branch_field:
			return {branch_field: branch}
		if pos_profile_scope_field:
			profiles = get_daily_sales_audit_allowed_pos_profiles(company, branch=branch, user=reader)
			return _profile_scope_filter(pos_profile_scope_field, profiles, selected_profile=selected_profile)
		return None

	if not scope.get("restricted"):
		return {}
	if branch_field:
		if not allowed:
			return {branch_field: NO_BRANCH_SCOPE_SENTINEL}
		if len(allowed) == 1:
			return {branch_field: allowed[0]}
		return {branch_field: ["in", allowed]}
	if pos_profile_scope_field:
		profiles = get_daily_sales_audit_allowed_pos_profiles(company, user=reader)
		return _profile_scope_filter(pos_profile_scope_field, profiles, selected_profile=selected_profile)
	return None


def validate_daily_sales_audit_read_context(
	context: dict[str, Any] | None,
	*,
	selection: dict[str, Any] | None = None,
	require_branch: bool = False,
	user: str | None = None,
) -> dict[str, Any]:
	"""Revalidate resolved Daily Sales Audit context against the current reader.

	Business context may be inferred from a selected cashier, POS Profile, or
	shift, but the inferred Branch never becomes authority by itself.
	"""
	result = dict(context or {})
	selection = dict(selection or {})
	company = _clean(result.get("company"))
	branch = _clean(result.get("branch"))
	reader = user or get_daily_sales_audit_reader()

	if branch and not company:
		frappe.throw(_("Company is required before Branch can be used for Daily Sales Audit."))
	if not company:
		return result

	scope = get_daily_sales_audit_branch_scope(company, user=reader)
	allowed = list(scope.get("allowed_branches") or [])

	if branch:
		if scope.get("restricted") and branch not in allowed:
			_throw_branch_denied(branch)
		_assert_branch_visible(company, branch, user=reader)
		# A restricted multi-Branch reader must not get an arbitrary Branch merely
		# from their own fallback/default when no business context was selected.
		if (
			require_branch
			and scope.get("restricted")
			and len(allowed) > 1
			and not any(_clean(selection.get(key)) for key in DAILY_SALES_AUDIT_CONTEXT_SELECTORS)
		):
			frappe.throw(_("Choose a Branch or operational context before continuing Daily Sales Audit."))
		result["branch"] = branch
		return result

	if not scope.get("restricted"):
		return result
	if not allowed:
		if require_branch:
			frappe.throw(
				_("Your Branch operating access is not active for Company {0}.").format(company),
				frappe.PermissionError,
			)
		return result
	if len(allowed) == 1:
		result["branch"] = allowed[0]
		result.setdefault("source_map", {})["branch"] = "Operational Branch Scope"
		return result
	if require_branch:
		frappe.throw(_("Choose a Branch or operational context before continuing Daily Sales Audit."))
	return result


def _assert_branch_visible(company: str, branch: str, *, user: str) -> None:
	if branch in get_daily_sales_audit_branch_options(company, user=user):
		return
	_throw_branch_denied(branch)


def _profile_scope_filter(
	fieldname: str,
	profiles: list[str],
	*,
	selected_profile: str = "",
) -> dict[str, Any]:
	if selected_profile:
		if selected_profile not in profiles:
			frappe.throw(
				_("POS Profile {0} is not available in your active Branch scope.").format(selected_profile),
				frappe.PermissionError,
			)
		return {fieldname: selected_profile}
	if not profiles:
		return {fieldname: NO_BRANCH_SCOPE_SENTINEL}
	if len(profiles) == 1:
		return {fieldname: profiles[0]}
	return {fieldname: ["in", profiles]}


def _throw_branch_denied(branch: str) -> None:
	frappe.throw(
		_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
		frappe.PermissionError,
	)


def _clean(value: Any) -> str:
	return str(value or "").strip()
