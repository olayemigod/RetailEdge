from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from retailedge.retailedge.report.retailedge_coreedge_quota_review import (
	retailedge_coreedge_quota_review as quota_report,
)


class CoreEdgeQuotaReviewReportTests(unittest.TestCase):
	def test_default_query_focuses_attention_rows(self):
		filters = frappe._dict({})
		query = quota_report._query_filters(filters)
		self.assertEqual(
			query["status"],
			["in", ["Pending Finalize", "Needs Review"]],
		)

	def test_explicit_status_overrides_attention_filter(self):
		filters = frappe._dict({"status": "Finalized", "needs_attention_only": 1})
		query = quota_report._query_filters(filters)
		self.assertEqual(query["status"], "Finalized")

	def test_company_branch_and_date_filters_are_applied(self):
		filters = frappe._dict(
			{
				"company": "Retail Co",
				"branch": "Ketu",
				"source_doctype": "Sales Invoice",
				"entitlement_key": "SALES_TRANSACTIONS",
				"from_date": "2026-10-01",
				"to_date": "2026-10-31",
			}
		)
		query = quota_report._query_filters(filters)
		self.assertEqual(query["company"], "Retail Co")
		self.assertEqual(query["branch"], "Ketu")
		self.assertEqual(query["source_doctype"], "Sales Invoice")
		self.assertEqual(query["entitlement_key"], "SALES_TRANSACTIONS")
		self.assertEqual(
			query["creation"],
			["between", ["2026-10-01 00:00:00", "2026-10-31 23:59:59"]],
		)

	def test_invalid_date_range_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			quota_report._validate_filters(
				frappe._dict({"from_date": "2026-10-31", "to_date": "2026-10-01"})
			)

	@patch.object(quota_report.frappe, "get_list")
	def test_data_query_is_permission_aware_bounded_and_actionable(self, mock_get_list):
		mock_get_list.return_value = [
			frappe._dict(
				name="quota-op-1",
				status="Pending Finalize",
				reason_code="",
				last_error="",
				creation="2026-10-01 10:00:00",
			)
		]
		rows, truncated = quota_report.get_data(frappe._dict({}))
		self.assertFalse(truncated)
		self.assertEqual(rows[0]["next_action"], "Retry Finalize")
		mock_get_list.assert_called_once()
		self.assertEqual(mock_get_list.call_args.kwargs["limit_page_length"], 1001)

	def test_next_action_classification(self):
		cases = [
			({"status": "Pending Finalize"}, "Retry Finalize"),
			({"status": "Finalized"}, "No action"),
			(
				{"status": "Needs Review", "reason_code": "FAIL_OPEN_UNRESERVED"},
				"Reconcile central usage",
			),
			(
				{"status": "Needs Review", "reason_code": "RESERVATION_EXPIRED"},
				"Platform review required",
			),
			(
				{"status": "Needs Review", "reason_code": "USAGE_RESERVATION_ACCESS_DENIED"},
				"Check Service Client access",
			),
			(
				{"status": "Needs Review", "last_error": "Source document is not submitted"},
				"Verify source document",
			),
		]
		for row, expected in cases:
			with self.subTest(row=row):
				self.assertEqual(quota_report.get_next_action(row), expected)

	def test_report_source_uses_get_list_not_get_all(self):
		source = Path(quota_report.__file__).read_text(encoding="utf-8")
		self.assertIn("frappe.get_list(", source)
		self.assertNotIn("frappe.get_all(", source)

	def test_report_ui_has_company_branch_cascade_and_manager_only_retry(self):
		js_path = Path(quota_report.__file__).with_suffix(".js")
		source = js_path.read_text(encoding="utf-8")
		self.assertIn('fieldname: "company"', source)
		self.assertIn('queryReport.set_filter_value("branch", "")', source)
		self.assertIn('filters: { company }', source)
		self.assertIn("canRetryCoreEdgeQuota()", source)
		self.assertIn('"RetailEdge Manager"', source)
		self.assertIn('"RetailEdgeManager"', source)
		self.assertIn("retry_sales_quota_finalize", source)

	def test_report_center_registers_quota_review_under_controls(self):
		source = Path(frappe.get_app_path("retailedge", "report_center.py")).read_text(
			encoding="utf-8"
		)
		self.assertIn('"label": "CoreEdge Quota Review"', source)
		self.assertIn('"target": "RetailEdge CoreEdge Quota Review"', source)
		self.assertIn('"native_desk": True', source)


class CoreEdgeQuotaReviewActionTests(unittest.TestCase):
	@patch("retailedge.coreedge_sales_quota.finalize_sales_quota_operation")
	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	@patch("retailedge.coreedge_sales_quota._assert_quota_review_operator")
	@patch("retailedge.coreedge_sales_quota._require_post")
	def test_pending_operation_can_be_retried(
		self,
		mock_post,
		mock_operator,
		mock_get_doc,
		mock_finalize,
	):
		operation = SimpleNamespace(
			name="quota-op-pending",
			status="Pending Finalize",
			check_permission=MagicMock(),
		)
		mock_get_doc.return_value = operation
		mock_finalize.return_value = {"status": "Finalized"}

		from retailedge.coreedge_sales_quota import retry_sales_quota_finalize

		result = retry_sales_quota_finalize("quota-op-pending")
		self.assertEqual(result["status"], "Finalized")
		operation.check_permission.assert_called_once_with("read")
		mock_finalize.assert_called_once_with("quota-op-pending")
		mock_post.assert_called_once()
		mock_operator.assert_called_once()

	@patch("retailedge.coreedge_sales_quota.frappe.get_doc")
	@patch("retailedge.coreedge_sales_quota._assert_quota_review_operator")
	@patch("retailedge.coreedge_sales_quota._require_post")
	def test_needs_review_operation_cannot_be_retried_as_pending(
		self,
		_mock_post,
		_mock_operator,
		mock_get_doc,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="quota-op-review",
			status="Needs Review",
			check_permission=MagicMock(),
		)
		from retailedge.coreedge_sales_quota import retry_sales_quota_finalize

		with self.assertRaises(frappe.ValidationError):
			retry_sales_quota_finalize("quota-op-review")


if __name__ == "__main__":
	unittest.main()
