from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public/js"
INSIGHT_VIEW = ROOT / "inventory_insights/InventoryInsightView.vue"
INTELLIGENCE_CENTRE = ROOT / "inventory_intelligence/InventoryIntelligenceCentre.vue"
FILES = (INSIGHT_VIEW, INTELLIGENCE_CENTRE)


def test_inventory_surfaces_consume_native_desk_capability_and_guard_shell_routes():
	for path in FILES:
		source = path.read_text(encoding="utf-8")
		assert "canUseNativeDesk: false" in source, path
		assert "Boolean(navigation.access?.can_use_native_desk)" in source, path
		assert '["DocType", "Report"].includes(item.target_type)' in source, path
		assert "!this.canUseNativeDesk" in source, path


def test_native_inventory_detail_cells_and_handlers_fail_closed():
	insight = INSIGHT_VIEW.read_text(encoding="utf-8")
	centre = INTELLIGENCE_CENTRE.read_text(encoding="utf-8")
	assert 'clickable: this.canUseNativeDesk && ["item_code", "source_warehouse", "target_warehouse"].includes(column.fieldname)' in insight
	assert "if (!this.canUseNativeDesk || !payload?.value) return" in insight
	assert 'clickable: this.canUseNativeDesk && column.fieldname === "item_code"' in centre
	assert "openReportCell(payload) {\n\t\t\tif (!this.canUseNativeDesk) return" in centre


def test_guided_transfer_stays_available_while_native_fallback_is_contained():
	source = INSIGHT_VIEW.read_text(encoding="utf-8")
	assert ':nativeFallbackEnabled="canUseNativeDesk"' in source
	assert "Advanced: Open Stock Entry" in source
	assert ':disabled="selectedRow.requires_full_stock_entry && !canUseNativeDesk"' in source
	assert "if (row.requires_full_stock_entry) {\n\t\t\t\tif (!this.canUseNativeDesk) return" in source
	assert "openNativeStockEntry() {\n\t\t\tif (!this.canUseNativeDesk) return" in source
	assert 'if (this.canUseNativeDesk) frappe.set_route("Form", result.doctype || "Stock Entry", result.name)' in source
	assert "Stock Transfer ${result.name} saved as Draft" in source
