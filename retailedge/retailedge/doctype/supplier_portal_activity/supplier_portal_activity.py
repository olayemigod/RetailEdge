from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

ALLOWED_ACTIVITY_TYPES = {"Message", "Acknowledged"}
MAX_ACTIVITY_MESSAGE_LENGTH = 2000


class SupplierPortalActivity(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("Supplier portal activity records are immutable."), frappe.ValidationError)

	def before_insert(self):
		if not getattr(self.flags, "supplier_portal_activity_api_write", False):
			frappe.throw(
				_("Supplier portal activity can only be recorded through the supplier portal."),
				frappe.PermissionError,
			)
		if self.reference_doctype != "Purchase Order":
			frappe.throw(_("Only Purchase Order activity is supported at this stage."), frappe.ValidationError)
		if self.activity_type not in ALLOWED_ACTIVITY_TYPES:
			frappe.throw(_("Unsupported supplier activity."), frappe.ValidationError)
		message = str(self.message or "").strip()
		if self.activity_type == "Message" and not message:
			frappe.throw(_("A message is required."), frappe.ValidationError)
		if len(message) > MAX_ACTIVITY_MESSAGE_LENGTH:
			frappe.throw(
				_("Message cannot exceed {0} characters.").format(MAX_ACTIVITY_MESSAGE_LENGTH),
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(_("Supplier portal activity records are immutable."), frappe.ValidationError)
