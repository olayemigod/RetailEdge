from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


def test_shared_inventory_insight_component_reuses_edgesuite_and_guided_transfer():
	component = (
		APP_ROOT / "public" / "js" / "inventory_insights" / "InventoryInsightView.vue"
	).read_text(encoding="utf-8")
	dialog = (
		APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleStockTransferDialog.vue"
	).read_text(encoding="utf-8")
	bundle = (APP_ROOT / "public" / "js" / "inventory_insights.bundle.js").read_text(encoding="utf-8")

	for token in ("EdgeAppShell", "EdgeReportShell", "EdgeLinkField"):
		assert token in component
	assert "SimpleStockTransferDialog" in component
	assert "../retailedge_business_hub/SimpleStockTransferDialog.vue" in component
	assert ':prefill="guidedTransferPrefill"' in component
	for token in (
		"source_warehouse: row.source_warehouse",
		"target_warehouse: row.target_warehouse",
		"item_code: row.item_code",
		"qty: Number(row.suggested_transfer_qty",
	):
		assert token in component
	assert 'prefill: { type: Object, default: () => ({}) }' in dialog
	assert "await this.applyPrefill()" in dialog
	assert "await this.setSourceWarehouse(sourceWarehouse)" in dialog
	assert "await this.setTargetWarehouse(targetWarehouse)" in dialog
	assert "this.values.items = [{ item_code: itemCode, qty }]" in dialog
	assert "retailedge.stock_position.search_stock_position_options" in component
	assert "resolve_branch_warehouse_selection" in component
	assert "from_date" in component and "to_date" in component
	assert "Age Bands (Days)" in component
	assert 'age_ranges: "30,60,90,180"' in component
	assert "Aged Stock Threshold (Days)" in component
	assert "aged_threshold_days: 90" in component
	assert "delete filters.age_ranges" in component
	assert "@sort-change=\"changeSort\"" in component
	assert "sort_field" in component and "sort_direction" in component
	assert 'window.open(`/app/item/${encodeURIComponent(payload.value)}`' in component
	assert 'window.open(`/app/warehouse/${encodeURIComponent(payload.value)}`' in component
	assert 'window.open("/app/stock-entry", "_blank", "noopener,noreferrer")' in component
	assert "never create or submit Stock Entries automatically" in component
	assert "R10 does not recalculate margin" in component
	assert "mountInventoryInsightView" in bundle
	assert "get_inventory_insight_view" in bundle


def test_inventory_insight_pages_use_shared_bundle_and_expected_views():
	pages = {
		"inventory_ageing": ("ageing", "Inventory Ageing"),
		"inventory_transfer_opportunities": ("transfer-opportunities", "Transfer Opportunities"),
		"inventory_profitability": ("profitability", "Inventory + Profitability"),
	}
	for directory, (view, title) in pages.items():
		page_dir = APP_ROOT / "retailedge" / "page" / directory
		js = (page_dir / f"{directory}.js").read_text(encoding="utf-8")
		page_json = (page_dir / f"{directory}.json").read_text(encoding="utf-8")
		assert 'const EDGEUI_ASSET = "edgeui.bundle.js"' in js
		assert 'const INVENTORY_INSIGHTS_ASSET = "inventory_insights.bundle.js"' in js
		assert f'const INSIGHT_VIEW = "{view}"' in js
		assert "mountInventoryInsightView" in js
		assert "document.createElement" in js
		assert "innerHTML" not in js
		assert title in page_json
		for role in (
			"System Manager",
			"Stock User",
			"Stock Manager",
			"RetailEdge Manager",
			"RetailEdge Branch Manager",
			"RetailEdge Auditor",
		):
			assert role in page_json