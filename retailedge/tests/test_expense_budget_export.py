from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.expense_dashboard_export import build_expense_dashboard_export_with_budget


class TestExpenseBudgetExport(unittest.TestCase):
	@patch("retailedge.expense_dashboard_export.get_expense_budget_insight")
	@patch("retailedge.expense_dashboard_export.build_expense_dashboard_export_dataset")
	def test_shared_export_includes_budget_and_category_targets(self, base_export, budget):
		base_export.return_value = {
			"title": "Expenses Dashboard",
			"columns": [],
			"rows": [{"section": "Headline", "dimension": "", "metric": "Total Expenses", "value": 5000}],
			"summary": [],
			"filters": {},
		}
		budget.return_value = {
			"available": True,
			"target_amount": 10000,
			"actual_amount": 5000,
			"remaining_amount": 5000,
			"projected_period_spend": 9000,
			"projected_variance": 1000,
			"category_targets": [
				{"category": "Fuel", "target": 3000},
				{"category": "Shared", "target": None},
			],
		}
		result = build_expense_dashboard_export_with_budget({"company": "Demo"})
		metrics = {(row["section"], row["metric"]): row["value"] for row in result["rows"]}
		self.assertEqual(metrics[("Budget & Burn Rate", "Budget for Period")], 10000)
		self.assertEqual(metrics[("Category Budget", "Budget Target")], 3000)
		self.assertEqual(len([row for row in result["rows"] if row.get("dimension") == "Shared"]), 0)

	@patch("retailedge.expense_dashboard_export.get_expense_budget_insight", return_value={"available": False})
	@patch("retailedge.expense_dashboard_export.build_expense_dashboard_export_dataset")
	def test_export_remains_available_when_budget_is_not_permitted_or_configured(self, base_export, _budget):
		base_export.return_value = {"title": "Expenses Dashboard", "columns": [], "rows": [], "summary": [], "filters": {}}
		result = build_expense_dashboard_export_with_budget({"company": "Demo"})
		self.assertEqual(result["rows"], [])


if __name__ == "__main__":
	unittest.main()
