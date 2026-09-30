from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


_ALLOWED_STATUSES = {
	"Reserved",
	"Finalize Pending",
	"Finalized",
	"Release Pending",
	"Released",
	"Expired",
	"Reconciliation Required",
	"Failed",
}
_TERMINAL_STATUSES = {
	"Finalized",
	"Released",
	"Expired",
	"Reconciliation Required",
	"Failed",
}
_IDENTITY_FIELDS = {
	"operation_key",
	"entitlement_key",
	"units",
	"transaction_doctype",
	"transaction_name",
	"transaction_event",
	"reserve_idempotency_key",
	"finalize_idempotency_key",
	"release_idempotency_key",
}


class RetailEdgeCoreEdgeQuotaOperation(Document):
	def before_insert(self) -> None:
		if not self.flags.get("allow_quota_operation_create"):
			frappe.throw(
				_("CoreEdge Quota Operations may only be created by the governed coordinator."),
				frappe.PermissionError,
			)

	def validate(self) -> None:
		if self.status not in _ALLOWED_STATUSES:
			frappe.throw(_("Select a valid quota-operation status."), frappe.ValidationError)
		if int(self.units or 0) <= 0:
			frappe.throw(_("Quota-operation Units must be greater than zero."), frappe.ValidationError)
		if self.is_new():
			return

		if not self.flags.get("allow_quota_operation_update"):
			frappe.throw(
				_("CoreEdge Quota Operations may only be changed by the governed coordinator."),
				frappe.PermissionError,
			)

		if any(self.has_value_changed(fieldname) for fieldname in _IDENTITY_FIELDS):
			frappe.throw(
				_("Quota-operation identity fields are immutable after creation."),
				frappe.ValidationError,
			)

		previous_status = self.get_db_value("status") or "Reserved"
		if previous_status in _TERMINAL_STATUSES and self.status != previous_status:
			frappe.throw(
				_("A terminal CoreEdge Quota Operation cannot change status."),
				frappe.ValidationError,
			)

	def on_trash(self) -> None:
		frappe.throw(
			_("CoreEdge Quota Operation history cannot be deleted."),
			frappe.PermissionError,
		)
