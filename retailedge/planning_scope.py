from __future__ import annotations

import frappe
from frappe import _

from retailedge.branch_context import (
	get_user_allowed_branches,
	user_has_global_branch_access,
	validate_user_branch_access,
)


def resolve_planning_branch_scope(company: str, branch: str | None = None, *, user: str | None = None) -> str:
	"""Resolve a planning Branch without allowing restricted users to fall back to company-wide scope.

	RetailEdge treats an empty configured branch-access list as unrestricted. For users who do have
	explicit branch restrictions, a blank Branch is safe only when exactly one Branch is allowed; that
	Branch is selected automatically. Users allowed multiple branches must choose one explicitly.
	"""
	user = user or frappe.session.user
	resolved = str(branch or "").strip()
	if resolved:
		validate_user_branch_access(resolved, user=user, company=company, throw=True)
		return resolved

	if user_has_global_branch_access(user=user):
		return ""

	allowed_info = get_user_allowed_branches(user=user, company=company)
	allowed = [str(value).strip() for value in allowed_info.get("branches") or [] if str(value).strip()]
	if not allowed:
		return ""
	if len(allowed) == 1:
		return allowed[0]

	frappe.throw(
		_("Select a Branch within your allowed access before opening Forecasting & Planning for Company {0}.").format(company),
		frappe.PermissionError,
	)
	return ""
