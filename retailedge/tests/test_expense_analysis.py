from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.expense_analysis import (
	SUPPORTED_GROUP_BY,
	_add_expense_row,
	_finalise_bucket,
	_new_bucket,
	_normalise_group_by,
	_period_group,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "expense_analysis.py"
COMPONENT = ROOT / "public" / "js" / "expense_register" / "ExpenseRegisterReport.vue"
BUNDLE = ROOT / "public" / "js" / "expense_register.bundle.js"
PAGE_JSON = ROOT / "retailedge" / "page" / "expense_analysis" / "expense_analysis.json"
PAGE_JS = ROOT / "retailedge" / "page" / "expense_analysis" / "expense_analysis.js"
REPORT_CENTER = ROOT / "report_center.py"
CAPABILITIES = ROOT / "reporting_capabilities.py"
ACTIONS = ROOT / "reporting_actions.py"
SORTING = ROOT / "report_sorting.py"
SHELL_ACTIONS = ROOT / "public" / "js" / "retailedge_reporting_actions.js"


class TestExpenseAnalysis(FrappeTestCase):
	def test_supported_dimensions_match_consolidated_expense_fields(self):
		self.assertEqual(
			SUPPORTED_GROUP_BY,
			(
				"Day",
				"Week",
				"Month",
				"Quarter",
				"Year",
				"Expense Category",
				"Expense Account",
				"Branch",
				"Source",
				"Cost Center",
				"Payment Account",
				"Cashier",
				"Expense Status",
			),
		)
		self.assertEqual(_normalise_group_by("expense account"), "Expense Account")
		self.assertEqual(_normalise_group_by(""), "Month")

	def test_period_grouping_is_stable(self):
		self.assertEqual(_period_group("2026-09-22", "Day"), ("2026-09-22", "2026-09-22"))
		self.assertEqual(_period_group("2026-09-22", "Week")[0], "2026-W39")
		self.assertEqual(_period_group("2026-09-22", "Month")[0], "2026-09")
		self.assertEqual(_period_group("2026-09-22", "Quarter"), ("2026-Q3", "Q3 2026"))
		self.assertEqual(_period_group("2026-09-22", "Year"), ("2026", "2026"))

	def test_posted_expense_unposted_cashier_exposure_and_reversals_stay_separate(self):
		bucket = _new_bucket("All", "All")
		_add_expense_row(
			bucket,
			{
				"amount": 100,
				"source_type": "Business Expense",
				"ledger_status": "Posted",
				"posting_ready": 1,
			},
		)
		_add_expense_row(
			bucket,
			{
				"amount": 40,
				"source_type": "Cashier / POS",
				"ledger_status": "Pending Ledger",
				"posting_ready": 0,
			},
		)
		_add_expense_row(
			bucket,
			{
				"amount": -20,
				"source_type": "Business Expense Reversal",
				"ledger_status": "Reversed",
				"posting_ready": 0,
			},
		)
		row = _finalise_bucket(bucket)

		self.assertEqual(row["expense_lines"], 3)
		self.assertEqual(row["posted_lines"], 2)
		self.assertEqual(row["unposted_cashier_lines"], 1)
		self.assertEqual(row["gross_spend"], 140)
		self.assertEqual(row["credits_reversals"], 20)
		self.assertEqual(row["net_expense"], 120)
		self.assertEqual(row["posted_net_expense"], 80)
		self.assertEqual(row["unposted_cashier_exposure"], 40)
		self.assertEqual(row["posting_blocked_count"], 1)
		self.assertEqual(row["average_expense"], 40)

	def test_backend_reuses_consolidated_expense_truth_instead_of_rebuilding_ledgers(self):
		source = BACKEND.read_text(encoding="utf-8")
		for token in (
			"get_consolidated_expense_export",
			"constrain_report_filters",
			'require_report_action(',
			'"expense-analysis"',
			'"accounting_truth"',
			'"unposted_policy"',
			'"de_duplication"',
			'"payment_account_policy"',
			'"project_payee_policy"',
		):
			self.assertIn(token, source)

		for forbidden in (
			"frappe.db.sql",
			"ignore_permissions",
			'"GL Entry"',
			'"Purchase Invoice"',
			'"Expense Claim"',
			'"Journal Entry"',
		):
			self.assertNotIn(forbidden, source)

	def test_page_provider_catalogue_and_governance_are_wired(self):
		for path in (PAGE_JSON, PAGE_JS):
			self.assertTrue(path.exists(), f"Missing Expense Analysis Page fixture: {path}")

		component = COMPONENT.read_text(encoding="utf-8")
		bundle = BUNDLE.read_text(encoding="utf-8")
		report_center = REPORT_CENTER.read_text(encoding="utf-8")
		capabilities = CAPABILITIES.read_text(encoding="utf-8")
		actions = ACTIONS.read_text(encoding="utf-8")
		sorting = SORTING.read_text(encoding="utf-8")
		shell = SHELL_ACTIONS.read_text(encoding="utf-8")

		for token in (
			"expense_analysis:",
			'providerKey: "expense-analysis"',
			'label="Group By"',
			'"Expenses by Category"',
			'"Expenses by Expense Account"',
			'"Expenses by Branch"',
			'"Expenses by Source"',
			'"Expenses by Cost Center"',
			'"Expenses by Payment Account"',
			'"Expenses by Cashier"',
		):
			self.assertIn(token, component)
		self.assertIn('key: "expense-analysis"', bundle)
		self.assertIn('pageMethod: "retailedge.expense_analysis.get_expense_analysis"', bundle)
		self.assertIn('"target": "expense-analysis"', report_center)
		self.assertIn('"expense-analysis": ReportCapabilitySpec', capabilities)
		self.assertIn('if key == "expense-analysis"', actions)
		self.assertIn('"expense-analysis": frozenset', sorting)
		self.assertIn('"/app/expense-analysis": "expense-analysis"', shell)
