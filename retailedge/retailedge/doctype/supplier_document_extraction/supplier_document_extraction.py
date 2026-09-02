from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

ALLOWED_EXTRACTION_METHODS = {"Manual", "Provider"}


class SupplierDocumentExtraction(Document):
	def before_insert(self):
		if not getattr(self.flags, "supplier_document_extraction_api_write", False):
			frappe.throw(
				_("Supplier document extraction evidence can only be recorded through the controlled extraction service."),
				frappe.PermissionError,
			)

	def validate(self):
		if not self.is_new():
			frappe.throw(
				_("Supplier document extraction evidence is immutable. Record a new extraction to correct values."),
				frappe.ValidationError,
			)
		if self.extraction_method not in ALLOWED_EXTRACTION_METHODS:
			frappe.throw(_("Choose Manual or Provider extraction."), frappe.ValidationError)
		if not frappe.db.exists("Supplier Document Intake", self.supplier_document_intake):
			frappe.throw(_("Supplier Document Intake was not found."), frappe.DoesNotExistError)
		intake = frappe.get_doc("Supplier Document Intake", self.supplier_document_intake)
		for fieldname in ("supplier", "company", "purchase_order"):
			if self.get(fieldname) != intake.get(fieldname):
				frappe.throw(
					_("Extraction authority must match the Supplier Document Intake."),
					frappe.ValidationError,
				)

		file_row = frappe.db.get_value(
			"File",
			self.source_file,
			["file_name", "is_private", "attached_to_doctype", "attached_to_name"],
			as_dict=True,
		)
		if not file_row:
			frappe.throw(_("Extraction source file was not found."), frappe.DoesNotExistError)
		if (
			not int(file_row.is_private or 0)
			or file_row.attached_to_doctype != "Supplier Document Intake"
			or file_row.attached_to_name != intake.name
			or file_row.file_name != self.source_file_name
		):
			frappe.throw(
				_("Extraction evidence must point to the private file attached to its intake record."),
				frappe.ValidationError,
			)
		if self.confidence not in (None, ""):
			confidence = flt(self.confidence)
			if confidence < 0 or confidence > 100:
				frappe.throw(_("Confidence must be between 0 and 100."), frappe.ValidationError)
		if self.extraction_method == "Manual" and (
			self.provider_name or self.provider_reference or self.raw_payload_json or self.confidence not in (None, "")
		):
			frappe.throw(
				_("Manual extraction cannot carry provider metadata or provider confidence."),
				frappe.ValidationError,
			)
		if self.extraction_method == "Provider" and not self.provider_name:
			frappe.throw(_("Provider name is required for provider extraction."), frappe.ValidationError)

	def on_trash(self):
		frappe.throw(
			_("Supplier document extraction evidence is retained for audit history."),
			frappe.ValidationError,
		)
