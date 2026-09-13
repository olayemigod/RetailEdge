from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.budget_spend_control import _build_budget_spend_control

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBudgetSpendControlTests(unittest.TestCase):
	def test_over_budget_and_category_pressure_are_prioritised(self):
		budget = {
			"available": True,
			"target_amount": 10000,
			"actual_amount": 11000,
			"remaining_amount": -1000,
			"used_pct": 110,
			"projected_period_spend": 14000,
			"projected_variance": -4000,
			"projected_over_budget": True,
			"over_budget": True,
			"ambiguous_category_count": 0,
			"category_targets": [
				{"category": "Fuel", "actual": 6000, "target": 5000, "ambiguous": False},
				{"category": "Repairs", "actual": 2000, "target": 5000, "ambiguous": False},
			],
		}
		dashboard = {"comparison": {"change_pct": 25, "current_total": 11000, "previous_total": 8800, "previous_period_available": True}}
		result = _build_budget_spend_control(budget=budget, dashboard=dashboard)
		self.assertEqual(result["controls"][0]["severity"], "critical")
		self.assertTrue(any(item.get("category") == "Fuel" for item in result["category_pressure"]))
		self.assertTrue(any(item["family"] == "Spend Trend" for item in result["controls"]))

	def test_ambiguous_category_is_not_given_false_budget_pressure(self):
		budget = {
			"available": True,
			"target_amount": 10000,
			"actual_amount": 5000,
			"used_pct": 50,
			"ambiguous_category_count": 1,
			"category_targets": [
				{"category": "Shared A", "actual": 4500, "target": None, "ambiguous": True},
			],
		}
		result = _build_budget_spend_control(budget=budget, dashboard={"comparison": {}})
		self.assertEqual(result["category_pressure"], [])
		self.assertTrue(any(item["family"] == "Budget Mapping" for item in result["controls"]))

	def test_service_reuses_budget_and_expense_dashboard_engines_without_direct_budget_queries(self):
		source = (APP_ROOT / "budget_spend_control.py").read_text()
		self.assertIn("get_expense_budget_insight", source)
		self.assertIn("get_expense_dashboard_data", source)
		self.assertNotIn('frappe.get_list("Budget"', source)
		self.assertNotIn('frappe.db.get_all("Budget"', source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertIn("RetailEdge does not change ERPNext Budget enforcement", source)


if __name__ == "__main__":
	unittest.main()
