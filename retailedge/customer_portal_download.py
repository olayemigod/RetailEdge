from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from erpnext.controllers.website_list_for_contact import has_website_permission

from retailedge.customer_portal import _assert_customer_portal_user
from retailedge.professional_print_formats import MANAGED_MARKER, get_preferred_print_format

PORTAL_DOWNLOAD_DOCTYPES = {
	"Quotation",
	"Sales Order",
	"Sales Invoice",
	"Delivery Note",
}


def _assert_supported_document(doctype: str, name: str):
	doctype = str(doctype or "").strip()
	name = str(name or "").strip()
	if doctype not in PORTAL_DOWNLOAD_DOCTYPES:
		frappe.throw(_("This document type is not available for portal PDF download."), frappe.PermissionError)
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("The requested document is not available."))
	return frappe.get_doc(doctype, name)


def _portal_print_format(doctype: str) -> str:
	preferred = get_preferred_print_format(doctype)
	if not preferred or not frappe.db.exists("Print Format", preferred):
		return "Standard"
	row = frappe.db.get_value(
		"Print Format",
		preferred,
		["doc_type", "disabled", "module", "html"],
		as_dict=True,
	) or {}
	owned = str(row.get("module") or "") == "RetailEdge" or MANAGED_MARKER in str(row.get("html") or "")
	if str(row.get("doc_type") or "") != doctype or cint(row.get("disabled")) or not owned:
		return "Standard"
	return preferred


@frappe.whitelist(methods=["GET"])
def download_customer_document_pdf(doctype: str, name: str):
	"""Download a customer-facing PDF using ERPNext website permissions.

	The browser cannot supply Customer identity or Print Format. Customer scope is
	resolved from the logged-in Website User and ERPNext's native website
	permission check; the output format is limited to Standard or an app-owned
	managed professional format.
	"""
	_assert_customer_portal_user()
	doc = _assert_supported_document(doctype, name)
	if not has_website_permission(doc, "read", frappe.session.user):
		frappe.throw(_("You do not have access to this document."), frappe.PermissionError)

	print_format = _portal_print_format(doc.doctype)
	pdf = frappe.get_print(
		doc.doctype,
		doc.name,
		print_format=print_format,
		as_pdf=True,
		no_letterhead=0,
	)
	frappe.local.response.filename = f"{doc.doctype}-{doc.name}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "download"
