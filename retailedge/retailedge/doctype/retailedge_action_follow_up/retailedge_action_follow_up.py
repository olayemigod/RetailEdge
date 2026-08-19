from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class RetailEdgeActionFollowUp(Document):
	def validate(self):
		if self.assigned_to:
			enabled = frappe.db.get_value("User", self.assigned_to, "enabled")
			if not enabled:
				frappe.throw(_("Assigned user must be enabled."))
		if self.snoozed_until and get_datetime(self.snoozed_until) <= get_datetime():
			frappe.throw(_("Snoozed Until must be in the future."))
		if self.follow_up_on and self.status == "Snoozed" and self.snoozed_until:
			if get_datetime(self.follow_up_on) < get_datetime(self.snoozed_until):
				frappe.throw(_("Follow Up On cannot be before Snoozed Until."))
