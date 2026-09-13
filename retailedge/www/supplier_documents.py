from __future__ import annotations

import frappe

from retailedge.supplier_document_intake import get_supplier_document_intake_context

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/supplier_documents"
		raise frappe.Redirect

	intake = get_supplier_document_intake_context()
	context.no_cache = 1
	context.show_sidebar = True
	context.title = "Supplier Documents"
	context.intake = intake
	context.company_name = intake.get("company_name") or ""
	context.supplier_label = intake.get("supplier_label") or ""
	return context
