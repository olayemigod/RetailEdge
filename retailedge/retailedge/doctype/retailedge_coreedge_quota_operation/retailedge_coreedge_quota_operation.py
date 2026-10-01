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
	"reconciliation_case_reference",
	"reconciliation_case_status",
	"reconciliation_case_evidence_hash",
	"reconciliation_submitted_on",
	"reconciliation_last_idempotency_key",
	"reconciliation_last_checked_on",
	"reconciliation_decision_reference",
	"reconciliation_decision_type",
	"reconciliation_result_status",
	"reconciliation_result_reason_code",
	"reconciliation_applied_usage",
	"reconciliation_reference",
	"reconciliation_decided_on",
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

		immutable_changes = [
			fieldname for fieldname in _IMMUTABLE_FIELDS if self.has_value_changed(fieldname)
		]
		if immutable_changes:
			allowed_reconciliation_fields = {
				"reservation_reference",
				"reservation_expires_on",
				"reserve_idempotency_key",
				"finalize_idempotency_key",
				"release_idempotency_key",
				"reserved_on",
			}
			allowed_case_submission_fields = {
				"reconciliation_case_reference",
				"reconciliation_case_status",
				"reconciliation_case_evidence_hash",
				"reconciliation_submitted_on",
				"reconciliation_last_idempotency_key",
			}
			allowed_case_status_sync_fields = {
				"reconciliation_case_status",
				"reconciliation_last_checked_on",
				"reconciliation_decision_reference",
				"reconciliation_decision_type",
				"reconciliation_result_status",
				"reconciliation_result_reason_code",
				"reconciliation_applied_usage",
				"reconciliation_reference",
				"reconciliation_decided_on",
			}
			changed_fields = set(immutable_changes)
			reconciliation_allowed = bool(
				self.flags.get("allow_retailedge_quota_reconciliation")
				and changed_fields.issubset(allowed_reconciliation_fields)
			)
			case_submission_allowed = bool(
				self.flags.get("allow_retailedge_quota_case_submission")
				and changed_fields.issubset(allowed_case_submission_fields)
			)
			case_status_sync_allowed = bool(
				self.flags.get("allow_retailedge_quota_case_status_sync")
				and changed_fields.issubset(allowed_case_status_sync_fields)
			)
			if (
				not reconciliation_allowed
				and not case_submission_allowed
				and not case_status_sync_allowed
			):
				frappe.throw(
					_(
						"CoreEdge quota operation identity, reservation and reconciliation case fields "
						"are immutable."
					),
					frappe.ValidationError,
				)

		previous_status = self.get_db_value("status") or "Pending Finalize"
		if previous_status in {"Finalized", "Resolved", "Rejected"} and self.status != previous_status:
			frappe.throw(
				_("A terminal CoreEdge quota operation cannot change status."),
				frappe.ValidationError,
			)
		if previous_status == "Needs Review" and self.status != previous_status:
			reopened_by_reservation = bool(
				self.flags.get("allow_retailedge_quota_reconciliation")
				and self.status in {"Pending Finalize", "Finalized"}
			)
			closed_by_case_status = bool(
				self.flags.get("allow_retailedge_quota_case_status_sync")
				and self.status in {"Resolved", "Rejected"}
			)
			if not reopened_by_reservation and not closed_by_case_status:
				frappe.throw(
					_(
						"A Needs Review quota operation may only be reopened by reservation "
						"reconciliation or closed by authoritative CoreEdge case status."
					),
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
