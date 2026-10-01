from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from retailedge.coreedge_quota_review import (
	_build_filters,
	_review_reason,
	reconcile_unreserved_quota_operation,
	retry_quota_operation,
)
from retailedge.coreedge_sales_quota import OPERATION_DOCTYPE


class QuotaReviewServiceContractTests(unittest.TestCase):
	def _operation(self, **overrides):
		values = {
			"name": "quota-op-001",
			"operation_key": "quota-operation-review-001",
			"status": "Needs Review",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-REVIEW-001",
			"company": "Test Company",
			"branch": "Main",
			"entitlement_key": "SALES_TRANSACTIONS",
			"units": 1,
			"reservation_reference": None,
			"reservation_expires_on": None,
			"warning": 0,
			"reason_code": "FAIL_OPEN_UNRESERVED",
			"remote_message": "",
			"last_error": "",
			"review_action": "",
			"review_reason": "",
			"reviewed_by": "",
			"reviewed_on": None,
			"attempt_count": 0,
			"finalized_on": None,
		}
		values.update(overrides)
		return SimpleNamespace(**values)

	def test_review_reason_is_required_and_bounded(self):
		with self.assertRaises(frappe.ValidationError):
			_review_reason("x")
		with self.assertRaises(frappe.ValidationError):
			_review_reason("x" * 1001)
		self.assertEqual(_review_reason("Reviewed after connectivity recovery."), "Reviewed after connectivity recovery.")

	@patch("retailedge.coreedge_quota_review._write_review_event")
	@patch("retailedge.coreedge_quota_review._assert_mutation_access")
	@patch("retailedge.coreedge_quota_review._require_post")
	@patch("retailedge.coreedge_quota_review.frappe.get_doc")
	@patch("retailedge.coreedge_quota_review.finalize_sales_quota_operation")
	def test_pending_operation_retry_uses_normal_finalize(
		self,
		mock_finalize,
		mock_get_doc,
		_mock_post,
		_mock_access,
		_mock_event,
	):
		mock_get_doc.return_value = self._operation(status="Pending Finalize", reservation_reference="CEUR-1")
		mock_finalize.return_value = {"status": "Finalized"}
		result = retry_quota_operation("quota-op-001")
		self.assertTrue(result["ok"])
		mock_finalize.assert_called_once_with("quota-op-001")

	@patch("retailedge.coreedge_quota_review._assert_mutation_access")
	@patch("retailedge.coreedge_quota_review._require_post")
	@patch("retailedge.coreedge_quota_review.frappe.get_doc")
	def test_unreserved_needs_review_routes_to_reconciliation(
		self,
		mock_get_doc,
		_mock_post,
		_mock_access,
	):
		mock_get_doc.return_value = self._operation()
		result = retry_quota_operation("quota-op-001")
		self.assertFalse(result["ok"])
		self.assertEqual(result["reason_code"], "RECONCILIATION_RESERVATION_REQUIRED")

	@patch("retailedge.coreedge_quota_review._write_review_event")
	@patch("retailedge.coreedge_quota_review._assert_mutation_access")
	@patch("retailedge.coreedge_quota_review._require_post")
	@patch("retailedge.coreedge_quota_review.frappe.get_doc")
	@patch("retailedge.coreedge_quota_review.finalize_sales_quota_operation")
	def test_needs_review_retry_requires_reason_and_governed_flag(
		self,
		mock_finalize,
		mock_get_doc,
		_mock_post,
		_mock_access,
		_mock_event,
	):
		mock_get_doc.return_value = self._operation(reservation_reference="CEUR-2")
		with self.assertRaises(frappe.ValidationError):
			retry_quota_operation("quota-op-001", "x")

		mock_finalize.return_value = {"status": "Finalized"}
		result = retry_quota_operation(
			"quota-op-001",
			"Verified CoreEdge credentials and reservation ownership.",
		)
		self.assertTrue(result["ok"])
		kwargs = mock_finalize.call_args.kwargs
		self.assertTrue(kwargs["allow_needs_review"])
		self.assertEqual(kwargs["review_action"], "Retry CoreEdge Finalization")

	@patch("retailedge.coreedge_quota_review._record_review_failure")
	@patch("retailedge.coreedge_quota_review._source_docstatus", return_value=1)
	@patch("retailedge.coreedge_quota_review.get_remote_usage_client")
	@patch("retailedge.coreedge_quota_review.frappe.get_doc")
	@patch("retailedge.coreedge_quota_review._assert_mutation_access")
	@patch("retailedge.coreedge_quota_review._require_post")
	def test_unreserved_reconciliation_preserves_review_when_coreedge_blocks(
		self,
		_mock_post,
		_mock_access,
		mock_get_doc,
		mock_client,
		_mock_docstatus,
		mock_record_failure,
	):
		operation = self._operation()
		mock_get_doc.return_value = operation
		client = MagicMock()
		client.reserve_usage.return_value = {
			"data": {
				"ok": False,
				"reason_code": "LIMIT_EXCEEDED",
				"message": "Limit exceeded",
			}
		}
		mock_client.return_value = client

		result = reconcile_unreserved_quota_operation(
			operation.name,
			"Reconcile the committed fail-open sale.",
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["status"], "Needs Review")
		self.assertEqual(result["reason_code"], "LIMIT_EXCEEDED")
		mock_record_failure.assert_called_once()

	@patch("retailedge.coreedge_quota_review._write_review_event")
	@patch("retailedge.coreedge_quota_review.finalize_sales_quota_operation")
	@patch("retailedge.coreedge_quota_review._save_review_operation")
	@patch("retailedge.coreedge_quota_review._lock_operation")
	@patch("retailedge.coreedge_quota_review._source_docstatus", return_value=2)
	@patch("retailedge.coreedge_quota_review.get_remote_usage_client")
	@patch("retailedge.coreedge_quota_review.frappe.get_doc")
	@patch("retailedge.coreedge_quota_review._assert_mutation_access")
	@patch("retailedge.coreedge_quota_review._require_post")
	def test_unreserved_reconciliation_attaches_reservation_then_finalizes(
		self,
		_mock_post,
		_mock_access,
		mock_get_doc,
		mock_client,
		_mock_docstatus,
		_mock_lock,
		mock_save,
		mock_finalize,
		_mock_event,
	):
		operation = self._operation()
		mock_get_doc.return_value = operation
		client = MagicMock()
		client.reserve_usage.return_value = {
			"data": {
				"ok": True,
				"quota": {
					"status": "Active",
					"reservation_reference": "CEUR-RECONCILE",
					"expires_on": "2026-10-01 02:00:00",
					"reason_code": "WITHIN_LIMIT",
					"message": "Reserved",
				}
			}
		}
		mock_client.return_value = client
		mock_finalize.return_value = {"status": "Finalized"}

		result = reconcile_unreserved_quota_operation(
			operation.name,
			"Approved post-factum quota reconciliation.",
		)
		self.assertTrue(result["ok"])
		self.assertEqual(operation.reservation_reference, "CEUR-RECONCILE")
		mock_save.assert_called_once()
		self.assertTrue(mock_save.call_args.kwargs["reconciliation"])
		self.assertTrue(mock_finalize.call_args.kwargs["allow_needs_review"])

	@patch("retailedge.coreedge_quota_review._record_review_failure")
	@patch("retailedge.coreedge_quota_review._source_docstatus", return_value=0)
	@patch("retailedge.coreedge_quota_review.frappe.get_doc")
	@patch("retailedge.coreedge_quota_review._assert_mutation_access")
	@patch("retailedge.coreedge_quota_review._require_post")
	def test_unreserved_reconciliation_refuses_unsubmitted_source(
		self,
		_mock_post,
		_mock_access,
		mock_get_doc,
		_mock_docstatus,
		mock_record_failure,
	):
		operation = self._operation()
		mock_get_doc.return_value = operation
		result = reconcile_unreserved_quota_operation(
			operation.name,
			"Review source transaction state.",
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["reason_code"], "SOURCE_NOT_SUBMITTED")
		mock_record_failure.assert_called_once()

	@patch("retailedge.coreedge_quota_review.get_operational_branch_scope")
	def test_restricted_zero_branch_scope_fails_closed(self, mock_scope):
		mock_scope.return_value = {
			"restricted": True,
			"allowed_branches": [],
		}
		with self.assertRaises(frappe.PermissionError):
			_build_filters(
				frappe._dict(
					{
						"status": "Open",
						"company": "Test Company",
						"branch": "Main",
					}
				)
			)

	@patch("retailedge.coreedge_quota_review.get_operational_branch_scope")
	def test_unrestricted_branch_scope_allows_explicit_branch_filter(self, mock_scope):
		mock_scope.return_value = {
			"restricted": False,
			"allowed_branches": [],
		}
		filters, _scope, _or_filters = _build_filters(
			frappe._dict(
				{
					"status": "Open",
					"company": "Test Company",
					"branch": "Main",
				}
			)
		)
		self.assertIn(
			[OPERATION_DOCTYPE, "branch", "=", "Main"],
			filters,
		)

	def test_review_service_uses_permission_aware_get_list_only(self):
		source = Path(
			frappe.get_app_path("retailedge", "coreedge_quota_review.py")
		).read_text()
		self.assertIn("frappe.get_list(", source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertIn("_assert_read_access()", source)
		self.assertIn("_assert_mutation_access()", source)
		self.assertIn("_require_post()", source)

	def test_review_page_is_edgesuite_owned_and_has_no_direct_doc_writes(self):
		root = Path(frappe.get_app_path("retailedge"))
		loader = (
			root
			/ "retailedge"
			/ "page"
			/ "quota_operations_review"
			/ "quota_operations_review.js"
		).read_text()
		component = (
			root / "public" / "js" / "coreedge_quota_review" / "CoreEdgeQuotaReview.vue"
		).read_text()
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', loader)
		self.assertIn('const REVIEW_ASSET = "coreedge_quota_review.bundle.js"', loader)
		self.assertIn("<EdgeAppShell", component)
		self.assertIn("retailedge.coreedge_quota_review.list_quota_operations", component)
		self.assertIn("Attempt Reconciliation", component)
		self.assertNotIn("frappe.db.set_value", component)
		self.assertNotIn("frappe.client.set_value", component)

	def test_workspace_and_sidebar_place_review_under_operations_review(self):
		root = Path(frappe.get_app_path("retailedge"))
		workspace = json.loads(
			(root / "retailedge" / "workspace" / "retailedge" / "retailedge.json").read_text()
		)
		links = workspace["links"]
		section = next(
			i for i, row in enumerate(links)
			if row.get("type") == "Card Break" and row.get("label") == "Operations Review"
		)
		quota = next(i for i, row in enumerate(links) if row.get("link_to") == "quota-operations-review")
		self.assertGreater(quota, section)
		self.assertEqual(links[section]["link_count"], 5)

		sidebar = json.loads(
			(
				root
				/ "retailedge"
				/ "workspace_sidebar"
				/ "retailedge"
				/ "retailedge.json"
			).read_text()
		)
		items = sidebar["items"]
		daily = next(i for i, row in enumerate(items) if row.get("link_to") == "daily-sales-audit")
		quota_side = next(
			i for i, row in enumerate(items)
			if row.get("link_to") == "quota-operations-review"
		)
		self.assertEqual(quota_side, daily + 1)

	def test_auditors_can_view_page_but_are_not_mutation_roles(self):
		root = Path(frappe.get_app_path("retailedge"))
		page = json.loads(
			(
				root
				/ "retailedge"
				/ "page"
				/ "quota_operations_review"
				/ "quota_operations_review.json"
			).read_text()
		)
		roles = {row["role"] for row in page["roles"]}
		self.assertIn("RetailEdge Auditor", roles)
		self.assertIn("RetailEdgeAuditor", roles)
		source = (root / "coreedge_quota_review.py").read_text()
		mutation_block = source.split("_MUTATION_ROLES =", 1)[1].split("}", 1)[0]
		self.assertNotIn("RetailEdge Auditor", mutation_block)
		self.assertNotIn("RetailEdgeAuditor", mutation_block)


class QuotaReviewLifecycleTests(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.delete(
			"RetailEdge CoreEdge Quota Review Event",
			{"event_key": ["like", "quota-review-event-%"]},
		)
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "quota-review-%"]})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "quota-review-%"]})
		super().tearDown()

	def _make_needs_review(self, suffix: str):
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

	def test_reservation_cannot_be_attached_by_ordinary_engine_update(self):
		doc = self._make_needs_review("ordinary-attach")
		doc.reservation_reference = "CEUR-FORGED"
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_governed_review_can_attach_reservation_once(self):
		doc = self._make_needs_review("governed-attach")
		doc.reservation_reference = "CEUR-GOVERNED"
		doc.reservation_expires_on = add_to_date(now_datetime(), minutes=30)
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_operation_reconcile = True
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.reservation_reference, "CEUR-GOVERNED")

		doc.reservation_reference = "CEUR-REWRITE"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_operation_reconcile = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_review_event_is_engine_created_and_append_only(self):
		operation = self._make_needs_review("event-history")
		event = frappe.get_doc(
			{
				"doctype": "RetailEdge CoreEdge Quota Review Event",
				"event_key": "quota-review-event-history",
				"quota_operation": operation.name,
				"action": "Attempt Reconciliation",
				"result_status": "Needs Review",
				"source_doctype": operation.source_doctype,
				"source_name": operation.source_name,
				"reason": "Operator reviewed the failed quota reconciliation.",
				"actor": "Administrator",
				"occurred_on": now_datetime(),
			}
		)
		with self.assertRaises(frappe.PermissionError):
			event.insert(ignore_permissions=True)

		event.flags.allow_retailedge_quota_review_event_create = True
		event.insert(ignore_permissions=True)
		event.message = "Attempted rewrite"
		with self.assertRaises(frappe.PermissionError):
			event.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(
				"RetailEdge CoreEdge Quota Review Event",
				event.name,
				ignore_permissions=True,
			)

	def test_needs_review_can_finalize_only_through_reconciliation_flag(self):
		doc = self._make_needs_review("status-transition")
		doc.reservation_reference = "CEUR-STATUS"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_operation_reconcile = True
		doc.save(ignore_permissions=True)

		doc.status = "Finalized"
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

		doc.status = "Finalized"
		doc.finalized_on = now_datetime()
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_operation_reconcile = True
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.status, "Finalized")


if __name__ == "__main__":
	unittest.main()
