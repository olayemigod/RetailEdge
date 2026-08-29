from __future__ import annotations

import frappe

from retailedge.customer_project_updates import get_customer_project_updates

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/customer_project_updates"
		raise frappe.Redirect

	updates = get_customer_project_updates(
		project=str(frappe.form_dict.get("project") or "").strip() or None,
	)
	context.no_cache = 1
	context.show_sidebar = True
	context.title = "Project Updates"
	context.updates = updates
	context.company_name = str(frappe.defaults.get_global_default("default_company") or "").strip()
	return context
