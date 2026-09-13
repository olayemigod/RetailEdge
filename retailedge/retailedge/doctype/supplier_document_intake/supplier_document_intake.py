from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

ALLOWED_REVIEW_STATUSES = {"Pending Review", "In Review", "Accepted", "Rejected"}
FINAL_REVIEW_STATUSES = {"Accepted", "Rejected"}
IMMUTABLE_FIELDS = (
	"intake_key",
	"supplier",
	"company",
	"purchase_order",
	"document_type",
	"submitted_on",
	"portal_user",
	"notes",
	"original_file_name",
)


class SupplierDocumentIntake(Document):
	def before_insert(self):
		if not getattr(self.flags, "supplier_document_intake_api_write", False):
			frappe.throw(
				_("Supplier documents can only be submitted through the supplier portal."),
				frappe.PermissionError,
			)
		if self.review_status != "Pending Review":
			frappe.throw(
				_("New supplier documents must start in Pending Review."),
				frappe.ValidationError,
			)
		self.reviewed_by = ""
		self.reviewed_on = None
		self.review_notes = ""

	def validate(self):
		if self.review_status not in ALLOWED_REVIEW_STATUSES:
			frappe.throw(_("Choose a valid review status."), frappe.ValidationError)
		if self.is_new():
			return

		previous = frappe.get_doc(self.doctype, self.name)
		changed_immutable = [
			fieldname for fieldname in IMMUTABLE_FIELDS if self.get(fieldname) != previous.get(fieldname)
		]
		if changed_immutable:
			frappe.throw(
				_("Submitted supplier document identity and source details are immutable."),
				frappe.ValidationError,
			)
		if (
			previous.review_status in FINAL_REVIEW_STATUSES
			and self.review_status != previous.review_status
		):
			frappe.throw(
				_("Accepted or rejected supplier documents cannot be reopened."),
				frappe.ValidationError,
			)

		review_changed = (
			self.review_status != previous.review_status
			or str(self.review_notes or "") != str(previous.review_notes or "")
		)
		if review_changed:
			self.reviewed_by = frappe.session.user
			self.reviewed_on = now_datetime()
		else:
			self.reviewed_by = previous.reviewed_by
			self.reviewed_on = previous.reviewed_on

	def on_trash(self):
		frappe.throw(
			_("Supplier document intake records are retained for review history."),
			frappe.ValidationError,
		)
