from __future__ import annotations

from typing import Any

import frappe

MAX_CANDIDATES = 100
MAX_PAGE_LENGTH = 50


def _coerce_filters(filters: dict[str, Any] | str | None) -> dict[str, Any]:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return dict(filters or {})


def _is_assignable_user(
	user: str,
	*,
	company: str,
	branch: str,
	require_global_scope: bool,
	require_owner_scope: bool,
) -> bool:
	from retailedge.action_follow_up import _has_action_center_role, _has_owner_financial_access
	from retailedge.branch_context import user_has_global_branch_access, validate_user_branch_access

	if not user or not _has_action_center_role(user):
		return False
	if require_owner_scope and not _has_owner_financial_access(user, company=company, branch=branch):
		return False
	if require_global_scope:
		return bool(user_has_global_branch_access(user=user))
	if branch:
		return bool(
			validate_user_branch_access(
				branch,
				user=user,
				company=company or None,
				throw=False,
			).get("allowed")
		)
	return True


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_assignable_users(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict[str, Any] | str | None = None,
):
	"""Return only enabled users who can validly own the current control follow-up."""
	from retailedge.action_follow_up import _assert_action_center_role

	_assert_action_center_role()
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	require_global_scope = bool(int(filters.get("require_global_scope") or 0))
	# Existing UI already identifies company-level R9 warnings through the global-scope flag.
	# Treat that flag as owner-financial scope too, while preserving legacy Action Centre queries.
	require_owner_scope = bool(int(filters.get("require_owner_scope") or filters.get("require_global_scope") or 0))
	needle = f"%{str(txt or '').strip()}%"

	query_filters: dict[str, Any] = {"enabled": 1, "user_type": "System User"}
	or_filters = None
	if needle != "%%":
		or_filters = {
			"name": ["like", needle],
			"full_name": ["like", needle],
		}

	candidates = frappe.get_list(
		"User",
		filters=query_filters,
		or_filters=or_filters,
		fields=["name", "full_name"],
		order_by="full_name asc, name asc",
		start=0,
		page_length=MAX_CANDIDATES,
	)
	eligible = [
		[row.name, row.full_name or row.name]
		for row in candidates
		if _is_assignable_user(
			row.name,
			company=company,
			branch=branch,
			require_global_scope=require_global_scope,
			require_owner_scope=require_owner_scope,
		)
	]
	start = max(int(start or 0), 0)
	page_len = min(max(int(page_len or 20), 1), MAX_PAGE_LENGTH)
	return eligible[start : start + page_len]
