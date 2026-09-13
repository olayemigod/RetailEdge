from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import frappe

from retailedge import cashier_expense_audit, expense_review
from retailedge.retailedge.report.retailedge_cashier_expense_review import (
	retailedge_cashier_expense_review as report,
)


class TestPrereportingCashierExpenseReviewScope(unittest.TestCase):
	def test_native_report_delegates_to_hardened_cashier_expense_authority(self):
		source = inspect.getsource(report)
		self.assertIn("get_cashier_expenses_for_daily_audit", source)
		self.assertNotIn("get_branch_query_filters", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_native_report_passes_company_and_branch_selection_unchanged(self):
		filters = frappe._dict(company="Scope Co", branch="Branch B", posting_ready="")
		with patch.object(report, "get_cashier_expenses_for_daily_audit", return_value=[]) as get_rows:
			report.get_data(filters)

		get_rows.assert_called_once_with(filters=filters)
		self.assertEqual(filters, {"company": "Scope Co", "branch": "Branch B", "posting_ready": ""})

	def test_authoritative_engine_applies_current_reader_scope_before_get_all(self):
		source = inspect.getsource(cashier_expense_audit._build_daily_audit_filters)
		self.assertIn("apply_cashier_expense_read_scope", source)
		self.assertNotIn("get_branch_query_filters", source)

	def test_page_and_export_share_one_scoped_dataset_builder(self):
		for endpoint in (expense_review.get_expense_review, expense_review.get_expense_review_export):
			self.assertIn("_build_expense_review_dataset", inspect.getsource(endpoint))
		self.assertIn(
			"get_cashier_expenses_for_daily_audit",
			inspect.getsource(expense_review._build_expense_review_dataset),
		)

	def test_review_mutations_are_not_rewired_through_read_scope(self):
		for action in (
			expense_review.apply_expense_review_action,
			cashier_expense_audit.mark_cashier_expense_included_for_daily_audit,
			cashier_expense_audit.mark_cashier_expense_excluded_from_daily_audit,
			cashier_expense_audit.mark_cashier_expense_needs_clarification,
		):
			self.assertNotIn("apply_cashier_expense_read_scope", inspect.getsource(action))


if __name__ == "__main__":
	unittest.main()
