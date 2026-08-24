from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.forecasting import ForecastValidationError, apply_plan_adjustment
from retailedge.planning_intelligence import (
	_bounded_percent,
	_build_planning_export,
	_inventory_domain,
	_monthly_gl_actuals,
	_summary_value,
	get_planning_action_summary,
)
from retailedge.planning_scope import resolve_planning_branch_scope
from retailedge.planning_snapshot import build_planning_snapshot
from retailedge.sales_forecasting import _normalise_filters as normalise_sales_forecast_filters

APP_DIR = Path(__file__).resolve().parents[1]


class TestR12PlanningScope(FrappeTestCase):
	@patch("retailedge.planning_scope.user_has_global_branch_access", return_value=False)
	@patch("retailedge.planning_scope.get_user_allowed_branches", return_value={"branches": ["Branch A"]})
	def test_blank_branch_resolves_single_restricted_branch(self, allowed, global_access):
		self.assertEqual(resolve_planning_branch_scope("Test Company", "", user="branch@example.com"), "Branch A")

	@patch("retailedge.planning_scope.user_has_global_branch_access", return_value=False)
	@patch("retailedge.planning_scope.get_user_allowed_branches", return_value={"branches": ["Branch A", "Branch B"]})
	def test_blank_branch_fails_closed_for_multiple_restricted_branches(self, allowed, global_access):
		with self.assertRaises(frappe.PermissionError):
			resolve_planning_branch_scope("Test Company", "", user="branch@example.com")

	@patch("retailedge.planning_scope.user_has_global_branch_access", return_value=False)
	@patch("retailedge.planning_scope.get_user_allowed_branches", return_value={"branches": []})
	def test_blank_branch_preserves_existing_unrestricted_convention(self, allowed, global_access):
		self.assertEqual(resolve_planning_branch_scope("Test Company", "", user="user@example.com"), "")


class TestR12AccountingTruth(FrappeTestCase):
	@patch("retailedge.planning_intelligence.frappe.has_permission", return_value=True)
	@patch("retailedge.planning_intelligence.frappe.get_list")
	def test_gl_forecast_excludes_period_closing_vouchers(self, get_list, has_permission):
		get_list.side_effect = [["Income - TC"], []]
		rows = _monthly_gl_actuals("Test Company", "2026-06-01", "2026-06-30", root_type="Income")
		self.assertEqual(rows, [{"period_start": "2026-06-01", "actual": 0.0}])
		gl_filters = get_list.call_args_list[1].kwargs["filters"]
		self.assertEqual(gl_filters["voucher_type"], ["!=", "Period Closing Voucher"])


class TestR12ActionCenterCost(FrappeTestCase):
	@patch("retailedge.planning_intelligence._build_planning_dataset", side_effect=AssertionError("full dataset must not be built"))
	@patch("retailedge.planning_intelligence._inventory_risk_signal", return_value={"at_risk_count": 2})
	@patch(
		"retailedge.planning_intelligence._profitability_domain",
		return_value={"future_rows": [{"period_start": "2026-09-01", "forecast": -1}]},
	)
	@patch(
		"retailedge.planning_intelligence._cash_domain",
		return_value={"future_rows": [{"period_start": "2026-09-01", "forecast": -1, "plan": -1}]},
	)
	@patch(
		"retailedge.planning_intelligence._normalise_filters",
		return_value=frappe._dict(company="Test Company", branch="", as_of_date="2026-08-24", history_months=6, forecast_months=3),
	)
	def test_action_summary_does_not_build_full_planning_workspace(
		self,
		normalise,
		cash,
		profitability,
		inventory,
		full_dataset,
	):
		result = get_planning_action_summary({"company": "Test Company"})
		self.assertEqual(result["count"], 3)
		full_dataset.assert_not_called()
		cash.assert_called_once()
		self.assertFalse(cash.call_args.kwargs["include_commitments"])


class TestR12ScenarioSnapshot(FrappeTestCase):
	@patch("retailedge.planning_snapshot.get_planning_intelligence")
	def test_snapshot_freezes_future_forecast_and_plan_rows(self, planning):
		planning.return_value = {
			"scope": {"company": "Test Company", "as_of_date": "2026-08-24"},
			"assumptions": {"sales_adjustment_percent": 10},
			"domains": {
				"sales": {
					"available": True,
					"source": "Sales Invoice",
					"future_rows": [{"period_start": "2026-09-01", "forecast": 100, "plan": 110, "other": "drop"}],
				},
				"cash": {"available": False},
				"expenses": {"available": False},
				"profitability": {"available": False},
				"inventory": {
					"available": True,
					"rows": [
						{"item_code": "ITEM-A", "coverage_risk": True},
						{"item_code": "ITEM-B", "coverage_risk": False},
					],
				},
			},
		}
		snapshot = build_planning_snapshot({"company": "Test Company"})
		self.assertTrue(snapshot["metadata"]["immutable_baseline"])
		self.assertEqual(
			snapshot["domains"]["sales"]["future_rows"],
			[{"period_start": "2026-09-01", "forecast": 100, "plan": 110}],
		)
		self.assertEqual(snapshot["domains"]["inventory"]["at_risk_count"], 1)
		self.assertEqual(snapshot["domains"]["inventory"]["at_risk_items"], ["ITEM-A"])

	def test_scenario_performance_does_not_recalculate_saved_forecast(self):
		source = (APP_DIR / "scenario_performance.py").read_text()
		self.assertNotIn("get_planning_intelligence(", source)
		self.assertIn("forecast_snapshot_json", source)
		self.assertIn("immutable baseline", source.lower())


class TestR12SalesForecastAsOfGuard(FrappeTestCase):
	@patch("retailedge.sales_forecasting.nowdate", return_value="2026-08-24")
	@patch("retailedge.sales_forecasting._coerce_filters")
	def test_future_as_of_date_is_rejected_before_source_query(self, coerce, current_date):
		coerce.return_value = frappe._dict(company="Test Company", as_of_date="2026-08-25")
		with self.assertRaises(frappe.ValidationError):
			normalise_sales_forecast_filters(coerce.return_value)


class TestR12InventoryTemporalConsistency(FrappeTestCase):
	@patch("retailedge.planning_intelligence.get_historical_inventory_demand")
	@patch("retailedge.planning_intelligence.nowdate", return_value="2026-08-25")
	def test_historical_inventory_planning_fails_before_current_stock_is_mixed_in(self, current_date, demand):
		filters = frappe._dict(
			company="Test Company",
			branch="",
			as_of_date="2026-07-31",
			history_months=6,
			forecast_months=3,
			inventory_safety_percent=10,
		)
		with self.assertRaises(frappe.ValidationError):
			_inventory_domain(filters)
		demand.assert_not_called()


class TestR12StableSummaryContracts(FrappeTestCase):
	def test_machine_key_wins_over_localized_summary_label(self):
		cards = [{"key": "net_change", "label": "Cambio Neto", "value": 42.5}]
		self.assertEqual(_summary_value(cards, "net_change", "Net Change"), 42.5)

	def test_cash_and_budget_sources_publish_machine_keys(self):
		cash_source = (APP_DIR / "cash_movement.py").read_text()
		budget_source = (APP_DIR / "budget_spend_control.py").read_text()
		self.assertIn('"key": "net_change"', cash_source)
		self.assertIn('"remaining_budget"', budget_source)
		self.assertIn('"budget_used"', budget_source)


class TestR12PlanningExport(FrappeTestCase):
	def test_export_includes_timeline_commitments_inventory_budget_and_assumptions(self):
		dataset = {
			"title": "Forecasting & Planning",
			"company_currency": "NGN",
			"rows": [{"domain": "Sales", "period_start": "2026-09-01", "row_type": "Forecast / Plan", "actual": None, "forecast": 100, "plan": 110, "variance": 10}],
			"summary": [],
			"assumptions": {"sales_adjustment_percent": 10},
			"metadata": {},
			"domains": {
				"sales": {"available": True},
				"cash": {"available": True, "commitment_rows": [{"period_start": "2026-09-01", "receivables_due": 50, "payables_due": 20, "net_known_due": 30}]},
				"inventory": {"available": True, "rows": [{"period_start": "2026-09-01", "item_code": "ITEM-A", "stock_uom": "Nos", "forecast_demand_qty": 5, "planned_demand_qty": 6, "cumulative_planned_demand_qty": 6, "current_projected_qty": 4, "coverage_shortfall_qty": 2, "coverage_risk": True, "replenishment_status": "Below reorder"}]},
				"budget": {"available": True, "summary": [{"key": "remaining_budget", "label": "Remaining Budget", "value": 1000, "datatype": "Currency", "available": True}], "controls": [{"family": "Budget", "label": "Budget pressure", "value": 90, "datatype": "Percent", "severity": "warning"}]},
				"expenses": {"available": False, "title": "Accounting Expenses", "reason": "Not available"},
			},
		}
		export = _build_planning_export(dataset)
		sections = {row["section"] for row in export["rows"]}
		self.assertTrue({"Planning Timeline", "Known Due Commitments", "Inventory Coverage", "Budget Summary", "Budget Controls", "Assumptions", "Availability"}.issubset(sections))
		self.assertEqual([column["fieldname"] for column in export["columns"]], ["domain", "section", "period_start", "reference", "metric", "value", "unit", "status", "notes"])


class TestR12NumericHardening(FrappeTestCase):
	def test_non_finite_plan_adjustment_is_rejected(self):
		with self.assertRaises(ForecastValidationError):
			apply_plan_adjustment([{"period_start": "2026-09-01", "forecast": 100}], adjustment_percent=float("nan"))

	def test_non_finite_planning_percentage_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			_bounded_percent(float("inf"), -100, 1000, "sales_adjustment_percent")


class TestR12ScenarioUI(FrappeTestCase):
	def test_scenario_creation_is_permission_aware_and_does_not_use_global_route_options(self):
		source = (APP_DIR / "public" / "js" / "forecasting_planning" / "ForecastingPlanning.vue").read_text()
		self.assertIn("canCreateScenario", source)
		self.assertIn("frappe.model?.can_create", source)
		self.assertIn('frappe.new_doc("RetailEdge Planning Scenario", {', source)
		self.assertNotIn("frappe.route_options = { company: this.filters.company", source)
