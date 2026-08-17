from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.expense_register import (
	MAX_DATE_RANGE_DAYS,
	MAX_EXPORT_ROWS,
	MAX_LINK_RESULTS,
	MAX_PAGE_SIZE,
	_build_query_filters,
	_can_view_other_cashiers,
	get_expense_register,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestExpenseRegister(unittest.TestCase):
	@patch("retailedge.expense_register._assert_company_read_access")
	@patch("retailedge.expense_register._assert_expense_read_access")
	@patch("retailedge.expense_register.validate_user_branch_access")
	@patch("retailedge.expense_register.get_branch_query_filters")
	@patch("retailedge.expense_register._can_view_other_cashiers", return_value=False)
	@patch("retailedge.expense_register.frappe.defaults.get_user_default")
	def test_cashier_scope_is_forced_to_current_user(
		self,
		mock_default,
		_mock_cashier_visibility,
		mock_branch_scope,
		_mock_branch_access,
		_mock_expense_access,
		_mock_company_access,
	):
		mock_default.return_value = "Demo Company"
		mock_branch_scope.return_value = {"filters": {"branch": "Lagos"}}
		original_user = frappe.session.user
		try:
			frappe.session.user = "cashier@example.com"
			filters = _build_query_filters(
				frappe._dict(
					company="Demo Company",
					branch="Lagos",
					from_date="2026-08-01",
					to_date="2026-08-17",
				)
			)
		finally:
			frappe.session.user = original_user
		self.assertEqual(filters["cashier"], "cashier@example.com")
		self.assertEqual(filters["branch"], "Lagos")
		self.assertEqual(filters["company"], "Demo Company")
		self.assertEqual(filters["docstatus"], ["!=", 2])

	@patch("retailedge.expense_register._assert_company_read_access")
	@patch("retailedge.expense_register._assert_expense_read_access")
	@patch("retailedge.expense_register.get_branch_query_filters")
	@patch("retailedge.expense_register._can_view_other_cashiers", return_value=True)
	def test_date_range_is_bounded(
		self,
		_mock_cashier_visibility,
		mock_branch_scope,
		_mock_expense_access,
		_mock_company_access,
	):
		mock_branch_scope.return_value = {"filters": {}}
		with self.assertRaises(frappe.ValidationError):
			_build_query_filters(
				frappe._dict(
					company="Demo Company",
					from_date="2025-01-01",
					to_date="2026-08-17",
				)
			)

	@patch("retailedge.expense_register._build_query_filters", return_value={"company": "Demo Company"})
	@patch("retailedge.expense_register._can_view_other_cashiers", return_value=False)
	@patch("retailedge.expense_register._get_summary")
	@patch("retailedge.expense_register.frappe.get_list")
	def test_register_clamps_page_size_and_omits_cashier_identity(
		self,
		mock_get_list,
		mock_summary,
		_mock_cashier_visibility,
		_mock_filters,
	):
		mock_summary.return_value = {
			"count": 1,
			"total_amount": 500,
			"submitted_count": 1,
			"posting_blocked_count": 0,
		}
		mock_get_list.return_value = [
			frappe._dict(
				name="RE-CE-1",
				expense_date="2026-08-17",
				branch="Lagos",
				expense_category="Fuel",
				amount=500,
				expense_status="Submitted",
				ledger_status="Not Applicable",
				posting_ready=1,
				description="Fuel",
				docstatus=1,
			)
		]
		result = get_expense_register(filters={"company": "Demo Company"}, page=1, page_size=500)
		self.assertEqual(result["pagination"]["page_size"], MAX_PAGE_SIZE)
		self.assertEqual(mock_get_list.call_args.kwargs["limit_page_length"], MAX_PAGE_SIZE)
		self.assertNotIn("cashier", mock_get_list.call_args.kwargs["fields"])
		self.assertNotIn("cashier", result["rows"][0])
		for sensitive in (
			"payment_account",
			"expense_account",
			"cost_center",
			"approved_by",
			"rejected_by",
			"linked_pos_opening_shift",
			"linked_pos_closing_shift",
		):
			self.assertNotIn(sensitive, result["rows"][0])

	@patch("retailedge.expense_register.frappe.get_roles")
	def test_cashier_only_role_does_not_receive_other_cashier_visibility(self, mock_roles):
		mock_roles.return_value = ["RetailEdge Cashier"]
		self.assertFalse(_can_view_other_cashiers("cashier@example.com"))
		mock_roles.return_value = ["RetailEdge Branch Manager"]
		self.assertTrue(_can_view_other_cashiers("manager@example.com"))

	def test_performance_limits_are_explicit(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_PAGE_SIZE, 100)
		self.assertEqual(MAX_EXPORT_ROWS, 5000)
		self.assertEqual(MAX_DATE_RANGE_DAYS, 366)

	def test_backend_uses_permission_aware_bounded_queries(self):
		source = (APP_ROOT / "expense_register.py").read_text()
		self.assertIn("frappe.get_list(", source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertIn("limit_page_length=page_size", source)
		self.assertIn("limit_page_length=MAX_EXPORT_ROWS + 1", source)
		self.assertIn("strict=True", source)
		self.assertIn('query_filters["cashier"] = frappe.session.user', source)
		self.assertNotIn('"payment_account"', source)
		self.assertNotIn('"approved_by"', source)

	def test_frontend_uses_shared_report_shell_with_server_search_and_provider_pagination(self):
		component = (
			APP_ROOT / "public" / "js" / "expense_register" / "ExpenseRegisterReport.vue"
		).read_text()
		self.assertIn("EdgeAppShell", component)
		self.assertIn("EdgeReportShell", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("EdgeExportMenu", component)
		self.assertIn("search_expense_register_options", component)
		self.assertIn('const REPORT_KEY = "expense-register"', component)
		self.assertIn("reportProvider.load", component)
		self.assertIn(':pageSizes="[25, 50, 100]"', component)
		self.assertIn("Expense Category", component)
		self.assertIn("Cashier view is limited to your own expenses", component)
		self.assertIn("this.filters.expense_category = \"\"", component)
		self.assertIn('frappe.new_doc("RetailEdge Cashier Expense")', component)
		self.assertIn('frappe.set_route("Form", "RetailEdge Cashier Expense", name)', component)
		self.assertNotIn("<table", component)
		self.assertNotIn("pagination-footer", component)
		self.assertNotIn("localStorage", component)
		self.assertNotIn("sessionStorage", component)

	def test_expense_register_registers_edgesuite_paginated_provider_and_mounts_report_consumer(self):
		bundle = (APP_ROOT / "public" / "js" / "expense_register.bundle.js").read_text()
		self.assertIn('ExpenseRegisterReport from "./expense_register/ExpenseRegisterReport.vue"', bundle)
		self.assertIn('const REPORT_PRODUCT = "RetailEdge"', bundle)
		self.assertIn('const REPORT_KEY = "expense-register"', bundle)
		self.assertIn("createPaginatedReportProvider", bundle)
		self.assertIn("registerProvider(REPORT_PRODUCT, REPORT_KEY", bundle)
		self.assertIn("defaultPageLength: 50", bundle)
		self.assertIn("maxPageLength: 100", bundle)
		self.assertIn("get_expense_register", bundle)
		self.assertIn("get_expense_register_export", bundle)
		self.assertIn("createEdgeApp(ExpenseRegisterReport)", bundle)
		self.assertNotIn("for (let page", bundle)
		self.assertNotIn("setInterval(", bundle)

	def test_page_uses_single_edgesuite_shell(self):
		page = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "expense_register"
			/ "expense_register.js"
		).read_text()
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', page)
		self.assertIn('const EXPENSE_REGISTER_ASSET = "expense_register.bundle.js"', page)
		self.assertIn("hideNativePageSidebar", page)
		self.assertIn("window.mountExpenseRegister", page)


if __name__ == "__main__":
	unittest.main()
