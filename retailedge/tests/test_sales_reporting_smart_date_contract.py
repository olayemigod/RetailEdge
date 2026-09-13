from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "retailedge" / "public" / "js" / "sales_reporting" / "SalesReportingReport.vue"


def test_sales_reports_require_shared_smart_date_component():
	text = SOURCE.read_text()
	assert '"EdgeSmartDateRange"' in text
	assert "<EdgeSmartDateRange" in text
	assert '@resolved="onSmartDateResolved"' in text


def test_smart_date_uses_stable_server_reference_date():
	text = SOURCE.read_text()
	assert 'smartDateReference: ""' in text
	assert ':referenceDate="smartDateReference || null"' in text
	assert 'this.smartDateReference = context.default_filters?.to_date || this.filters.to_date || ""' in text
	assert ':referenceDate="filters.to_date || null"' not in text


def test_smart_date_resolution_only_updates_exact_report_dates():
	text = SOURCE.read_text()
	assert "onSmartDateResolved(value)" in text
	assert "this.filters.from_date = value.from_date" in text
	assert "this.filters.to_date = value.to_date" in text
	assert 'this.filters.date_range_preset = "Custom Period"' in text
	assert "this.currentPage = 1" in text


def test_provider_and_export_receive_exact_filters_not_free_text_expression():
	text = SOURCE.read_text()
	assert "providerFilters()" in text
	assert "const { page_size: _pageSize, date_range_preset: _preset, ...filters } = this.filters" in text
	assert "this.reportProvider.load({ filters: this.providerFilters()" in text
	assert "this.reportProvider.export({ filters: this.providerFilters() })" in text
	assert "smartDate" not in text.split("providerFilters()", 1)[1].split("async fetchData", 1)[0]


def test_existing_manual_and_preset_date_controls_remain_available_during_adoption():
	text = SOURCE.read_text()
	assert 'v-model="filters.date_range_preset"' in text
	assert 'v-model="filters.from_date"' in text
	assert 'v-model="filters.to_date"' in text
	assert "onPresetChange()" in text
	assert "onDateChange()" in text
