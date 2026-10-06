from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "retailedge" / "public" / "js"

PERIOD_SURFACES = (
	ROOT / "money_overview" / "MoneyOverview.vue",
	ROOT / "payment_management" / "PaymentHistoryPanel.vue",
	ROOT / "customer_sales_intelligence" / "CustomerSalesIntelligence.vue",
	ROOT / "customer_360" / "Customer360.vue",
	ROOT / "action_center" / "ActionCenter.vue",
	ROOT / "basket_affinity" / "BasketAffinity.vue",
)


def _source(path):
	return path.read_text()


def test_analytical_period_surfaces_use_shared_fuzzy_date_control():
	for path in PERIOD_SURFACES:
		text = _source(path)
		assert '"EdgeSmartDateRange"' in text, path
		assert "<EdgeSmartDateRange" in text, path
		assert 'label="Period"' in text, path
		assert '@resolved="onSmartDateResolved"' in text, path


def test_analytical_period_surfaces_do_not_expose_dual_native_date_inputs():
	for path in PERIOD_SURFACES:
		text = _source(path)
		assert 'type="date"' not in text, path
		assert 'v-model="filters.from_date"' not in text, path
		assert 'v-model="filters.to_date"' not in text, path


def test_fuzzy_date_resolution_keeps_exact_backend_filter_contract():
	for path in PERIOD_SURFACES:
		text = _source(path)
		assert "onSmartDateResolved(value)" in text, path
		assert "this.filters.from_date = value.from_date" in text, path
		assert "this.filters.to_date = value.to_date" in text, path
		assert "this.smartDate = { ...value }" in text, path


def test_fuzzy_date_uses_stable_reference_date_on_every_migrated_surface():
	for path in PERIOD_SURFACES:
		text = _source(path)
		assert "smartDateReference" in text, path
		assert ':referenceDate="smartDateReference || null"' in text, path


def test_fuzzy_date_fields_can_shrink_inside_filter_grids_without_forcing_overlap():
	css_contracts = {
		"MoneyOverview.vue": "money-period-filter { min-width: 0; width: 100%; }",
		"PaymentHistoryPanel.vue": "history-period-filter { min-width:0; width:100%; }",
		"CustomerSalesIntelligence.vue": "customer-period-filter {",
		"Customer360.vue": "customer-360-period-filter { min-width: 0; width: 100%; }",
		"ActionCenter.vue": "action-center-period-filter { min-width: 0; width: 100%; }",
		"BasketAffinity.vue": "basket-affinity-period-filter { min-width: 0; width: 100%; }",
	}
	for path in PERIOD_SURFACES:
		text = _source(path)
		assert css_contracts[path.name] in text, path
