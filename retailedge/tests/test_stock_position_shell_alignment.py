from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = APP_ROOT / "public" / "js" / "stock_position.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "stock_position" / "StockPositionReport.vue"
LEGACY_COMPONENT = APP_ROOT / "public" / "js" / "stock_position" / "StockPosition.vue"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_stock_position_bundle_mounts_shared_shell_consumer_and_bounded_provider():
	bundle = read(BUNDLE)
	assert 'StockPositionReport from "./stock_position/StockPositionReport.vue"' in bundle
	assert "createEdgeApp(StockPositionReport)" in bundle
	assert "createBoundedPaginatedReportProvider" in bundle
	assert 'const REPORT_KEY = "stock-position"' in bundle
	assert "maxDatasetRows: 10000" in bundle
	assert "get_stock_position" in bundle
	assert "get_stock_position_export" in bundle


def test_shared_stock_position_consumer_uses_report_shell_without_custom_table_or_paginator():
	component = read(COMPONENT)
	for contract in (
		"EdgeAppShell",
		"EdgeReportShell",
		"EdgeLinkField",
		"EdgeExportMenu",
		'const REPORT_KEY = "stock-position"',
		"reportProvider.load",
		"reportProvider.export",
		':pageSizes="[25, 50, 100]"',
		"search_stock_position_options",
		"resolve_branch_warehouse_selection",
		"Include zero rows",
		"Cost values hidden by RetailEdge settings",
		"Bounded server dataset",
	):
		assert contract in component
	assert "<table" not in component
	assert "pagination-footer" not in component
	assert "new Blob" not in component
	assert "createObjectURL" not in component
	assert "setInterval(" not in component


def test_stock_context_cascades_cost_visibility_and_item_drilldown_remain_product_owned():
	component = read(COMPONENT)
	for contract in (
		'this.filters.branch = ""',
		'this.filters.warehouse = ""',
		'this.filters.item_code = ""',
		"this.showCosts = Boolean(Number(result.metadata?.show_costs))",
		'frappe.set_route("Form", "Item", itemCode)',
	):
		assert contract in component


def test_original_stock_position_component_is_retained_as_rollback_reference():
	assert LEGACY_COMPONENT.exists()
	legacy = read(LEGACY_COMPONENT)
	assert 'name: "StockPosition"' in legacy
	assert "get_stock_position" in legacy
	assert "get_stock_position_export" in legacy
