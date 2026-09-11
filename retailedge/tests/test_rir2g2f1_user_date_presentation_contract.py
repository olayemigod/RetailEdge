from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
	"customer_360": ROOT / "public/js/customer_360/Customer360.vue",
	"project_operations": ROOT / "public/js/project_operations/ProjectOperations.vue",
	"forecasting_planning": ROOT / "public/js/forecasting_planning/ForecastingPlanning.vue",
	"sales_forecast": ROOT / "public/js/sales_forecast/SalesForecast.vue",
	"customer_sales": ROOT / "public/js/customer_sales_intelligence/CustomerSalesIntelligence.vue",
	"customer_opportunity": ROOT / "public/js/customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue",
	"inventory_insights": ROOT / "public/js/inventory_insights/InventoryInsightView.vue",
	"inventory_intelligence": ROOT / "public/js/inventory_intelligence/InventoryIntelligenceCentre.vue",
	"profitability": ROOT / "public/js/profitability_intelligence/ProfitabilityIntelligence.vue",
}


def _source(key: str) -> str:
	return FILES[key].read_text(encoding="utf-8")


def test_scoped_pages_use_frappe_user_date_formatting():
	for key in FILES:
		source = _source(key)
		assert "frappe.datetime.str_to_user" in source, key


def test_customer_360_date_formatter_no_longer_returns_raw_value():
	source = _source("customer_360")
	assert 'formatDate(value) { return value || "—"; }' not in source
	assert "formatDate(data.relationship.first_purchase_date)" in source
	assert "formatDate(row.posting_date)" in source


def test_project_operations_formats_visible_timeline_and_payment_dates():
	source = _source("project_operations")
	assert "formatDate(row.date)" in source
	assert "formatDate(row.posting_date)" in source
	assert '{{ row.date || "—" }}' not in source
	assert "{{ row.posting_date }}" not in source


def test_forecasting_visible_period_dates_are_formatted():
	source = _source("forecasting_planning")
	assert "formatDate(row.period_start)" in source
	assert 'type="date"' in source
	assert "filters.as_of_date" in source


def test_scope_and_comparison_date_labels_are_formatted():
	assert "formatDate(scope.history_from_date)" in _source("sales_forecast")
	assert "formatDate(scope.history_to_date)" in _source("sales_forecast")
	assert "formatDate(scope.from_date)" in _source("customer_sales")
	assert "formatDate(scope.to_date)" in _source("customer_sales")
	assert "formatDate(scope.current_from_date)" in _source("customer_opportunity")
	assert "formatDate(scope.prior_from_date)" in _source("customer_opportunity")
	assert "formatDate(scope.from_date)" in _source("inventory_insights")
	assert "formatDate(scope.from_date)" in _source("inventory_intelligence")
	assert "formatDate(this.comparison.previous_from_date)" in _source("profitability")


def test_date_inputs_remain_native_iso_controls():
	for key in ("forecasting_planning", "sales_forecast", "inventory_insights", "profitability"):
		assert 'type="date"' in _source(key), key
