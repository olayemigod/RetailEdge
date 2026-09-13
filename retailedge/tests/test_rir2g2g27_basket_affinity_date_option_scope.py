from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/basket_affinity/BasketAffinity.vue"


def test_basket_affinity_option_search_passes_current_reporting_period():
	source = VUE.read_text(encoding="utf-8")
	search_start = source.index("async searchOptions")
	search_block = source[search_start : search_start + 750]

	assert "company: this.filters.company" in search_block
	assert "branch: this.filters.branch" in search_block
	assert "item_group: this.filters.item_group" in search_block
	assert "from_date: this.filters.from_date" in search_block
	assert "to_date: this.filters.to_date" in search_block


def test_basket_affinity_date_changes_clear_period_dependent_people_filters():
	source = VUE.read_text(encoding="utf-8")

	assert '@change="onAffinityDateChange"' in source
	handler_start = source.index("onAffinityDateChange()")
	handler_block = source[handler_start : handler_start + 320]
	assert 'this.filters.customer = "";' in handler_block
	assert 'this.filters.salesperson = "";' in handler_block
	assert "this.page = 1;" in handler_block


def test_basket_affinity_existing_company_branch_and_product_cascades_remain():
	source = VUE.read_text(encoding="utf-8")

	company_start = source.index("onCompanySelected(option)")
	company_block = source[company_start : company_start + 500]
	assert 'this.filters.branch = "";' in company_block
	assert 'this.filters.customer = "";' in company_block
	assert 'this.filters.salesperson = "";' in company_block
	assert 'this.filters.item_group = "";' in company_block
	assert 'this.filters.item_code = "";' in company_block

	branch_start = source.index("onBranchSelected(option)")
	branch_block = source[branch_start : branch_start + 350]
	assert 'this.filters.customer = "";' in branch_block
	assert 'this.filters.salesperson = "";' in branch_block

	item_group_start = source.index("onItemGroupSelected(option)")
	item_group_block = source[item_group_start : item_group_start + 300]
	assert 'this.filters.item_code = "";' in item_group_block


def test_basket_affinity_native_item_detail_remains_capability_gated():
	source = VUE.read_text(encoding="utf-8")
	open_start = source.rindex("openReportCell(payload)")
	open_block = source[open_start : open_start + 500]
	assert "if (!this.canUseNativeDesk) return;" in open_block
	assert "/app/item/" in open_block
