from __future__ import annotations

import frappe

from retailedge.supplier_portal import get_supplier_portal_context

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/supplier_portal"
		raise frappe.Redirect

	portal = get_supplier_portal_context()
	context.no_cache = 1
	context.show_sidebar = True
	context.title = "Supplier Portal"
	context.portal = portal
	context.company_name = portal.get("company_name") or ""
	context.user_full_name = portal.get("user_full_name") or ""
	context.supplier_label = portal.get("supplier_label") or ""
	return context
