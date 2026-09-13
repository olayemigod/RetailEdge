from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public/js"
FILES = (
	ROOT / "customer_360/Customer360.vue",
	ROOT / "customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue",
	ROOT / "customer_sales_intelligence/CustomerSalesIntelligence.vue",
	ROOT / "basket_affinity/BasketAffinity.vue",
	ROOT / "sales_quality_intelligence/SalesQualityIntelligence.vue",
)


def test_all_scoped_pages_consume_native_desk_capability_and_guard_shell_routes():
	for path in FILES:
		source = path.read_text(encoding="utf-8")
		assert "canUseNativeDesk: false" in source, path
		assert "Boolean(navigation.access?.can_use_native_desk)" in source, path
		assert '["DocType", "Report"].includes(item.target_type)' in source, path
		assert "!this.canUseNativeDesk" in source, path


def test_customer_360_preserves_identity_and_contains_native_forms():
	source = FILES[0].read_text(encoding="utf-8")
	assert "Advanced: Open Customer" in source
	assert source.count('v-if="canUseNativeDesk"') >= 3
	assert "if (!this.canUseNativeDesk || !name) return" in source
	assert "row.item_name || row.item_code" in source
	assert "row.invoice" in source


def test_edgesuite_customer_360_transitions_remain_available():
	for path in FILES[1:3]:
		source = path.read_text(encoding="utf-8")
		assert 'frappe.set_route("customer-360")' in source
		assert 'clickable: column.fieldname === "customer"' in source


def test_native_analytical_detail_cells_are_capability_gated():
	for path in FILES[3:]:
		source = path.read_text(encoding="utf-8")
		assert "clickable: this.canUseNativeDesk &&" in source
		assert "openReportCell(payload) { if (!this.canUseNativeDesk) return;" in source
