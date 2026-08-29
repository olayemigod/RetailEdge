from __future__ import annotations

import frappe

from retailedge.customer_portal import get_customer_portal_context

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/customer_portal"
		raise frappe.Redirect

	portal = get_customer_portal_context()
	company_name = str(frappe.defaults.get_global_default("default_company") or "").strip()
	context.no_cache = 1
	context.show_sidebar = True
	context.title = "Customer Portal"
	context.portal = portal
	context.company_name = company_name
	context.user_full_name = portal.get("user_full_name") or ""
	context.customer_label = portal.get("customer_label") or ""
	return context
