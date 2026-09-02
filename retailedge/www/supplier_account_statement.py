from __future__ import annotations

import frappe

from retailedge.supplier_portal_financial import get_supplier_account_statement

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/supplier_account_statement"
		raise frappe.Redirect

	statement = get_supplier_account_statement(
		company=str(frappe.form_dict.get("company") or "").strip() or None,
		from_date=str(frappe.form_dict.get("from_date") or "").strip() or None,
		to_date=str(frappe.form_dict.get("to_date") or "").strip() or None,
	)
	context.no_cache = 1
	context.show_sidebar = True
	context.title = "Supplier Account Statement"
	context.statement = statement
	context.company_name = statement.get("company") or ""
	return context
