from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


_IMMUTABLE_FIELDS = {
	"operation_key",
	"source_doctype",
	"source_name",
	"company",
	"branch",
	"entitlement_key",
	"units",
	"reservation_reference",
	"reservation_expires_on",
	"reserve_idempotency_key",
	"finalize_idempotency_key",
	"release_idempotency_key",
	"reserved_on",
}


class RetailEdgeCoreEdgeQuotaOperation(Document):
	def before_insert(self) -> None:
		if not self.flags.get("allow_retailedge_quota_operation_create"):
			frappe.throw(
				_("CoreEdge quota operations may only be created by the RetailEdge quota service."),
				frappe.PermissionError,
			)

	def validate(self) -> None:
		if int(self.units or 0) <= 0:
			frappe.throw(_("Quota operation Units must be greater than zero."), frappe.ValidationError)
		if self.status in {"Pending Finalize", "Finalized"} and not self.reservation_reference:
			frappe.throw(
				_("A quota reservation reference is required for active/finalized operations."),
				frappe.ValidationError,
			)
		if self.is_new():
			return
		if not self.flags.get("allow_retailedge_quota_operation_update"):
			frappe.throw(
				_("CoreEdge quota operations may only be changed by the RetailEdge quota service."),
				frappe.PermissionError,
			)

		if any(self.has_value_changed(fieldname) for fieldname in _IMMUTABLE_FIELDS):
			frappe.throw(
				_("CoreEdge quota operation identity and reservation fields are immutable."),
				frappe.ValidationError,
			)

		previous_status = self.get_db_value("status") or "Pending Finalize"
		if previous_status == "Finalized" and self.status != "Finalized":
			frappe.throw(
				_("A finalized CoreEdge quota operation cannot change status."),
				frappe.ValidationError,
			)
		if previous_status == "Needs Review" and self.status not in {
			"Needs Review",
			"Finalized",
		}:
			frappe.throw(
				_("A Needs Review quota operation may only remain under review or finalize."),
				frappe.ValidationError,
			)
		if previous_status == "Pending Finalize" and self.status not in {
			"Pending Finalize",
			"Finalized",
			"Needs Review",
		}:
			frappe.throw(_("Invalid CoreEdge quota operation transition."), frappe.ValidationError)

	def on_trash(self) -> None:
		frappe.throw(
			_("CoreEdge quota operation history cannot be deleted."),
			frappe.PermissionError,
		)
