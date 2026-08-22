from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.control_early_warning import _build_control_early_warning

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeControlEarlyWarningTests(unittest.TestCase):
	def test_combines_budget_liquidity_collections_payables_and_profitability_signals(self):
		budget = {
			"controls": [
				{"severity": "warning", "family": "Spend Trend", "label": "Spend increased", "value": 25, "datatype": "Percent", "route": "/app/expense-register"},
			]
		}
		liquidity = {
			"current_liquidity": {
				"cash_bank_available": True,
				"immediate_obligation_coverage_ratio": 0.8,
				"indicative_liquidity_gap": -500,
				"overdue_receivables": 1200,
				"overdue_payables": 700,
			}
		}
		profitability = {
			"available": True,
			"current": {"net_profit": -100, "gross_margin_percent": 20, "route": "/app/query-report/Profit%20and%20Loss%20Statement"},
			"previous": {"net_profit": 1000, "gross_margin_percent": 30},
		}
		result = _build_control_early_warning(budget=budget, liquidity=liquidity, profitability=profitability)
		families = {row["family"] for row in result["warnings"]}
		self.assertTrue({"Spend Trend", "Liquidity", "Collections", "Supplier Obligations", "Profitability"}.issubset(families))
		self.assertGreaterEqual(result["critical_count"], 2)

	def test_unavailable_branch_profitability_does_not_create_false_profit_warning(self):
		result = _build_control_early_warning(
			budget={"controls": []},
			liquidity={"current_liquidity": {"cash_bank_available": False, "overdue_receivables": 0, "overdue_payables": 0}},
			profitability={"available": False, "reason": "Branch accounting attribution unavailable"},
		)
		self.assertFalse(any(row["family"] == "Profitability" for row in result["warnings"]))

	def test_service_composes_existing_engines_and_does_not_invent_historical_ar_ap(self):
		source = (APP_ROOT / "control_early_warning.py").read_text()
		self.assertIn("get_budget_spend_control", source)
		self.assertIn("get_liquidity_control", source)
		self.assertIn("get_accounting_profitability", source)
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertIn("does not manufacture historical AR/AP balances", source)
		self.assertIn("previous equal period", source)


if __name__ == "__main__":
	unittest.main()
