from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class RetailEdgeBusinessControlFinancialOverviewTests(unittest.TestCase):
	def test_business_control_payload_reuses_existing_early_warning_financial_payloads(self):
		source = (APP_ROOT / "business_control_center.py").read_text()
		self.assertIn('"liquidity": warnings.get("liquidity") or {}', source)
		self.assertIn('"budget_spend": warnings.get("budget_spend") or {}', source)
		self.assertIn("without triggering duplicate financial queries", source)
		self.assertNotIn("get_financial_position(", source)

	def test_ui_lazy_loads_full_financial_position(self):
		source = (APP_ROOT / "public" / "js" / "business_control_center" / "BusinessControlCenter.vue").read_text()
		self.assertIn('import FinancialOverview from "./FinancialOverview.vue"', source)
		self.assertIn("@load-position=\"loadFinancialPosition\"", source)
		self.assertIn("retailedge.financial_position.get_financial_position", source)
		self.assertNotIn("Promise.all([callMethod(\"retailedge.financial_position.get_financial_position\"", source)
		self.assertIn("financialPositionLoaded = false", source)

	def test_financial_overview_keeps_balance_and_movement_semantics_distinct(self):
		source = (APP_ROOT / "public" / "js" / "business_control_center" / "FinancialOverview.vue").read_text()
		self.assertIn("Current closing balance", source)
		self.assertIn("Selected-period movement, not balance", source)
		self.assertIn("Net Trade Position means current receivables minus current payables", source)
		self.assertIn("It is not accounting net assets or complete working capital", source)
		self.assertIn("Management indicator, not forecast", source)

	def test_unavailable_financial_values_are_shown_as_withheld_not_zero(self):
		source = (APP_ROOT / "public" / "js" / "business_control_center" / "FinancialOverview.vue").read_text()
		self.assertIn("card.available === false", source)
		self.assertIn("This value is withheld for the current scope", source)
		self.assertIn('metric.available === false || metric.value === null || metric.value === undefined', source)


if __name__ == "__main__":
	unittest.main()
