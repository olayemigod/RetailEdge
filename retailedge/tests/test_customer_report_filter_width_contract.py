from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_SALES = ROOT / "public/js/customer_sales_intelligence/CustomerSalesIntelligence.vue"
CUSTOMER_OPPORTUNITY = ROOT / "public/js/customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue"


def _filter_grid_block(text: str, selector: str) -> str:
	start = text.index(selector)
	block_start = text.index("{", start)
	block_end = text.index("}", block_start)
	return text[block_start + 1 : block_end]


def test_customer_report_filter_grids_claim_full_width_inside_edgesuite_filter_bar():
	cases = (
		(CUSTOMER_SALES, ".customer-intelligence-filter-grid"),
		(CUSTOMER_OPPORTUNITY, ".customer-opportunity-filter-grid"),
	)

	for path, selector in cases:
		text = path.read_text(encoding="utf-8")
		block = _filter_grid_block(text, selector)
		assert "display: grid" in block
		assert "repeat(auto-fit, minmax(190px, 1fr))" in block
		assert "flex: 1 1 100%" in block
		assert "min-width: 0" in block
		assert "width: 100%" in block


def test_filter_width_fix_does_not_force_fixed_desktop_column_count():
	for path in (CUSTOMER_SALES, CUSTOMER_OPPORTUNITY):
		text = path.read_text(encoding="utf-8")
		assert "repeat(auto-fit, minmax(190px, 1fr))" in text
		assert "grid-template-columns: repeat(6" not in text
