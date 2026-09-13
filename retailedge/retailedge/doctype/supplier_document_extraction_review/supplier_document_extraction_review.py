from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

ALLOWED_DECISIONS = {"Accepted", "Rejected"}


class SupplierDocumentExtractionReview(Document):
	def before_insert(self):
		if not getattr(self.flags, "supplier_document_extraction_review_api_write", False):
			frappe.throw(
				_("Supplier document extraction reviews can only be recorded through the controlled review service."),
				frappe.PermissionError,
			)

	def validate(self):
		if not self.is_new():
			frappe.throw(_("Supplier document extraction reviews are immutable."), frappe.ValidationError)
		if self.decision not in ALLOWED_DECISIONS:
			frappe.throw(_("Choose Accepted or Rejected."), frappe.ValidationError)
		if not frappe.db.exists("Supplier Document Extraction", self.extraction):
			frappe.throw(_("Supplier Document Extraction was not found."), frappe.DoesNotExistError)
		extraction = frappe.get_doc("Supplier Document Extraction", self.extraction)
		for fieldname in ("supplier_document_intake", "supplier", "company"):
			if self.get(fieldname) != extraction.get(fieldname):
				frappe.throw(
					_("Extraction review authority must match its immutable extraction evidence."),
					frappe.ValidationError,
				)
		if frappe.db.exists("Supplier Document Extraction Review", {"extraction": self.extraction}):
			frappe.throw(
				_("This extraction already has a final review. Record a new extraction to correct values."),
				frappe.ValidationError,
			)
		if self.decision == "Rejected" and not str(self.review_notes or "").strip():
			frappe.throw(_("Review notes are required when rejecting an extraction."), frappe.ValidationError)

	def on_trash(self):
		frappe.throw(
			_("Supplier document extraction reviews are retained for audit history."),
			frappe.ValidationError,
		)
