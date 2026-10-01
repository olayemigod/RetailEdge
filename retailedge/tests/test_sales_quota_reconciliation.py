from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime, now_datetime

from retailedge.coreedge_sales_quota_reconciliation import (
	REVIEW_EVENT_DOCTYPE,
	_can_mutate_quota_review,
	_recommended_action,
	get_quota_reconciliation_rows,
	refresh_reconciliation_case_status,
	retry_quota_finalization,
	submit_unreserved_quota_reconciliation_case,
)
from retailedge.coreedge_quota_permissions import (
	get_operation_permission_query_conditions,
	has_operation_permission,
)
from retailedge.integrations.coreedge_remote_usage import CoreEdgeRemoteUsageError


OPERATION_DOCTYPE = "RetailEdge CoreEdge Quota Operation"


class SalesQuotaReconciliationContractTests(unittest.TestCase):
	def _operation(self, **overrides):
		values = {
			"name": "quota-op-test",
			"operation_key": "resq-test-case",
			"status": "Needs Review",
			"company": "RetailEdge Consulting",
			"branch": "Ketu",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-0001",
			"entitlement_key": "SALES_TRANSACTIONS",
			"units": 1,
			"reservation_reference": None,
			"reservation_expires_on": None,
			"reason_code": "FAIL_OPEN_UNRESERVED",
			"remote_message": "COREDGE_REMOTE_USAGE_UNAVAILABLE",
			"last_error": "",
			"reconciliation_case_reference": None,
			"reconciliation_case_status": None,
			"reconciliation_case_evidence_hash": None,
			"reconciliation_submitted_on": None,
			"reconciliation_last_idempotency_key": None,
			"reconciliation_last_checked_on": None,
			"reconciliation_decision_reference": None,
			"reconciliation_decision_type": None,
			"reconciliation_result_status": None,
			"reconciliation_result_reason_code": None,
			"reconciliation_applied_usage": 0,
			"reconciliation_reference": None,
			"reconciliation_decided_on": None,
			"attempt_count": 0,
			"finalized_on": None,
			"warning": 0,
			"flags": frappe._dict(),
		}
		values.update(overrides)
		op = SimpleNamespace(**values)
		op.save = MagicMock()
		op.reload = MagicMock()
		return op

	def test_recommended_actions_are_state_specific(self):
		self.assertEqual(
			_recommended_action({"status": "Pending Finalize", "reservation_reference": "CEUR-1"}),
			"Retry CoreEdge finalization",
		)
		self.assertEqual(
			_recommended_action(
				{
					"status": "Needs Review",
					"reservation_reference": "",
					"reason_code": "FAIL_OPEN_UNRESERVED",
					"reconciliation_case_reference": "",
				}
			),
			"Submit to CoreEdge review",
		)
		self.assertEqual(
			_recommended_action(
				{
					"status": "Needs Review",
					"reservation_reference": "",
					"reason_code": "FAIL_OPEN_UNRESERVED",
					"reconciliation_case_reference": "ceurc-existing",
				}
			),
			"CoreEdge review submitted",
		)
		self.assertEqual(
			_recommended_action(
				{"status": "Needs Review", "reservation_reference": "", "reason_code": "OTHER"}
			),
			"Manual CoreEdge review required",
		)
		self.assertEqual(
			_recommended_action({"status": "Resolved", "reservation_reference": ""}),
			"CoreEdge usage review resolved",
		)
		self.assertEqual(
			_recommended_action({"status": "Rejected", "reservation_reference": ""}),
			"CoreEdge evidence rejected",
		)

	@patch("retailedge.coreedge_quota_permissions._readable_companies", return_value=["RetailEdge Consulting"])
	@patch("retailedge.coreedge_quota_permissions.get_report_branch_scope")
	@patch("retailedge.coreedge_quota_permissions.frappe.get_roles")
	def test_permission_query_limits_auditor_to_assigned_branch(
		self,
		mock_roles,
		mock_scope,
		_mock_companies,
	):
		mock_roles.return_value = ["RetailEdge Auditor"]
		mock_scope.return_value = {
			"restricted": True,
			"allowed_branches": ["Ketu"],
		}
		condition = get_operation_permission_query_conditions("audit@example.com")
		self.assertIn("RetailEdge Consulting", condition)
		self.assertIn("Ketu", condition)
		self.assertNotIn("Ikeja", condition)

	@patch("retailedge.coreedge_quota_permissions.get_report_branch_scope")
	@patch("retailedge.coreedge_quota_permissions.frappe.has_permission", return_value=True)
	@patch("retailedge.coreedge_quota_permissions.frappe.get_roles")
	def test_direct_operation_permission_respects_branch_scope(
		self,
		mock_roles,
		_mock_company_permission,
		mock_scope,
	):
		mock_roles.return_value = ["RetailEdge Branch Manager"]
		mock_scope.return_value = {
			"restricted": True,
			"allowed_branches": ["Ketu"],
		}
		allowed = SimpleNamespace(company="RetailEdge Consulting", branch="Ketu")
		denied = SimpleNamespace(company="RetailEdge Consulting", branch="Ikeja")
		self.assertTrue(
			has_operation_permission(
				allowed,
				user="branch@example.com",
				permission_type="read",
			)
		)
		self.assertFalse(
			has_operation_permission(
				denied,
				user="branch@example.com",
				permission_type="read",
			)
		)
		self.assertFalse(
			has_operation_permission(
				allowed,
				user="branch@example.com",
				permission_type="write",
			)
		)

	@patch("retailedge.coreedge_sales_quota_reconciliation.frappe.get_list")
	@patch("retailedge.coreedge_sales_quota_reconciliation.validate_report_scope")
	@patch("retailedge.coreedge_sales_quota_reconciliation.frappe.has_permission", return_value=True)
	def test_report_rows_apply_authoritative_branch_scope_before_query(
		self,
		_mock_has_permission,
		mock_scope,
		mock_get_list,
	):
		mock_scope.return_value = {
			"restricted": True,
			"allowed_branches": ["Ketu", "Ikorodu"],
		}
		mock_get_list.return_value = []
		result = get_quota_reconciliation_rows(
			{"company": "RetailEdge Consulting"},
			user="branch@example.com",
		)
		filters = mock_get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "RetailEdge Consulting")
		self.assertEqual(filters["branch"], ["in", ["Ketu", "Ikorodu"]])
		self.assertEqual(
			filters["status"],
			["in", ["Needs Review", "Pending Finalize"]],
		)
		self.assertTrue(result["scope"]["restricted"])

	@patch("retailedge.coreedge_sales_quota_reconciliation.frappe.get_roles")
	def test_only_manager_roles_can_mutate_reconciliation(self, mock_roles):
		mock_roles.return_value = ["RetailEdge Auditor"]
		self.assertFalse(_can_mutate_quota_review(user="auditor@example.com"))
		mock_roles.return_value = ["RetailEdge Manager"]
		self.assertTrue(_can_mutate_quota_review(user="manager@example.com"))

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation.finalize_sales_quota_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_retry_finalization_can_resolve_needs_review(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_finalize,
		mock_event,
	):
		op = self._operation(
			reservation_reference="CEUR-RETRY",
			reason_code="USAGE_RESERVATION_ACCESS_DENIED",
		)
		mock_get_operation.return_value = op

		def finalize(_name, allow_needs_review=False):
			self.assertTrue(allow_needs_review)
			op.status = "Finalized"
			op.reason_code = "RESERVATION_FINALIZED"
			return {"status": "Finalized"}

		mock_finalize.side_effect = finalize
		result = retry_quota_finalization(
			op.name,
			"Service Client access was repaired and the reservation should be rechecked.",
		)
		self.assertTrue(result["ok"])
		self.assertEqual(result["status"], "Finalized")
		mock_event.assert_called_once()
		self.assertEqual(mock_event.call_args.kwargs["action"], "Retry Finalization")
		self.assertEqual(mock_event.call_args.kwargs["result"], "Finalized")

	@patch("retailedge.coreedge_sales_quota_reconciliation.frappe.db.get_value")
	@patch("retailedge.coreedge_sales_quota_reconciliation.frappe.get_meta")
	def test_cancelled_sale_is_not_eligible_for_coreedge_usage_evidence(
		self,
		mock_meta,
		mock_get_value,
	):
		mock_meta.return_value.has_field.side_effect = lambda fieldname: fieldname in {
			"posting_date",
			"posting_time",
		}
		mock_get_value.return_value = frappe._dict(
			{
				"docstatus": 2,
				"posting_date": "2026-09-30",
				"posting_time": "14:25:00",
				"creation": "2026-09-30 14:20:00",
			}
		)
		from retailedge.coreedge_sales_quota_reconciliation import _get_source_state

		with self.assertRaises(frappe.ValidationError):
			_get_source_state(self._operation())

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_source_state")
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_historical_fail_open_sale_submits_original_occurrence_without_new_reservation(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		mock_source,
		_mock_attempt,
		mock_event,
	):
		op = self._operation()
		mock_get_operation.return_value = op
		mock_source.return_value = {
			"docstatus": 1,
			"event_date": get_datetime("2026-09-30").date(),
			"occurred_on": get_datetime("2026-09-30 14:25:00"),
		}
		client = MagicMock()
		client.submit_reconciliation_case.return_value = {
			"data": {
				"ok": True,
				"status": "Accepted",
				"case": {
					"accepted": True,
					"case_reference": "ceurc-historical-001",
					"case_status": "Open",
					"evidence_hash": "a" * 64,
					"submitted_on": "2026-10-01 20:00:00",
				},
			}
		}
		mock_client_factory.return_value = client

		result = submit_unreserved_quota_reconciliation_case(
			op.name,
			"Verified the original sale committed during the CoreEdge outage.",
		)

		self.assertTrue(result["ok"])
		self.assertEqual(result["status"], "Needs Review")
		self.assertIsNone(op.reservation_reference)
		self.assertEqual(op.reconciliation_case_reference, "ceurc-historical-001")
		self.assertEqual(op.reconciliation_case_status, "Open")
		self.assertEqual(op.reconciliation_case_evidence_hash, "a" * 64)
		self.assertTrue(op.flags.allow_retailedge_quota_case_submission)
		op.save.assert_called_once()
		client.reserve_usage.assert_not_called()
		client.get_usage_status.assert_not_called()

		call = client.submit_reconciliation_case.call_args
		self.assertEqual(call.args[0], "SALES_TRANSACTIONS")
		self.assertEqual(call.args[1], "resq-test-case")
		self.assertEqual(call.args[2], "FAIL_OPEN_UNRESERVED")
		self.assertEqual(call.args[4], "Sales Invoice")
		self.assertEqual(call.args[5], "SINV-0001")
		self.assertEqual(call.args[6], "2026-09-30 14:25:00")
		self.assertEqual(call.kwargs["local_status"], "Needs Review")
		self.assertEqual(call.kwargs["local_reason_code"], "FAIL_OPEN_UNRESERVED")
		self.assertEqual(mock_event.call_args.kwargs["action"], "Submit CoreEdge Review")
		self.assertEqual(mock_event.call_args.kwargs["result"], "Submitted")

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_source_state")
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_missing_reconcile_submit_capability_keeps_fail_open_case_in_review(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		mock_source,
		_mock_attempt,
		mock_event,
	):
		op = self._operation()
		mock_get_operation.return_value = op
		mock_source.return_value = {
			"docstatus": 1,
			"event_date": get_datetime("2026-10-01").date(),
			"occurred_on": get_datetime("2026-10-01 10:30:00"),
		}
		client = MagicMock()
		client.submit_reconciliation_case.return_value = {
			"data": {
				"ok": False,
				"reason_code": "CAPABILITY_NOT_ACTIVATED",
				"message": "The required CoreEdge capability is not active.",
			}
		}
		mock_client_factory.return_value = client

		result = submit_unreserved_quota_reconciliation_case(
			op.name,
			"Submit the audited fail-open evidence to CoreEdge.",
		)

		self.assertFalse(result["ok"])
		self.assertEqual(op.status, "Needs Review")
		self.assertEqual(op.reason_code, "FAIL_OPEN_UNRESERVED")
		self.assertIsNone(op.reconciliation_case_reference)
		self.assertIn("capability", op.last_error.lower())
		client.reserve_usage.assert_not_called()
		self.assertEqual(mock_event.call_args.kwargs["result"], "Blocked")
		self.assertEqual(
			mock_event.call_args.kwargs["reason_code"],
			"CAPABILITY_NOT_ACTIVATED",
		)

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", side_effect=[1, 2])
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_source_state")
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_case_submission_retry_uses_new_request_key_but_same_business_identity(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		mock_source,
		_mock_attempt,
		_mock_event,
	):
		op = self._operation(remote_message="Original reserve request timed out.")
		mock_get_operation.return_value = op
		mock_source.return_value = {
			"docstatus": 1,
			"event_date": get_datetime("2026-10-01").date(),
			"occurred_on": get_datetime("2026-10-01 11:45:00"),
		}
		client = MagicMock()
		client.submit_reconciliation_case.side_effect = [
			CoreEdgeRemoteUsageError("COREDGE_REMOTE_USAGE_UNAVAILABLE"),
			{
				"data": {
					"ok": True,
					"status": "Accepted",
					"case": {
						"case_reference": "ceurc-retry-001",
						"case_status": "Open",
						"evidence_hash": "b" * 64,
						"submitted_on": "2026-10-01 20:10:00",
					},
				}
			},
		]
		mock_client_factory.return_value = client

		first = submit_unreserved_quota_reconciliation_case(
			op.name,
			"First governed submission attempt.",
		)
		second = submit_unreserved_quota_reconciliation_case(
			op.name,
			"Retry after the transport failure.",
		)

		self.assertFalse(first["ok"])
		self.assertTrue(second["ok"])
		self.assertEqual(op.reconciliation_case_reference, "ceurc-retry-001")
		self.assertEqual(client.submit_reconciliation_case.call_count, 2)
		first_call, second_call = client.submit_reconciliation_case.call_args_list
		self.assertEqual(first_call.args[1], second_call.args[1])
		self.assertEqual(first_call.args[1], "resq-test-case")
		self.assertNotEqual(first_call.args[7], second_call.args[7])
		self.assertEqual(first_call.kwargs["error_summary"], second_call.kwargs["error_summary"])

	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_already_submitted_case_does_not_create_another_remote_request(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-existing",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op

		result = submit_unreserved_quota_reconciliation_case(
			op.name,
			"Confirm the already-submitted CoreEdge review case.",
		)

		self.assertTrue(result["ok"])
		self.assertEqual(result["reconciliation_case_reference"], "ceurc-existing")
		mock_client_factory.assert_not_called()


	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_open_coreedge_case_refresh_stays_needs_review_without_reservation(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		_mock_attempt,
		mock_event,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-open-001",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op
		client = MagicMock()
		client.get_reconciliation_case_status.return_value = {
			"data": {
				"ok": True,
				"status": "Found",
				"case": {
					"case_reference": "ceurc-open-001",
					"case_status": "Open",
					"decision": None,
				},
			}
		}
		mock_client_factory.return_value = client

		result = refresh_reconciliation_case_status(
			op.name,
			"Check whether CoreEdge has completed the platform review.",
		)

		self.assertTrue(result["ok"])
		self.assertEqual(result["status"], "Needs Review")
		self.assertEqual(op.reconciliation_case_status, "Open")
		self.assertIsNotNone(op.reconciliation_last_checked_on)
		self.assertIsNone(op.reservation_reference)
		self.assertEqual(op.reason_code, "FAIL_OPEN_UNRESERVED")
		self.assertTrue(op.flags.allow_retailedge_quota_case_status_sync)
		client.reserve_usage.assert_not_called()
		client.finalize_usage.assert_not_called()
		self.assertEqual(mock_event.call_args.kwargs["action"], "Refresh CoreEdge Review")
		self.assertEqual(mock_event.call_args.kwargs["result"], "Needs Review")

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_resolved_coreedge_case_closes_local_review_without_reservation(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		_mock_attempt,
		mock_event,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-resolved-001",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op
		client = MagicMock()
		client.get_reconciliation_case_status.return_value = {
			"data": {
				"ok": True,
				"status": "Found",
				"case": {
					"case_reference": "ceurc-resolved-001",
					"case_status": "Resolved",
					"decision": {
						"decision_reference": "CEURD-RESOLVED",
						"decision_type": "Apply Usage",
						"reason_code": "COREEDGE_UNAVAILABLE",
						"result_status": "Recorded Historical",
						"result_reason_code": "HISTORICAL_USAGE_RECORDED",
						"applied_usage": True,
						"reconciliation_reference": "CEURC-USAGE-001",
						"decided_on": "2026-10-01 20:30:00",
					},
				},
			}
		}
		mock_client_factory.return_value = client

		result = refresh_reconciliation_case_status(
			op.name,
			"Refresh the submitted fail-open sale after CoreEdge review.",
		)

		self.assertTrue(result["ok"])
		self.assertEqual(result["status"], "Resolved")
		self.assertEqual(op.status, "Resolved")
		self.assertEqual(op.reconciliation_case_status, "Resolved")
		self.assertEqual(op.reconciliation_decision_reference, "CEURD-RESOLVED")
		self.assertEqual(op.reconciliation_decision_type, "Apply Usage")
		self.assertEqual(op.reconciliation_result_status, "Recorded Historical")
		self.assertEqual(
			op.reconciliation_result_reason_code,
			"HISTORICAL_USAGE_RECORDED",
		)
		self.assertEqual(op.reconciliation_reference, "CEURC-USAGE-001")
		self.assertTrue(op.reconciliation_applied_usage)
		self.assertIsNone(op.reservation_reference)
		self.assertEqual(op.reason_code, "FAIL_OPEN_UNRESERVED")
		client.reserve_usage.assert_not_called()
		client.finalize_usage.assert_not_called()
		self.assertEqual(mock_event.call_args.kwargs["result"], "Resolved")

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_rejected_coreedge_case_closes_local_review_as_rejected(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		_mock_attempt,
		mock_event,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-rejected-001",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op
		client = MagicMock()
		client.get_reconciliation_case_status.return_value = {
			"data": {
				"ok": True,
				"status": "Found",
				"case": {
					"case_reference": "ceurc-rejected-001",
					"case_status": "Rejected",
					"decision": {
						"decision_reference": "CEURD-REJECTED",
						"decision_type": "Reject",
						"reason_code": "INVALID_EVIDENCE",
						"result_status": "Rejected",
						"result_reason_code": "INVALID_EVIDENCE",
						"applied_usage": False,
						"reconciliation_reference": "",
						"decided_on": "2026-10-01 20:31:00",
					},
				},
			}
		}
		mock_client_factory.return_value = client

		result = refresh_reconciliation_case_status(
			op.name,
			"Refresh the submitted evidence after platform review.",
		)

		self.assertTrue(result["ok"])
		self.assertEqual(result["status"], "Rejected")
		self.assertEqual(op.status, "Rejected")
		self.assertEqual(op.reconciliation_decision_type, "Reject")
		self.assertFalse(op.reconciliation_applied_usage)
		self.assertIsNone(op.reservation_reference)
		self.assertEqual(mock_event.call_args.kwargs["result"], "Rejected")

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_mismatched_coreedge_case_reference_fails_closed(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		_mock_attempt,
		mock_event,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-expected",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op
		client = MagicMock()
		client.get_reconciliation_case_status.return_value = {
			"data": {
				"ok": True,
				"case": {
					"case_reference": "ceurc-other",
					"case_status": "Resolved",
					"decision": {"decision_type": "Apply Usage"},
				},
			}
		}
		mock_client_factory.return_value = client

		result = refresh_reconciliation_case_status(
			op.name,
			"Verify the exact CoreEdge case identity before closure.",
		)

		self.assertFalse(result["ok"])
		self.assertEqual(op.status, "Needs Review")
		self.assertIn("different", op.last_error.lower())
		self.assertEqual(
			mock_event.call_args.kwargs["reason_code"],
			"COREDGE_RECONCILIATION_CASE_MISMATCH",
		)

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_invalid_coreedge_decision_pair_fails_closed(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		_mock_attempt,
		mock_event,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-invalid-pair",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op
		client = MagicMock()
		client.get_reconciliation_case_status.return_value = {
			"data": {
				"ok": True,
				"case": {
					"case_reference": "ceurc-invalid-pair",
					"case_status": "Resolved",
					"decision": {"decision_type": "Reject"},
				},
			}
		}
		mock_client_factory.return_value = client

		result = refresh_reconciliation_case_status(
			op.name,
			"Verify the authoritative decision contract before closure.",
		)

		self.assertFalse(result["ok"])
		self.assertEqual(op.status, "Needs Review")
		self.assertEqual(
			mock_event.call_args.kwargs["reason_code"],
			"COREDGE_RECONCILIATION_DECISION_INVALID",
		)

	@patch("retailedge.coreedge_sales_quota_reconciliation._write_review_event")
	@patch("retailedge.coreedge_sales_quota_reconciliation._next_review_attempt", return_value=1)
	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_remote_status_error_keeps_case_in_review(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
		_mock_attempt,
		mock_event,
	):
		op = self._operation(
			reconciliation_case_reference="ceurc-error",
			reconciliation_case_status="Open",
		)
		mock_get_operation.return_value = op
		client = MagicMock()
		client.get_reconciliation_case_status.side_effect = CoreEdgeRemoteUsageError(
			"COREDGE_REMOTE_USAGE_UNAVAILABLE"
		)
		mock_client_factory.return_value = client

		result = refresh_reconciliation_case_status(
			op.name,
			"Retry the platform status read after a service outage.",
		)

		self.assertFalse(result["ok"])
		self.assertEqual(op.status, "Needs Review")
		self.assertIn("UNAVAILABLE", op.last_error)
		self.assertEqual(mock_event.call_args.kwargs["result"], "Failed")

	@patch("retailedge.coreedge_sales_quota_reconciliation.get_remote_usage_client")
	@patch("retailedge.coreedge_sales_quota_reconciliation._get_scoped_operation")
	@patch("retailedge.coreedge_sales_quota_reconciliation._assert_reconciliation_operator")
	@patch("retailedge.coreedge_sales_quota_reconciliation._require_post")
	def test_terminal_local_case_status_returns_without_remote_call(
		self,
		_mock_post,
		_mock_operator,
		mock_get_operation,
		mock_client_factory,
	):
		op = self._operation(
			status="Resolved",
			reconciliation_case_reference="ceurc-terminal",
			reconciliation_case_status="Resolved",
			reconciliation_decision_type="Apply Usage",
		)
		mock_get_operation.return_value = op

		result = refresh_reconciliation_case_status(
			op.name,
			"Confirm the already-synchronized terminal review result.",
		)

		self.assertTrue(result["ok"])
		self.assertEqual(result["status"], "Resolved")
		mock_client_factory.assert_not_called()

	def test_report_and_form_surface_contracts_exist(self):
		report_center = Path(frappe.get_app_path("retailedge", "report_center.py")).read_text()
		form_js = Path(
			frappe.get_app_path(
				"retailedge",
				"retailedge",
				"doctype",
				"retailedge_coreedge_quota_operation",
				"retailedge_coreedge_quota_operation.js",
			)
		).read_text()
		self.assertIn("RetailEdge Sales Quota Reconciliation", report_center)
		self.assertIn("Retry CoreEdge Finalization", form_js)
		self.assertIn("Submit to CoreEdge Review", form_js)
		self.assertIn("Refresh CoreEdge Review Status", form_js)
		self.assertNotIn("RetailEdge Auditor\") || roles.has", form_js)


class SalesQuotaReconciliationPersistenceTests(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.delete(REVIEW_EVENT_DOCTYPE, {"quota_operation": ["like", "quota-review-%"]})
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "quota-review-%"]})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(REVIEW_EVENT_DOCTYPE, {"quota_operation": ["like", "quota-review-%"]})
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "quota-review-%"]})
		super().tearDown()

	def _operation(self, suffix: str = "one"):
		doc = frappe.get_doc(
			{
				"doctype": OPERATION_DOCTYPE,
				"operation_key": f"quota-review-{suffix}",
				"status": "Needs Review",
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"units": 1,
				"reservation_reference": None,
				"reserve_idempotency_key": f"reserve-{suffix}",
				"finalize_idempotency_key": f"finalize-{suffix}",
				"release_idempotency_key": f"release-{suffix}",
				"reason_code": "FAIL_OPEN_UNRESERVED",
				"reserved_on": now_datetime(),
			}
		)
		doc.flags.allow_retailedge_quota_operation_create = True
		return doc.insert(ignore_permissions=True)

	def test_normal_engine_update_cannot_attach_recovered_reservation(self):
		doc = self._operation("immutable")
		doc.status = "Pending Finalize"
		doc.reservation_reference = "CEUR-FORGED"
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_normal_engine_update_cannot_attach_reconciliation_case(self):
		doc = self._operation("case-immutable")
		doc.reconciliation_case_reference = "ceurc-forged"
		doc.reconciliation_case_status = "Open"
		doc.reconciliation_case_evidence_hash = "c" * 64
		doc.reconciliation_submitted_on = now_datetime()
		doc.reconciliation_last_idempotency_key = "case-submit-forged"
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_case_submission_flag_attaches_case_without_reopening_needs_review(self):
		doc = self._operation("case-governed")
		doc.reconciliation_case_reference = "ceurc-governed"
		doc.reconciliation_case_status = "Open"
		doc.reconciliation_case_evidence_hash = "d" * 64
		doc.reconciliation_submitted_on = now_datetime()
		doc.reconciliation_last_idempotency_key = "case-submit-governed"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_case_submission = True
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.status, "Needs Review")
		self.assertIsNone(doc.reservation_reference)
		self.assertEqual(doc.reconciliation_case_reference, "ceurc-governed")

	def test_normal_update_cannot_forge_coreedge_review_resolution(self):
		doc = self._operation("status-forged")
		doc.reconciliation_case_reference = "ceurc-status-forged"
		doc.reconciliation_case_status = "Open"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_case_submission = True
		doc.save(ignore_permissions=True)

		doc.status = "Resolved"
		doc.reconciliation_case_status = "Resolved"
		doc.reconciliation_decision_reference = "CEURD-FORGED"
		doc.reconciliation_decision_type = "Apply Usage"
		doc.reconciliation_applied_usage = 1
		doc.flags.allow_retailedge_quota_case_submission = False
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_case_status_sync_flag_can_close_needs_review_without_reservation(self):
		doc = self._operation("status-governed")
		doc.reconciliation_case_reference = "ceurc-status-governed"
		doc.reconciliation_case_status = "Open"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_case_submission = True
		doc.save(ignore_permissions=True)

		doc.status = "Resolved"
		doc.reconciliation_case_status = "Resolved"
		doc.reconciliation_last_checked_on = now_datetime()
		doc.reconciliation_decision_reference = "CEURD-GOVERNED"
		doc.reconciliation_decision_type = "Apply Usage"
		doc.reconciliation_result_status = "Recorded Historical"
		doc.reconciliation_result_reason_code = "HISTORICAL_USAGE_RECORDED"
		doc.reconciliation_applied_usage = 1
		doc.reconciliation_reference = "CEURC-USAGE-GOVERNED"
		doc.reconciliation_decided_on = now_datetime()
		doc.flags.allow_retailedge_quota_case_submission = False
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_case_status_sync = True
		doc.save(ignore_permissions=True)

		self.assertEqual(doc.status, "Resolved")
		self.assertIsNone(doc.reservation_reference)
		self.assertEqual(doc.reconciliation_decision_type, "Apply Usage")

	def test_reconciliation_flag_can_attach_reservation_and_reopen_needs_review(self):
		doc = self._operation("governed")
		doc.status = "Pending Finalize"
		doc.reservation_reference = "CEUR-GOVERNED"
		doc.reservation_expires_on = now_datetime()
		doc.reserve_idempotency_key = "review-reserve-governed"
		doc.finalize_idempotency_key = "review-finalize-governed"
		doc.release_idempotency_key = "review-release-governed"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_reconciliation = True
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.status, "Pending Finalize")
		self.assertEqual(doc.reservation_reference, "CEUR-GOVERNED")

	def test_review_event_is_engine_created_and_append_only(self):
		op = self._operation("event")
		forged = frappe.get_doc(
			{
				"doctype": REVIEW_EVENT_DOCTYPE,
				"quota_operation": op.name,
				"action": "Submit CoreEdge Review",
				"result": "Submitted",
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"reconciliation_case_reference": "ceurc-forged",
				"reason": "Manual forged event should be blocked.",
				"reviewed_on": now_datetime(),
				"reviewed_by": "Administrator",
			}
		)
		with self.assertRaises(frappe.PermissionError):
			forged.insert(ignore_permissions=True)

		event = frappe.get_doc(
			{
				"doctype": REVIEW_EVENT_DOCTYPE,
				"quota_operation": op.name,
				"action": "Submit CoreEdge Review",
				"result": "Submitted",
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"reconciliation_case_reference": "ceurc-governed",
				"reason": "Reviewed through governed reconciliation.",
				"reviewed_on": now_datetime(),
				"reviewed_by": "Administrator",
			}
		)
		event.flags.allow_retailedge_quota_review_event = True
		event.insert(ignore_permissions=True)
		event.message = "Attempted rewrite"
		with self.assertRaises(frappe.PermissionError):
			event.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(REVIEW_EVENT_DOCTYPE, event.name, ignore_permissions=True)


if __name__ == "__main__":
	unittest.main()
