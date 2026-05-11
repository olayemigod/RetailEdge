from __future__ import annotations

import frappe

from retailedge.integrations.coreedge import get_coreedge_status, load_coreedge_attr, log_coreedge_debug


def get_active_branch(user: str | None = None):
	status = get_coreedge_status()
	if not status["branch_context_enabled"]:
		return None

	user = user or frappe.session.user
	func = load_coreedge_attr("coreedge.branch_context.get_active_branch", "coreedge.api.get_active_branch")
	if not func:
		return None

	try:
		return func(user=user)
	except TypeError:
		try:
			return func(user)
		except Exception:
			log_coreedge_debug("CoreEdge active branch lookup failed.", context={"user": user})
			return None
	except Exception:
		log_coreedge_debug("CoreEdge active branch lookup failed.", context={"user": user})
		return None


def get_user_allowed_branches(user: str | None = None):
	status = get_coreedge_status()
	if not status["branch_context_enabled"]:
		return []

	user = user or frappe.session.user
	func = load_coreedge_attr(
		"coreedge.branch_context.get_user_allowed_branches",
		"coreedge.api.get_user_allowed_branches",
	)
	if not func:
		return []

	try:
		result = func(user=user)
	except TypeError:
		try:
			result = func(user)
		except Exception:
			log_coreedge_debug("CoreEdge allowed branches lookup failed.", context={"user": user})
			return []
	except Exception:
		log_coreedge_debug("CoreEdge allowed branches lookup failed.", context={"user": user})
		return []

	if result is None:
		return []

	return list(result)
