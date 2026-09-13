from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/sales_quality_intelligence/SalesQualityIntelligence.vue"


def test_sales_quality_option_search_passes_current_reporting_period():
	source = VUE.read_text(encoding="utf-8")
	search_start = source.index("async searchOptions")
	search_block = source[search_start : search_start + 700]

	assert "company: this.filters.company" in search_block
	assert "branch: this.filters.branch" in search_block
	assert "from_date: this.filters.from_date" in search_block
	assert "to_date: this.filters.to_date" in search_block


def test_sales_quality_date_changes_clear_period_dependent_customer_and_salesperson():
	source = VUE.read_text(encoding="utf-8")

	assert '@change="onReportingDateChange"' in source
	handler_start = source.index("onReportingDateChange()")
	handler_block = source[handler_start : handler_start + 300]
	assert 'this.filters.customer = "";' in handler_block
	assert 'this.filters.salesperson = "";' in handler_block
	assert "this.page = 1;" in handler_block


def test_sales_quality_keeps_existing_non_date_cascade_contract():
	source = VUE.read_text(encoding="utf-8")

	company_start = source.index("onCompanySelected(option)")
	company_block = source[company_start : company_start + 500]
	assert 'this.filters.branch = "";' in company_block
	assert 'this.filters.customer = "";' in company_block
	assert 'this.filters.salesperson = "";' in company_block
	assert 'this.filters.item_group = "";' in company_block
	assert 'this.filters.item_code = "";' in company_block
	assert 'this.filters.warehouse = "";' in company_block

	item_group_start = source.index("onItemGroupSelected(option)")
	item_group_block = source[item_group_start : item_group_start + 250]
	assert 'this.filters.item_code = "";' in item_group_block
