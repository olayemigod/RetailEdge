from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class RetailEdgeCoreEdgeQuotaReviewEvent(Document):
	def before_insert(self) -> None:
		if not self.flags.get("allow_retailedge_quota_review_event_create"):
			frappe.throw(
				_("Quota Review Events may only be created by the governed review service."),
				frappe.PermissionError,
			)

	def before_save(self) -> None:
		if self.is_new():
			return
		frappe.throw(
			_("Quota Review Events are append-only and cannot be edited."),
			frappe.PermissionError,
		)

	def on_trash(self) -> None:
		frappe.throw(
			_("Quota Review Event history cannot be deleted."),
			frappe.PermissionError,
		)
