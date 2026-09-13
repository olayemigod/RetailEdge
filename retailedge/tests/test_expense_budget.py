from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from frappe import _dict

from retailedge import expense_budget


class TestExpenseBudgetInsight(unittest.TestCase):
	def test_prorates_budget_for_partial_overlap(self):
		amount = expense_budget._prorated_amount(
			3100,
			period_start=date(2026, 8, 1),
			period_end=date(2026, 8, 31),
			start=date(2026, 8, 1),
			end=date(2026, 8, 10),
		)
		self.assertEqual(round(amount, 2), 1000.00)

	@patch("retailedge.expense_budget.frappe.has_permission", return_value=False)
	@patch("retailedge.expense_budget.frappe.db.exists", return_value=True)
	def test_budget_permission_failure_returns_unavailable_without_query(self, _exists, _permission):
		with patch("retailedge.expense_budget._matching_budgets") as matching:
			result = expense_budget.build_expense_budget_insight(
				company="Demo",
				branch="",
				from_date="2026-08-01",
				to_date="2026-08-31",
				expense_rows=[],
			)
		self.assertFalse(result["available"])
		matching.assert_not_called()

	@patch("retailedge.expense_budget._branch_expense_cost_center", return_value="Main - D")
	@patch("retailedge.expense_budget.frappe.db.get_value", side_effect=["Demo", "Demo"])
	@patch("retailedge.expense_budget.frappe.get_list")
	def test_branch_cost_center_overrides_category_default(self, get_list, _get_value, _branch_cc):
		get_list.return_value = [
			_dict(name="Fuel", company="Demo", expense_account="Fuel Expense - D", default_cost_center="Other - D")
		]
		rows = expense_budget._category_mappings(company="Demo", branch="Lagos")
		self.assertEqual(rows[0]["cost_center"], "Main - D")

	@patch("retailedge.expense_budget._elapsed_days", return_value=10)
	@patch("retailedge.expense_budget._matching_budgets")
	@patch("retailedge.expense_budget._category_mappings")
	@patch("retailedge.expense_budget.frappe.has_permission", return_value=True)
	@patch("retailedge.expense_budget.frappe.db.exists", return_value=True)
	def test_ambiguous_category_mapping_is_not_split_arbitrarily(
		self,
		_exists,
		_permission,
		category_mappings,
		matching_budgets,
		_elapsed,
	):
		category_mappings.return_value = [
			{"category": "Fuel", "expense_account": "Travel - D", "cost_center": "Main - D"},
			{"category": "Transport", "expense_account": "Travel - D", "cost_center": "Main - D"},
		]
		matching_budgets.return_value = [
			{
				"name": "BUDGET-1",
				"account": "Travel - D",
				"cost_center": "Main - D",
				"budget_amount": 31000,
				"budget_start_date": date(2026, 8, 1),
				"budget_end_date": date(2026, 8, 31),
				"distribution": [],
			}
		]
		with patch("retailedge.expense_budget._branch_expense_cost_center", return_value=""):
			result = expense_budget.build_expense_budget_insight(
				company="Demo",
				branch="",
				from_date="2026-08-01",
				to_date="2026-08-31",
				expense_rows=[{"expense_category": "Fuel", "amount": 5000}],
			)
		self.assertTrue(result["available"])
		self.assertEqual(result["target_amount"], 31000)
		self.assertEqual(result["ambiguous_category_count"], 2)
		self.assertIsNone(result["category_targets"][0]["target"])

	@patch("retailedge.expense_budget._elapsed_days", return_value=10)
	@patch("retailedge.expense_budget._matching_budgets")
	@patch("retailedge.expense_budget._category_mappings")
	@patch("retailedge.expense_budget.frappe.has_permission", return_value=True)
	@patch("retailedge.expense_budget.frappe.db.exists", return_value=True)
	def test_projection_flags_expected_overspend(
		self,
		_exists,
		_permission,
		category_mappings,
		matching_budgets,
		_elapsed,
	):
		category_mappings.return_value = [
			{"category": "Fuel", "expense_account": "Fuel - D", "cost_center": "Main - D"}
		]
		matching_budgets.return_value = [
			{
				"name": "BUDGET-1",
				"account": "Fuel - D",
				"cost_center": "Main - D",
				"budget_amount": 10000,
				"budget_start_date": date(2026, 8, 1),
				"budget_end_date": date(2026, 8, 31),
				"distribution": [],
			}
		]
		with patch("retailedge.expense_budget._branch_expense_cost_center", return_value=""):
			result = expense_budget.build_expense_budget_insight(
				company="Demo",
				branch="",
				from_date="2026-08-01",
				to_date="2026-08-31",
				expense_rows=[{"expense_category": "Fuel", "amount": 5000}],
			)
		self.assertEqual(result["used_pct"], 50)
		self.assertGreater(result["projected_period_spend"], result["target_amount"])
		self.assertTrue(result["projected_over_budget"])

	def test_source_contains_no_budget_mutation_calls(self):
		from pathlib import Path

		source = Path(expense_budget.__file__).read_text(encoding="utf-8")
		for forbidden in (".insert(", ".save(", ".submit(", ".cancel(", "ignore_permissions"):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
