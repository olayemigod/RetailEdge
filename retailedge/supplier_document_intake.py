from __future__ import annotations

from mimetypes import guess_type
from typing import Any
from uuid import uuid4

import frappe
from frappe import _
from frappe.utils import now_datetime, strip_html
from frappe.utils.file_manager import save_file

from erpnext.controllers.website_list_for_contact import has_website_permission, get_transaction_list

from retailedge.supplier_portal import _assert_supplier_portal_user

ALLOWED_DOCUMENT_TYPES = {
	"Supplier Invoice",
	"Delivery Document",
	"Receipt",
	"Credit Note",
	"Other",
}
ALLOWED_MIMETYPES = {
	"application/pdf",
	"image/jpeg",
	"image/png",
	"application/msword",
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	"application/vnd.ms-excel",
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"text/csv",
	"text/plain",
}
MAX_NOTES_LENGTH = 2000
MAX_PO_CHOICES = 50
MAX_RECENT_INTAKES = 50


def _clean_notes(notes: str | None) -> str:
	plain = strip_html(str(notes or ""))
	cleaned = "\n".join(line.strip() for line in plain.splitlines() if line.strip()).strip()
	if len(cleaned) > MAX_NOTES_LENGTH:
		frappe.throw(
			_("Notes cannot exceed {0} characters.").format(MAX_NOTES_LENGTH),
			frappe.ValidationError,
		)
	return cleaned


def _assert_owned_purchase_order(purchase_order_name: str, suppliers: list[str]):
	purchase_order_name = str(purchase_order_name or "").strip()
	if not purchase_order_name or not frappe.db.exists("Purchase Order", purchase_order_name):
		frappe.throw(_("Purchase Order was not found."), frappe.DoesNotExistError)
	purchase_order = frappe.get_doc("Purchase Order", purchase_order_name)
	if purchase_order.supplier not in suppliers:
		frappe.throw(
			_("This Purchase Order is not linked to your supplier account."),
			frappe.PermissionError,
		)
	if not has_website_permission(purchase_order, "read", frappe.session.user):
		frappe.throw(_("You do not have access to this Purchase Order."), frappe.PermissionError)
	if purchase_order.docstatus != 1:
		frappe.throw(
			_("Documents can only be submitted against a submitted Purchase Order."),
			frappe.ValidationError,
		)
	return purchase_order


def _uploaded_file() -> tuple[str, bytes, str]:
	filename = str(getattr(frappe.local, "uploaded_filename", "") or "").strip()
	content = getattr(frappe.local, "uploaded_file", None)
	if not filename or not content:
		frappe.throw(_("Choose a file to upload."), frappe.ValidationError)
	mimetype = str(guess_type(filename)[0] or "").lower()
	if mimetype not in ALLOWED_MIMETYPES:
		frappe.throw(
			_("Upload a PDF, JPG, PNG, Word, Excel, CSV or text document."),
			frappe.ValidationError,
		)
	return filename, content, mimetype


@frappe.whitelist(methods=["POST"])
def upload_supplier_document() -> dict[str, Any]:
	suppliers = _assert_supplier_portal_user()
	purchase_order = _assert_owned_purchase_order(
		str(frappe.form_dict.get("purchase_order_name") or ""),
		suppliers,
	)
	document_type = str(frappe.form_dict.get("document_type") or "").strip()
	if document_type not in ALLOWED_DOCUMENT_TYPES:
		frappe.throw(_("Choose a valid document type."), frappe.ValidationError)

	notes = _clean_notes(frappe.form_dict.get("notes"))
	filename, content, mimetype = _uploaded_file()

	intake = frappe.new_doc("Supplier Document Intake")
	intake.update(
		{
			"intake_key": f"SDI-{uuid4().hex}",
			"supplier": purchase_order.supplier,
			"company": purchase_order.company,
			"purchase_order": purchase_order.name,
			"document_type": document_type,
			"submitted_on": now_datetime(),
			"portal_user": frappe.session.user,
			"notes": notes,
			"original_file_name": filename,
			"review_status": "Pending Review",
		}
	)
	intake.flags.supplier_document_intake_api_write = True
	intake.insert(ignore_permissions=True)

	file_doc = save_file(
		filename,
		content,
		"Supplier Document Intake",
		intake.name,
		folder="Home/Attachments",
		is_private=1,
	)
	return {
		"intake": intake.name,
		"purchase_order": purchase_order.name,
		"document_type": document_type,
		"review_status": intake.review_status,
		"file_name": file_doc.file_name,
		"mimetype": mimetype,
		"private": True,
		"native_buying_document_created": False,
	}


def get_supplier_document_intake_context() -> dict[str, Any]:
	suppliers = _assert_supplier_portal_user()
	purchase_orders = []
	if frappe.db.exists("DocType", "Purchase Order"):
		native_rows = get_transaction_list(
			doctype="Purchase Order",
			limit_start=0,
			limit_page_length=MAX_PO_CHOICES,
			order_by="creation desc",
		) or []
		purchase_orders = [
			{
				"name": row.name,
				"status": getattr(row, "status", "") or "",
				"company": getattr(row, "company", "") or "",
				"date": getattr(row, "transaction_date", None),
			}
			for row in native_rows
		]

	intakes = []
	if frappe.db.exists("DocType", "Supplier Document Intake"):
		rows = frappe.get_all(
			"Supplier Document Intake",
			filters={"supplier": ["in", suppliers]},
			fields=[
				"name",
				"supplier",
				"company",
				"purchase_order",
				"document_type",
				"submitted_on",
				"original_file_name",
				"review_status",
				"reviewed_on",
				"review_notes",
			],
			order_by="submitted_on desc, creation desc",
			limit_page_length=MAX_RECENT_INTAKES,
		)
		intakes = [dict(row) for row in rows]

	companies = {str(row.get("company") or "") for row in intakes if row.get("company")}
	companies.update(str(row.get("company") or "") for row in purchase_orders if row.get("company"))
	return {
		"supplier_names": suppliers,
		"supplier_label": ", ".join(suppliers),
		"purchase_orders": purchase_orders,
		"intakes": intakes,
		"company_name": next(iter(companies)) if len(companies) == 1 else "",
		"document_types": sorted(ALLOWED_DOCUMENT_TYPES),
		"source_of_truth": (
			"Private File attached to Supplier Document Intake; ERPNext buying documents remain unchanged"
		),
		"human_review_required": True,
	}
