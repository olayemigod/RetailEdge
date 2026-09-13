from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.expense_dashboard import (
	_aggregate,
	_attention_items,
	_period_comparison,
	get_expense_dashboard_data,
)


class TestExpenseDashboard(unittest.TestCase):
	def test_category_breakdown_ranks_amount_and_share(self):
		rows = [
			{"expense_category": "Fuel", "amount": 600},
			{"expense_category": "Fuel", "amount": 100},
			{"expense_category": "Repairs", "amount": 300},
		]
		result = _aggregate(rows, "expense_category")
		self.assertEqual(result[0]["label"], "Fuel")
		self.assertEqual(result[0]["amount"], 700)
		self.assertEqual(result[0]["count"], 2)
		self.assertAlmostEqual(result[0]["share_pct"], 70)

	def test_period_comparison_uses_equal_period_daily_rate(self):
		current = [{"amount": 1400}]
		previous = [{"amount": 700}]
		result = _period_comparison(
			current,
			previous,
			{"from_date": "2026-08-01", "to_date": "2026-08-07"},
			{"from_date": "2026-07-25", "to_date": "2026-07-31"},
		)
		self.assertEqual(result["change_pct"], 100)
		self.assertEqual(result["current_daily_average"], 200)
		self.assertEqual(result["previous_daily_average"], 100)

	def test_attention_flags_control_and_concentration_signals(self):
		source = {
			"summary": [
				{"label": "Posting Blocked", "value": 2, "type": "Int"},
				{"label": "Submitted for Review", "value": 3, "type": "Int"},
			]
		}
		breakdowns = {"category": [{"label": "Fuel", "amount": 700, "share_pct": 70}]}
		comparison = {"change_pct": 25}
		items = _attention_items(source, breakdowns, comparison)
		labels = [item["label"] for item in items]
		self.assertIn("Expenses are blocked from ledger posting", labels)
		self.assertIn("Expenses are waiting for review", labels)
		self.assertIn("Spend increased materially versus the previous equal period", labels)
		self.assertIn("One expense category represents at least half of spending", labels)

	@patch("retailedge.expense_dashboard._account_context", return_value=[])
	@patch("retailedge.expense_dashboard.require_dashboard_action", return_value={"can_view": True})
	@patch("retailedge.expense_dashboard.get_expense_register_export")
	def test_dashboard_composes_expense_register_for_current_and_previous_period(self, export, capability, account_context):
		export.side_effect = [
			{
				"rows": [
					{"name": "EXP-1", "expense_category": "Fuel", "branch": "Aba", "cashier": "cashier@example.com", "amount": 1000}
				],
				"summary": [{"label": "Total Expenses", "value": 1000, "type": "Currency"}],
			},
			{"rows": [{"name": "EXP-0", "expense_category": "Fuel", "branch": "Aba", "amount": 500}], "summary": []},
		]
		result = get_expense_dashboard_data(
			{"company": "Demo Company", "branch": "Aba", "from_date": "2026-08-01", "to_date": "2026-08-07"}
		)
		self.assertEqual(export.call_count, 2)
		capability.assert_called_once_with("expense-overview", "view", company="Demo Company", branch="Aba")
		self.assertEqual(result["breakdowns"]["category"][0]["label"], "Fuel")
		self.assertEqual(result["comparison"]["change_pct"], 100)
		self.assertEqual(result["metadata"]["judgement_basis"], "trend_concentration_and_control_signals_not_budget_compliance")
		account_context.assert_called_once()

	def test_dashboard_source_does_not_claim_budget_compliance(self):
		from pathlib import Path

		source = (Path(__file__).resolve().parents[1] / "expense_dashboard.py").read_text(encoding="utf-8")
		self.assertIn("Budget compliance is not inferred", source)
		self.assertIn("get_expense_register_export", source)
		self.assertNotIn("frappe.db.sql", source)


if __name__ == "__main__":
	unittest.main()
