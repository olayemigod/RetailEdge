from __future__ import annotations

import frappe

from retailedge.integrations.coreedge import is_coreedge_enabled, load_coreedge_attr, log_coreedge_debug


def has_retailedge_access(user: str | None = None, tenant: str | None = None) -> bool:
	if not is_coreedge_enabled():
		return True

	user = user or frappe.session.user
	func = load_coreedge_attr("coreedge.entitlements.has_app_access", "coreedge.api.has_app_access")
	if not func:
		log_coreedge_debug(
			"CoreEdge entitlement adapter not available; defaulting to access allowed.",
			context={"user": user, "tenant": tenant},
		)
		return True

	try:
		return bool(func(app_name="retailedge", user=user, tenant=tenant))
	except TypeError:
		try:
			return bool(func("retailedge", user=user, tenant=tenant))
		except Exception:
			log_coreedge_debug(
				"CoreEdge entitlement adapter call failed; defaulting to access allowed.",
				context={"user": user, "tenant": tenant},
			)
			return True
	except Exception:
		log_coreedge_debug(
			"CoreEdge entitlement adapter call failed; defaulting to access allowed.",
			context={"user": user, "tenant": tenant},
		)
		return True


def require_retailedge_access(user: str | None = None, tenant: str | None = None) -> bool:
	if not has_retailedge_access(user=user, tenant=tenant):
		raise frappe.PermissionError("You do not currently have access to RetailEdge.")

	return True
