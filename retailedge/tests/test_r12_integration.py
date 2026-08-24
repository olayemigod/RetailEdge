from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import action_center
from retailedge.action_follow_up import action_fingerprint
from retailedge.edgesuite_ui import NAVIGATION_GROUPS

APP_DIR = Path(__file__).resolve().parents[1]
_EMPTY_SUMMARY = {"summary": []}


class TestR12UIAndNavigation(FrappeTestCase):
	def test_r12_pages_live_in_insights_without_new_top_level_group(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		self.assertNotIn("forecasting", groups)
		self.assertNotIn("planning", groups)
		insights = groups["insights"]
		targets = [item.get("target") for item in insights["items"]]
		self.assertIn("sales-forecast", targets)
		self.assertIn("forecasting-planning", targets)
		self.assertIn("RetailEdge Planning Scenario", targets)
		self.assertLess(targets.index("sales-forecast"), targets.index("forecasting-planning"))
		for key, group in groups.items():
			if key == "insights":
				continue
			other_targets = {item.get("target") for item in group["items"]}
			self.assertNotIn("sales-forecast", other_targets)
			self.assertNotIn("forecasting-planning", other_targets)
			self.assertNotIn("RetailEdge Planning Scenario", other_targets)

	def test_forecasting_planning_bundle_has_non_empty_vue_target(self):
		bundle = (APP_DIR / "public/js/forecasting_planning.bundle.js").read_text()
		vue_path = APP_DIR / "public/js/forecasting_planning/ForecastingPlanning.vue"
		vue = vue_path.read_text()
		self.assertIn('./forecasting_planning/ForecastingPlanning.vue', bundle)
		self.assertGreater(len(vue.strip()), 1000)
		self.assertIn("<template>", vue)
		self.assertIn('name: "ForecastingPlanning"', vue)
		self.assertIn("Cumulative demand vs projected stock", vue)
		self.assertIn("Known due commitments", vue)
		self.assertIn("Forecast vs Actual", vue)

	def test_sales_forecast_bundle_has_non_empty_vue_target(self):
		bundle = (APP_DIR / "public/js/sales_forecast.bundle.js").read_text()
		vue = (APP_DIR / "public/js/sales_forecast/SalesForecast.vue").read_text()
		self.assertIn('./sales_forecast/SalesForecast.vue', bundle)
		self.assertGreater(len(vue.strip()), 1000)
		self.assertIn("<template>", vue)

	def test_page_loaders_use_edgesuite_bundles(self):
		sales_page = (APP_DIR / "retailedge/page/sales_forecast/sales_forecast.js").read_text()
		planning_page = (APP_DIR / "retailedge/page/forecasting_planning/forecasting_planning.js").read_text()
		self.assertIn('sales_forecast.bundle.js', sales_page)
		self.assertIn('window.mountSalesForecast', sales_page)
		self.assertIn('forecasting_planning.bundle.js', planning_page)
		self.assertIn('window.mountForecastingPlanning', planning_page)

	def test_planning_engine_uses_projected_stock_and_cumulative_coverage(self):
		source = (APP_DIR / "planning_intelligence.py").read_text()
		self.assertIn('row.get("projected_qty")', source)
		self.assertIn('"cumulative_planned_demand_qty"', source)
		self.assertIn('"coverage_shortfall_qty"', source)
		self.assertNotIn('current_projected = flt(reorder.get("recommended_reorder_qty"))', source)
		self.assertIn("ERPNext Budget remains authoritative", source)
		self.assertIn("collection/payment is not assumed", source)


class TestR12ActionCenterIntegration(FrappeTestCase):
	def setUp(self):
		frappe.session.user = "Administrator"

	@patch("retailedge.action_center.get_planning_action_summary")
	@patch("retailedge.action_center.get_customer_sales_action_summary", return_value={"items": []})
	@patch("retailedge.action_center.get_bank_exception_summary", return_value={"summary": [], "oldest_days": {}})
	@patch("retailedge.action_center.get_supplier_payables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_customer_receivables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_cash_shift_verification", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_expense_register", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_inventory_action_summary", return_value=_EMPTY_SUMMARY)
	def test_r12_action_uses_existing_follow_up_contract(
		self, stock, expenses, cash, receivables, payables, bank, r11, r12
	):
		r12.return_value = {
			"items": [
				{
					"source": "r12_planning",
					"label": "Planned cumulative demand exceeds current projected stock for some items",
					"value": 4,
					"datatype": "Int",
					"severity": "warning",
					"route": "/app/forecasting-planning",
					"time_basis": "forecast",
					"kind": "inventory_plan_shortfall",
					"semantic_key": "inventory_plan_shortfall",
					"target_type": "Page",
					"target": "forecasting-planning",
					"open_mode": "same_tab",
				}
			]
		}
		result = action_center.get_action_center_data(
			{"company": "Test Company", "branch": "", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		item = next(row for row in result["items"] if row["kind"] == "inventory_plan_shortfall")
		expected = action_fingerprint(
			company="Test Company",
			branch="",
			source="r12_planning",
			kind="inventory_plan_shortfall",
			label="Planned cumulative demand exceeds current projected stock for some items",
			route="/app/forecasting-planning",
		)
		self.assertEqual(item["fingerprint"], expected)
		self.assertEqual(item["follow_up"]["effective_status"], "Open")
		self.assertTrue(result["sources"]["r12_planning"]["available"])
		self.assertIn("planning_provider", result["metadata"])

	@patch("retailedge.action_center.get_planning_action_summary", side_effect=frappe.ValidationError("planning unavailable"))
	@patch("retailedge.action_center.get_customer_sales_action_summary", return_value={"items": []})
	@patch("retailedge.action_center.get_bank_exception_summary", return_value={"summary": [], "oldest_days": {}})
	@patch("retailedge.action_center.get_supplier_payables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_customer_receivables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_cash_shift_verification", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_expense_register", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_inventory_action_summary", return_value=_EMPTY_SUMMARY)
	def test_r12_validation_failure_isolated_from_action_center(
		self, stock, expenses, cash, receivables, payables, bank, r11, r12
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "branch": "", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		self.assertEqual(result["items"], [])
		self.assertFalse(result["sources"]["r12_planning"]["available"])
		self.assertNotIn("planning unavailable", result["sources"]["r12_planning"]["reason"])
