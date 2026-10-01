from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from retailedge.coreedge_sales_quota import OPERATION_DOCTYPE
from retailedge.usage_reconciliation import (
	_decorate_row,
	_scope_filters,
	get_usage_reconciliation,
	retry_usage_finalization,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class UsageReconciliationContractTests(unittest.TestCase):
	def test_scope_filters_apply_company_and_selected_branch(self):
		filters = _scope_filters(
			{
				"company": "Demo Co",
				"branch": "Main",
				"restricted": True,
				"allowed_branches": ["Main", "East"],
			}
		)
		self.assertEqual(filters, {"company": "Demo Co", "branch": "Main"})

	def test_scope_filters_limit_blank_branch_to_allowed_branches_when_restricted(self):
		filters = _scope_filters(
			{
				"company": "Demo Co",
				"branch": "",
				"restricted": True,
				"allowed_branches": ["Main", "East"],
			}
		)
		self.assertEqual(filters["company"], "Demo Co")
		self.assertEqual(filters["branch"], ["in", ["Main", "East"]])

	def test_unreserved_needs_review_is_escalation_only(self):
		row = _decorate_row(
			{
				"status": "Needs Review",
				"reservation_reference": "",
				"reason_code": "FAIL_OPEN_UNRESERVED",
			},
			can_retry=True,
		)
		self.assertFalse(row["retry_allowed"])
		self.assertTrue(row["requires_platform_reconciliation"])
		self.assertIn("do not create a replacement", row["guidance"])

	def test_existing_reservation_can_be_retried_by_manager(self):
		row = _decorate_row(
			{
				"status": "Needs Review",
				"reservation_reference": "CEUR-001",
				"reason_code": "RESERVATION_EXPIRED",
			},
			can_retry=True,
		)
		self.assertTrue(row["retry_allowed"])
		self.assertFalse(row["requires_platform_reconciliation"])

	@patch("retailedge.usage_reconciliation._get_summary")
	@patch("retailedge.usage_reconciliation.frappe.get_list")
	@patch("retailedge.usage_reconciliation._resolve_scope")
	@patch("retailedge.usage_reconciliation._assert_review_access")
	@patch("retailedge.usage_reconciliation._can_retry", return_value=True)
	def test_queue_read_is_permission_aware_bounded_and_branch_scoped(
		self,
		_mock_can_retry,
		_mock_access,
		mock_scope,
		mock_get_list,
		mock_summary,
	):
		mock_scope.return_value = {
			"company": "Demo Co",
			"branch": "",
			"companies": ["Demo Co"],
			"branches": ["Main", "East"],
			"restricted": True,
			"allowed_branches": ["Main", "East"],
			"requires_company": False,
			"no_branch_access": False,
			"scope_source": "branch_assignment",
		}
		mock_get_list.return_value = [
			frappe._dict(
				name="op-one",
				status="Needs Review",
				source_doctype="Sales Invoice",
				source_name="SINV-001",
				company="Demo Co",
				branch="Main",
				reservation_reference="CEUR-001",
				reason_code="RESERVATION_EXPIRED",
			)
		]
		mock_summary.return_value = {
			"needs_review": 1,
			"pending_finalize": 0,
			"finalized": 0,
			"open": 1,
		}

		result = get_usage_reconciliation(
			{"company": "Demo Co", "status": "Needs Review"},
			page_length=500,
		)

		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["pagination"]["page_length"], 100)
		filters = mock_get_list.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "Demo Co")
		self.assertEqual(filters["branch"], ["in", ["Main", "East"]])
		self.assertEqual(filters["status"], "Needs Review")
		self.assertEqual(mock_get_list.call_args.kwargs["limit_page_length"], 101)

	@patch("retailedge.usage_reconciliation._assert_retry_access")
	@patch("retailedge.usage_reconciliation._assert_post")
	@patch("retailedge.usage_reconciliation._assert_operation_scope")
	@patch("retailedge.usage_reconciliation.frappe.get_doc")
	def test_unreserved_exception_cannot_create_post_fact_reservation(
		self,
		mock_get_doc,
		_mock_scope,
		_mock_post,
		_mock_access,
	):
		operation = SimpleNamespace(
			name="op-unreserved",
			status="Needs Review",
			reservation_reference=None,
			check_permission=MagicMock(),
		)
		mock_get_doc.return_value = operation
		with self.assertRaises(frappe.ValidationError):
			retry_usage_finalization("op-unreserved")

	@patch("retailedge.usage_reconciliation.finalize_sales_quota_operation")
	@patch("retailedge.usage_reconciliation._assert_retry_access")
	@patch("retailedge.usage_reconciliation._assert_post")
	@patch("retailedge.usage_reconciliation._assert_operation_scope")
	@patch("retailedge.usage_reconciliation.frappe.get_doc")
	def test_retry_uses_existing_reservation_and_governed_needs_review_path(
		self,
		mock_get_doc,
		_mock_scope,
		_mock_post,
		_mock_access,
		mock_finalize,
	):
		operation = SimpleNamespace(
			name="op-retry",
			status="Needs Review",
			reservation_reference="CEUR-retry",
			check_permission=MagicMock(),
		)
		refreshed = frappe._dict(
			name="op-retry",
			status="Finalized",
			source_doctype="Sales Invoice",
			source_name="SINV-001",
			company="Demo Co",
			branch="Main",
			entitlement_key="SALES_TRANSACTIONS",
			units=1,
			reservation_reference="CEUR-retry",
			reservation_expires_on=None,
			warning=0,
			reason_code="RESERVATION_ALREADY_FINALIZED",
			remote_message="Already finalized",
			reserved_on=None,
			finalized_on=now_datetime(),
			last_attempt_on=now_datetime(),
			attempt_count=2,
			last_error="",
			creation=None,
			modified=None,
		)
		refreshed.as_dict = lambda: dict(refreshed)
		mock_get_doc.side_effect = [operation, refreshed]
		mock_finalize.return_value = {"status": "Finalized"}

		result = retry_usage_finalization("op-retry")

		self.assertTrue(result["ok"])
		mock_finalize.assert_called_once_with(
			"op-retry",
			allow_needs_review_retry=True,
		)

	def test_source_contract_is_permission_aware_and_never_reserves_new_quota(self):
		source = (APP_ROOT / "usage_reconciliation.py").read_text()
		self.assertIn("frappe.get_list(", source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("reserve_usage(", source)
		self.assertIn("allow_needs_review_retry=True", source)
		self.assertIn("_assert_post()", source)


class UsageReconciliationLifecycleTests(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "recon-test-%"]})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "recon-test-%"]})
		super().tearDown()

	def _operation(self):
		doc = frappe.get_doc(
			{
				"doctype": OPERATION_DOCTYPE,
				"operation_key": "recon-test-one",
				"status": "Needs Review",
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"units": 1,
				"reservation_reference": "CEUR-recon-test",
				"reserve_idempotency_key": "reserve-recon-test",
				"finalize_idempotency_key": "finalize-recon-test",
				"release_idempotency_key": "release-recon-test",
				"reserved_on": now_datetime(),
			}
		)
		doc.flags.allow_retailedge_quota_operation_create = True
		return doc.insert(ignore_permissions=True)

	def test_needs_review_cannot_finalize_without_reconciliation_flag(self):
		doc = self._operation()
		doc.status = "Finalized"
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_reconciliation_service_can_finalize_needs_review(self):
		doc = self._operation()
		doc.status = "Finalized"
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.flags.allow_retailedge_quota_reconciliation = True
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.status, "Finalized")


if __name__ == "__main__":
	unittest.main()
