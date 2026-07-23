from __future__ import annotations

import frappe

from retailedge.branch_context import get_user_allowed_branches, user_has_global_branch_access


def get_branch_profile_query(user=None):
	user = user or frappe.session.user
	if user_has_global_branch_access(user=user):
		return ""
	allowed = get_user_allowed_branches(user=user).get("branches") or []
	if not allowed:
		return ""
	values = ", ".join(frappe.db.escape(branch) for branch in allowed)
	return f"`tabRetailEdge Branch Profile`.`branch` in ({values})"
