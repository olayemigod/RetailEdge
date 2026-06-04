from __future__ import annotations

import json
import pathlib
import unittest
from unittest.mock import patch

import frappe

from retailedge.branch_performance import (
	debug_branch_performance_cashier_filter,
	get_branch_performance_debug_summary,
	get_branch_payment_breakdown,
	get_branch_performance_rows,
	get_branch_performance_summary,
	get_branch_sales_summary,
	resolve_sales_invoice_cashier,
)
from retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary import (
	execute as execute_branch_performance_report,
	validate_filters,
)


class BranchPerformanceTests(unittest.TestCase):
	REPORT_JS_PATH = pathlib.Path(
		"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_branch_performance_summary/retailedge_branch_performance_summary.js"
	)

	def test_report_imports_cleanly(self):
		self.assertTrue(callable(execute_branch_performance_report))

	def test_report_js_does_not_access_branch_company_from_client_side_filters(self):
		script = self.REPORT_JS_PATH.read_text(encoding="utf-8")
		branch_block = script.split('fieldname: "branch"', 1)[1].split('fieldname: "pos_profile"', 1)[0]
		self.assertNotIn("get_query()", branch_block)
		self.assertNotIn("{ filters: { company } }", branch_block)

	def test_report_js_default_filters_are_safe_for_first_load(self):
		script = self.REPORT_JS_PATH.read_text(encoding="utf-8")
		self.assertIn('fieldname: "from_date"', script)
		self.assertIn('default: frappe.datetime.month_start()', script)
		self.assertIn('fieldname: "to_date"', script)
		self.assertIn('default: frappe.datetime.get_today()', script)
		self.assertIn('fieldname: "only_pos_invoices"', script)
		self.assertIn("default: 0", script)
		self.assertIn('fieldname: "include_unattributed"', script)


	def test_report_js_refreshes_when_filters_change(self):
		script = self.REPORT_JS_PATH.read_text(encoding="utf-8")
		self.assertIn("configureOperationalReportRefresh(report);", script)
		self.assertIn("report.ignore_prepared_report = true;", script)
		self.assertIn("forceOperationalPrimaryAction(report);", script)
		self.assertIn("Refresh Report", script)
		self.assertIn("filter.on_change = function", script)
		self.assertIn("report.refresh();", script)

	def test_branch_performance_report_disables_prepared_report_mode(self):
		report_json_path = pathlib.Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_branch_performance_summary/retailedge_branch_performance_summary.json"
		)
		report_json = json.loads(report_json_path.read_text(encoding="utf-8"))
		self.assertEqual(report_json.get("disable_prepared_report"), 1)

	def test_validate_filters_raises_on_invalid_range(self):
		with self.assertRaises(Exception):
			validate_filters(frappe._dict({"from_date": "2026-05-31", "to_date": "2026-05-01"}))

	def test_validate_filters_raises_on_too_wide_live_range(self):
		with self.assertRaises(Exception):
			validate_filters(frappe._dict({"from_date": "2026-01-01", "to_date": "2026-05-31"}))

	@patch("retailedge.branch_performance.resolve_branch_from_opening_shift")
	def test_resolve_sales_invoice_cashier_prefers_pos_opening_shift_user_over_owner(self, mock_shift):
		mock_shift.return_value = {"cashier": "cashier1@example.com", "messages": []}
		result = resolve_sales_invoice_cashier(
			{
				"owner": "Guest",
				"posa_pos_opening_shift": "POSA-OS-001",
				"company": "Process Edge (Demo)",
			}
		)
		self.assertEqual(result["cashier"], "cashier1@example.com")
		self.assertEqual(result["source"], "POS Opening Shift.user")

	def test_resolve_sales_invoice_cashier_falls_back_to_owner_when_no_stronger_source_exists(self):
		result = resolve_sales_invoice_cashier({"owner": "Guest"})
		self.assertEqual(result["cashier"], "Guest")
		self.assertEqual(result["source"], "Sales Invoice.owner")

	@patch("retailedge.branch_performance._resolve_branch_scope", return_value={"filters": frappe._dict({"company": "Process Edge (Demo)", "from_date": "2026-05-01", "to_date": "2026-05-31", "branch": "HQ", "only_pos_invoices": 1, "include_unattributed": 0, "include_fallback_branch_resolution": 0}), "messages": [], "allowed_branches": []})
	@patch("retailedge.branch_performance.get_branch_stock_activity_summary", return_value={"by_branch": {"HQ": {"material_request_count": 1, "stock_entry_count": 1}}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_variance_summary", return_value={"by_branch": {"HQ": {"expected_cash": 900.0, "actual_closing_cash": 950.0, "audit_variance": 50.0, "daily_audit_count": 1, "pending_audit_count": 0, "approved_audit_count": 1, "high_variance_count": 0}}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_expense_summary", return_value={"by_branch": {"HQ": {"cashier_expenses": 100.0, "cashier_expense_count": 1}}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_payment_breakdown", return_value={"by_branch": {"HQ": {"Cash": 1000.0, "Bank Transfer": 200.0, "Card / POS": 0.0, "Mobile Money": 0.0, "Other": 0.0}}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_sales_summary", return_value={"by_branch": {"HQ": {"invoice_count": 2, "gross_sales": 1200.0, "net_total": 1150.0, "outstanding_amount": 200.0, "paid_amount": 1000.0, "paid_invoice_count": 1, "partially_paid_invoice_count": 0, "outstanding_invoice_count": 1, "unattributed_invoice_count": 0}}, "messages": []})
	def test_get_branch_performance_summary_builds_read_only_summary(
		self,
		_mock_sales,
		_mock_payments,
		_mock_expenses,
		_mock_variance,
		_mock_stock,
		_mock_scope,
	):
		summary = get_branch_performance_summary({"company": "Process Edge (Demo)", "branch": "HQ"})
		self.assertEqual(summary["branch"], "HQ")
		self.assertEqual(summary["gross_sales"], 1200.0)
		self.assertEqual(summary["cash_sales"], 1000.0)
		self.assertEqual(summary["cashier_expenses"], 100.0)
		self.assertEqual(summary["net_cash_expected"], 900.0)
		self.assertEqual(summary["audit_variance"], 50.0)
		self.assertEqual(summary["review_status"], "Needs Review")

	@patch("retailedge.branch_performance.get_branch_performance_rows")
	def test_get_branch_performance_summary_aggregates_all_rows_when_branch_not_selected(self, mock_rows):
		mock_rows.return_value = [
			{"branch": "Airport Branch", "period": "2026-05-01 to 2026-05-31", "invoice_count": 3, "gross_sales": 2430.0, "cash_sales": 810.0, "cashier_expenses": 5000.0, "audit_variance": -1000.0, "payment_issues": 3, "review_status": "Needs Review", "Bank Transfer": 1620.0},
			{"branch": "HQ", "period": "2026-05-01 to 2026-05-31", "invoice_count": 2, "gross_sales": 1900.0, "cash_sales": 1000.0, "cashier_expenses": 0.0, "audit_variance": 0.0, "payment_issues": 0, "review_status": "Reviewed", "Bank Transfer": 0.0},
		]
		summary = get_branch_performance_summary({"company": "Process Edge (Demo)", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(summary["branch"], "All Branches")
		self.assertEqual(summary["gross_sales"], 4330.0)
		self.assertEqual(summary["cash_sales"], 1810.0)
		self.assertEqual(summary["Bank Transfer"], 1620.0)
		self.assertEqual(summary["review_status"], "Needs Review")

	@patch("retailedge.branch_performance.resolve_retailedge_branch_context")
	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_fallback_branch_resolution_is_not_used_by_default(self, _mock_doctype, mock_has_field, mock_sql, mock_resolve):
		mock_has_field.return_value = True
		mock_sql.return_value = [{"branch": "HQ", "invoice_count": 1, "gross_sales": 1000.0, "net_total": 900.0, "outstanding_amount": 0.0, "paid_amount": 1000.0, "paid_invoice_count": 1, "partially_paid_invoice_count": 0, "unpaid_invoice_count": 0}]
		get_branch_sales_summary({"company": "Process Edge (Demo)", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		mock_resolve.assert_not_called()

	@patch("retailedge.branch_performance.resolve_retailedge_branch_context", return_value={"branch": "HQ", "messages": []})
	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_fallback_branch_resolution_runs_only_when_enabled(self, _mock_doctype, mock_has_field, mock_sql, mock_resolve):
		mock_has_field.return_value = True
		mock_sql.side_effect = [
			[],
			[{"name": "SINV-001", "company": "Process Edge (Demo)", "pos_profile": "POS-1", "owner": "cashier@example.com", "grand_total": 1000.0, "net_total": 900.0, "outstanding_amount": 0.0, "paid_amount": 1000.0}],
		]
		get_branch_sales_summary({"company": "Process Edge (Demo)", "from_date": "2026-05-01", "to_date": "2026-05-31", "include_fallback_branch_resolution": 1})
		mock_resolve.assert_called_once()

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_branch_filter_applies_correctly_using_stored_branch(self, _mock_doctype, mock_has_field, mock_sql):
		mock_has_field.return_value = True
		mock_sql.return_value = [{"branch": "HQ", "invoice_count": 1, "gross_sales": 1000.0, "net_total": 900.0, "outstanding_amount": 0.0, "paid_amount": 1000.0, "paid_invoice_count": 1, "partially_paid_invoice_count": 0, "unpaid_invoice_count": 0}]
		get_branch_sales_summary({"company": "Process Edge (Demo)", "branch": "HQ", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		sql_text = mock_sql.call_args[0][0]
		self.assertIn("COALESCE(NULLIF(si.retailedge_branch, ''), NULLIF(si.branch, ''))", sql_text)
		self.assertIn("= %s", sql_text)
		self.assertIn("HQ", mock_sql.call_args[0][1])

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_pos_profile_filter_applies_correctly(self, _mock_doctype, mock_has_field, mock_sql):
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname in {"company", "posting_date", "pos_profile", "retailedge_branch", "grand_total", "outstanding_amount", "paid_amount", "net_total", "is_pos"}
		mock_sql.return_value = []
		get_branch_sales_summary({"company": "Process Edge (Demo)", "pos_profile": "POS-HQ", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertIn("si.pos_profile = %s", mock_sql.call_args[0][0])
		self.assertIn("POS-HQ", mock_sql.call_args[0][1])

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_cashier_filter_does_not_crash_if_cashier_field_is_missing(self, _mock_doctype, mock_has_field, mock_sql):
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname in {"company", "posting_date", "retailedge_branch", "grand_total", "outstanding_amount", "paid_amount", "net_total"}
		mock_sql.return_value = []
		get_branch_sales_summary({"company": "Process Edge (Demo)", "cashier": "cashier@example.com", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertIn("si.owner", mock_sql.call_args[0][0])
		self.assertIn("cashier@example.com", mock_sql.call_args[0][1])

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype")
	def test_cashier_filter_uses_pos_opening_shift_user_not_only_owner(self, mock_has_doctype, mock_has_field, mock_sql):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Sales Invoice", "POS Opening Shift"}
		mock_has_field.side_effect = lambda doctype, fieldname: (
			(doctype == "Sales Invoice" and fieldname in {"company", "posting_date", "retailedge_branch", "grand_total", "outstanding_amount", "paid_amount", "net_total", "is_pos", "posa_pos_opening_shift"})
			or (doctype == "POS Opening Shift" and fieldname in {"user"})
		)
		mock_sql.return_value = []
		get_branch_sales_summary({"company": "Process Edge (Demo)", "cashier": "cashier1@example.com", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		sql_text = mock_sql.call_args[0][0]
		params = mock_sql.call_args[0][1]
		self.assertIn("LEFT JOIN `tabPOS Opening Shift` si_posa_opening_shift", sql_text)
		self.assertIn("si_posa_opening_shift.user", sql_text)
		self.assertIn("cashier1@example.com", params)

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype")
	def test_guest_filter_does_not_absorb_invoice_when_shift_user_exists(self, mock_has_doctype, mock_has_field, mock_sql):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Sales Invoice", "POS Opening Shift"}
		mock_has_field.side_effect = lambda doctype, fieldname: (
			(doctype == "Sales Invoice" and fieldname in {"company", "posting_date", "retailedge_branch", "grand_total", "outstanding_amount", "paid_amount", "net_total", "is_pos", "posa_pos_opening_shift"})
			or (doctype == "POS Opening Shift" and fieldname in {"user"})
		)
		mock_sql.return_value = []
		get_branch_sales_summary({"company": "Process Edge (Demo)", "cashier": "Guest", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		sql_text = mock_sql.call_args[0][0]
		self.assertNotIn("si.owner = %s", sql_text)
		self.assertIn("si_posa_opening_shift.user", sql_text)

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_sales_totals_use_submitted_invoices_only(self, _mock_doctype, mock_has_field, mock_sql):
		mock_has_field.return_value = True
		mock_sql.return_value = [{"branch": "HQ", "invoice_count": 2, "gross_sales": 1500.0, "net_total": 1400.0, "outstanding_amount": 500.0, "paid_amount": 1000.0, "paid_invoice_count": 1, "partially_paid_invoice_count": 0, "unpaid_invoice_count": 1}]
		summary = get_branch_sales_summary({"company": "Process Edge (Demo)", "branch": "HQ", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(summary["by_branch"]["HQ"]["invoice_count"], 2)
		self.assertIn("docstatus = 1", mock_sql.call_args[0][0])

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_payment_method_totals_aggregate_correctly(self, _mock_doctype, mock_has_field, mock_sql):
		mock_has_field.return_value = True
		mock_sql.return_value = [
			{"branch": "HQ", "payment_category": "Cash", "total_amount": 1000.0},
			{"branch": "HQ", "payment_category": "Bank Transfer", "total_amount": 500.0},
		]
		breakdown = get_branch_payment_breakdown({"company": "Process Edge (Demo)", "branch": "HQ", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(breakdown["by_branch"]["HQ"]["Cash"], 1000.0)
		self.assertEqual(breakdown["by_branch"]["HQ"]["Bank Transfer"], 500.0)

	@patch("retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_branch_performance_rows")
	def test_report_executes(self, mock_rows):
		mock_rows.return_value = [
			{
				"branch": "HQ",
				"period": "2026-05-01 to 2026-05-31",
				"invoice_count": 2,
				"gross_sales": 1200.0,
				"outstanding_amount": 200.0,
				"cash_sales": 1000.0,
				"cashier_expenses": 100.0,
				"net_cash_expected": 900.0,
				"audit_variance": 50.0,
				"payment_issues": 1,
				"review_status": "Needs Review",
				"Bank Transfer": 200.0,
				"Card / POS": 0.0,
				"Mobile Money": 0.0,
			}
		]
		columns, data, _, _, summary = execute_branch_performance_report({"company": "Process Edge (Demo)", "from_date": "2026-05-01", "to_date": "2026-05-31", "branch": "HQ"})
		self.assertTrue(columns)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["branch"], "HQ")
		self.assertEqual(data[0]["bank_card_mobile_sales"], 200.0)
		self.assertTrue(summary)

	@patch("retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_branch_performance_debug_summary")
	@patch("retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_branch_performance_rows")
	def test_report_execute_works_with_none_and_returns_columns_when_no_data(self, mock_rows, mock_debug):
		mock_rows.return_value = []
		mock_debug.return_value = {
			"submitted_sales_invoice_count": 4,
			"sales_invoice_with_retailedge_branch_count": 0,
			"cashier_expense_count": 1,
			"daily_sales_audit_count": 1,
			"filters_used": {},
		}
		columns, data, message, _, summary = execute_branch_performance_report(None)
		self.assertTrue(columns)
		self.assertEqual(data, [])
		self.assertIn("No matching records found", message)
		self.assertTrue(summary)

	@patch("retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_branch_performance_debug_summary")
	@patch("retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_branch_performance_rows")
	def test_report_execute_works_with_empty_filters(self, mock_rows, mock_debug):
		mock_rows.return_value = []
		mock_debug.return_value = {
			"submitted_sales_invoice_count": 0,
			"sales_invoice_with_retailedge_branch_count": 0,
			"cashier_expense_count": 0,
			"daily_sales_audit_count": 0,
			"filters_used": {},
		}
		columns, data, message, _, _ = execute_branch_performance_report({})
		self.assertTrue(columns)
		self.assertEqual(data, [])
		self.assertIsNotNone(message)

	@patch("retailedge.branch_performance.get_branch_stock_activity_summary", return_value={"by_branch": {}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_variance_summary", return_value={"by_branch": {}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_expense_summary", return_value={"by_branch": {}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_payment_breakdown", return_value={"by_branch": {}, "messages": []})
	@patch("retailedge.branch_performance.get_branch_sales_summary", return_value={"by_branch": {"Unattributed": {"invoice_count": 2, "gross_sales": 500.0, "net_total": 480.0, "outstanding_amount": 20.0, "paid_amount": 480.0, "paid_invoice_count": 1, "partially_paid_invoice_count": 1, "outstanding_invoice_count": 0, "unattributed_invoice_count": 2}}, "messages": []})
	@patch("retailedge.branch_performance._resolve_branch_scope", return_value={"filters": frappe._dict({"from_date": "2026-05-01", "to_date": "2026-05-31", "only_pos_invoices": 0, "include_unattributed": 1, "include_fallback_branch_resolution": 0}), "messages": [], "allowed_branches": []})
	def test_report_groups_missing_branch_as_unattributed_by_default(
		self,
		_mock_scope,
		_mock_sales,
		_mock_payments,
		_mock_expenses,
		_mock_variance,
		_mock_stock,
	):
		rows = get_branch_performance_rows({"from_date": "2026-05-01", "to_date": "2026-05-31", "include_unattributed": 1})
		self.assertEqual(rows[0]["branch"], "Unattributed")

	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	@patch("retailedge.branch_performance.frappe.db.sql")
	def test_debug_summary_uses_transaction_tables_not_branch_company(self, mock_sql, _mock_doctype, mock_has_field):
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname in {"company", "posting_date", "retailedge_branch", "expense_date", "audit_date"}
		def _sql_side_effect(query, _params=None, **_kwargs):
			if "tabSales Invoice" in query and "retailedge_branch" in query:
				return [(2,)]
			if "tabSales Invoice" in query:
				return [(4,)]
			if "tabRetailEdge Cashier Expense" in query:
				return [(1,)]
			if "tabRetailEdge Daily Sales Audit" in query:
				return [(1,)]
			return [(0,)]
		mock_sql.side_effect = _sql_side_effect
		summary = get_branch_performance_debug_summary({"company": "Process Edge (Demo)", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(summary["submitted_sales_invoice_count"], 4)
		sql_text = "\n".join(call.args[0] for call in mock_sql.call_args_list)
		self.assertNotIn("tabBranch", sql_text)

	@patch("retailedge.branch_performance.frappe.db.sql")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype")
	def test_debug_cashier_filter_reports_available_sources_and_samples(self, mock_has_doctype, mock_has_field, mock_sql):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Sales Invoice", "POS Opening Shift"}
		mock_has_field.side_effect = lambda doctype, fieldname: (
			(doctype == "Sales Invoice" and fieldname in {"company", "posting_date", "retailedge_branch", "grand_total", "is_pos", "pos_profile", "owner", "posa_pos_opening_shift"})
			or (doctype == "POS Opening Shift" and fieldname in {"user", "retailedge_branch"})
		)
		mock_sql.side_effect = [
			[
				{"sales_invoice_count": 2, "resolved_cashier_source": "POS Opening Shift.user", "resolved_cashier": "cashier1@example.com", "gross_sales": 1800.0}
			],
			[
				{
					"name": "SINV-001",
					"posting_date": "2026-05-20",
					"grand_total": 900.0,
					"owner": "Guest",
					"pos_profile": "Airport",
					"is_pos": 1,
					"posa_pos_opening_shift": "POSA-OS-001",
					"pos_opening_shift": None,
					"retailedge_branch": "Airport Branch",
					"resolved_cashier": "cashier1@example.com",
					"resolved_cashier_source": "POS Opening Shift.user",
				}
			],
		]
		summary = debug_branch_performance_cashier_filter({"company": "Process Edge (Demo)", "cashier": "cashier1@example.com", "from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(summary["cashier_filter"], "cashier1@example.com")
		self.assertIn("POS Opening Shift.user", summary["available_cashier_fields"])
		self.assertEqual(summary["sample_invoices"][0]["resolved_cashier"], "cashier1@example.com")


if __name__ == "__main__":
	unittest.main()
