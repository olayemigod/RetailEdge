from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	get_sales_quota_review,
	retry_sales_quota_review,
)


class UsageReconciliationApiTests(unittest.TestCase):
	@patch("retailedge.coreedge_sales_quota.frappe.session")
	@patch("retailedge.coreedge_sales_quota.frappe.get_roles")
	@patch("retailedge.coreedge_sales_quota.frappe.get_list")
	def test_auditor_can_read_but_cannot_retry(
		self,
		mock_get_list,
		mock_get_roles,
		mock_session,
	):
		mock_session.user = "auditor@example.com"
		mock_get_roles.return_value = ["RetailEdge Auditor"]
		mock_get_list.return_value = [
			frappe._dict(
				name="op-review",
				status="Needs Review",
				source_doctype="Sales Invoice",
				source_name="SINV-001",
				company="Test Company",
				branch="Main",
				entitlement_key="SALES_TRANSACTIONS",
				units=1,
				reservation_reference="CEUR-001",
				attempt_count=1,
			)
		]

		payload = get_sales_quota_review()

		self.assertFalse(payload["can_manage"])
		self.assertFalse(payload["rows"][0]["can_retry"])
		self.assertFalse(payload["rows"][0]["requires_manual_reconciliation"])

	@patch("retailedge.coreedge_sales_quota.frappe.session")
	@patch("retailedge.coreedge_sales_quota.frappe.get_roles")
	@patch("retailedge.coreedge_sales_quota.frappe.get_list")
	def test_manager_sees_retry_only_when_reservation_exists(
		self,
		mock_get_list,
		mock_get_roles,
		mock_session,
	):
		mock_session.user = "manager@example.com"
		mock_get_roles.return_value = ["RetailEdge Manager"]
		mock_get_list.return_value = [
			frappe._dict(
				name="op-reserved",
				status="Needs Review",
				source_doctype="Sales Invoice",
				source_name="SINV-001",
				reservation_reference="CEUR-001",
				entitlement_key="SALES_TRANSACTIONS",
				attempt_count=1,
			),
			frappe._dict(
				name="op-unreserved",
				status="Needs Review",
				source_doctype="Sales Invoice",
				source_name="SINV-002",
				reservation_reference=None,
				entitlement_key="SALES_TRANSACTIONS",
				attempt_count=0,
			),
		]

		payload = get_sales_quota_review()

		self.assertTrue(payload["can_manage"])
		self.assertTrue(payload["rows"][0]["can_retry"])
		self.assertFalse(payload["rows"][0]["requires_manual_reconciliation"])
		self.assertFalse(payload["rows"][1]["can_retry"])
		self.assertTrue(payload["rows"][1]["requires_manual_reconciliation"])

	@patch("retailedge.coreedge_sales_quota.frappe.session")
	@patch("retailedge.coreedge_sales_quota.frappe.get_roles")
	def test_non_review_role_is_denied(self, mock_get_roles, mock_session):
		mock_session.user = "cashier@example.com"
		mock_get_roles.return_value = ["Sales User"]
		with self.assertRaises(frappe.PermissionError):
			get_sales_quota_review()

	@patch("retailedge.coreedge_sales_quota.finalize_sales_quota_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	@patch("retailedge.coreedge_sales_quota.frappe.session")
	@patch("retailedge.coreedge_sales_quota.frappe.get_roles")
	def test_manager_retry_calls_governed_finalize_with_review_override(
		self,
		mock_get_roles,
		mock_session,
		mock_get_doc,
		mock_finalize,
	):
		mock_session.user = "manager@example.com"
		mock_get_roles.return_value = ["RetailEdge Manager"]
		operation = MagicMock()
		operation.name = "op-review"
		operation.status = "Needs Review"
		operation.reservation_reference = "CEUR-001"
		mock_get_doc.return_value = operation
		mock_finalize.return_value = {"name": operation.name, "status": "Finalized"}

		result = retry_sales_quota_review(operation.name)

		self.assertEqual(result["status"], "Finalized")
		operation.check_permission.assert_called_once_with("read")
		mock_finalize.assert_called_once_with(
			operation.name,
			allow_review_retry=True,
		)

	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	@patch("retailedge.coreedge_sales_quota.frappe.session")
	@patch("retailedge.coreedge_sales_quota.frappe.get_roles")
	def test_unreserved_review_cannot_retry(
		self,
		mock_get_roles,
		mock_session,
		mock_get_doc,
	):
		mock_session.user = "manager@example.com"
		mock_get_roles.return_value = ["RetailEdge Manager"]
		operation = MagicMock()
		operation.name = "op-unreserved"
		operation.status = "Needs Review"
		operation.reservation_reference = None
		mock_get_doc.return_value = operation

		with self.assertRaises(frappe.ValidationError):
			retry_sales_quota_review(operation.name)

	def test_review_query_source_uses_permission_aware_get_list(self):
		source = Path(
			frappe.get_app_path("retailedge", "coreedge_sales_quota.py")
		).read_text()
		start = source.index("def get_sales_quota_review")
		end = source.index("def retry_sales_quota_review", start)
		section = source[start:end]
		self.assertIn("frappe.get_list(", section)
		self.assertNotIn("frappe.get_all(", section)


class UsageReconciliationOperationTests(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "review-op-%"]})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete(OPERATION_DOCTYPE, {"operation_key": ["like", "review-op-%"]})
		super().tearDown()

	def _operation(self, *, status="Needs Review", reservation="CEUR-REVIEW"):
		doc = frappe.get_doc(
			{
				"doctype": OPERATION_DOCTYPE,
				"operation_key": f"review-op-{frappe.generate_hash(length=8)}",
				"status": status,
				"source_doctype": "User",
				"source_name": "Administrator",
				"entitlement_key": "SALES_TRANSACTIONS",
				"units": 1,
				"reservation_reference": reservation,
				"reserve_idempotency_key": "review-reserve",
				"finalize_idempotency_key": "review-finalize",
				"release_idempotency_key": "review-release",
				"reserved_on": now_datetime(),
			}
		)
		doc.flags.allow_retailedge_quota_operation_create = True
		return doc.insert(ignore_permissions=True)

	def test_needs_review_can_finalize_only_through_engine_flag(self):
		doc = self._operation()
		doc.status = "Finalized"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

		doc.reload()
		doc.status = "Finalized"
		doc.finalized_on = now_datetime()
		doc.flags.allow_retailedge_quota_operation_update = True
		doc.save(ignore_permissions=True)
		self.assertEqual(doc.status, "Finalized")

	def test_needs_review_cannot_return_to_pending(self):
		doc = self._operation()
		doc.status = "Pending Finalize"
		doc.flags.allow_retailedge_quota_operation_update = True
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)


class UsageReconciliationPageContractTests(unittest.TestCase):
	def test_page_roles_are_governance_only(self):
		page = frappe.get_app_path(
			"retailedge",
			"retailedge",
			"page",
			"usage_reconciliation",
			"usage_reconciliation.json",
		)
		import json

		data = json.loads(Path(page).read_text())
		roles = {row["role"] for row in data["roles"]}
		self.assertEqual(
			roles,
			{
				"System Manager",
				"RetailEdge Manager",
				"RetailEdgeManager",
				"RetailEdge Auditor",
				"RetailEdgeAuditor",
			},
		)

	def test_page_exposes_retry_but_no_manual_status_override(self):
		page = Path(
			frappe.get_app_path(
				"retailedge",
				"retailedge",
				"page",
				"usage_reconciliation",
				"usage_reconciliation.js",
			)
		).read_text()
		self.assertIn("retry_sales_quota_review", page)
		self.assertIn("Manual commercial reconciliation is required", page)
		self.assertNotIn("Mark Resolved", page)
		self.assertNotIn("frappe.db.set_value", page)

	def test_review_navigation_contains_usage_reconciliation(self):
		source = Path(
			frappe.get_app_path("retailedge", "edgesuite_ui.py")
		).read_text()
		self.assertIn('"label": "Usage Reconciliation"', source)
		self.assertIn('"target": "usage-reconciliation"', source)


if __name__ == "__main__":
	unittest.main()
