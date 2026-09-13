from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public/js"
PLANNING = ROOT / "forecasting_planning/ForecastingPlanning.vue"
SALES_FORECAST = ROOT / "sales_forecast/SalesForecast.vue"
FILES = (PLANNING, SALES_FORECAST)


def test_forecasting_pages_consume_native_desk_capability_and_guard_shell_routes():
	for path in FILES:
		source = path.read_text(encoding="utf-8")
		assert "canUseNativeDesk: false" in source, path
		assert "Boolean(navigation.access?.can_use_native_desk)" in source, path
		assert '["DocType", "Report"].includes(item.target_type)' in source, path
		assert "!this.canUseNativeDesk" in source, path


def test_planning_scenario_native_form_actions_are_explicitly_contained():
	source = PLANNING.read_text(encoding="utf-8")
	assert "Advanced: Save Scenario" in source
	assert "Advanced: Open Scenario" in source
	assert ':disabled="!filters.company || !canCreateScenario || !canUseNativeDesk"' in source
	assert ':disabled="!canUseNativeDesk"' in source
	assert "if (!this.canUseNativeDesk || !this.canCreateScenario || !this.filters.company) return" in source
	assert 'if (this.canUseNativeDesk && this.scenarioName) frappe.set_route("Form", "RetailEdge Planning Scenario", this.scenarioName)' in source


def test_edgesuite_forecast_to_planning_transition_remains_available():
	source = SALES_FORECAST.read_text(encoding="utf-8")
	assert 'openPlanningWorkspace() { frappe.set_route("forecasting-planning"); }' in source
