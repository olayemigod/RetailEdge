from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = APP_ROOT / "public" / "js" / "sales_reporting.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "sales_reporting" / "SalesReportingReport.vue"
LEGACY_COMPONENT = APP_ROOT / "public" / "js" / "sales_reporting" / "SalesReportingPage.vue"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_sales_bundle_mounts_shared_shell_consumer_and_keeps_bounded_providers():
	bundle = read(BUNDLE)
	assert 'SalesReportingReport from "./sales_reporting/SalesReportingReport.vue"' in bundle
	assert "createEdgeApp(SalesReportingReport" in bundle
	assert "createBoundedPaginatedReportProvider" in bundle
	assert 'key: "sales-by-item"' in bundle
	assert 'key: "sales-invoice-register"' in bundle
	assert "maxDatasetRows: 10000" in bundle
	assert "maxDatasetRows: 2000" in bundle
	assert "get_sales_by_item_export" in bundle
	assert "get_sales_invoice_register_export" in bundle


def test_shared_sales_consumer_uses_edgesuite_report_shell_without_custom_table_or_paginator():
	component = read(COMPONENT)
	for contract in (
		"EdgeAppShell",
		"EdgeReportShell",
		"EdgeLinkField",
		"EdgeExportMenu",
		'providerKey: "sales-by-item"',
		'providerKey: "sales-invoice-register"',
		"reportProvider.load",
		"reportProvider.export",
		':pageSizes="[25, 50, 100]"',
		"search_sales_reporting_options",
		"resolve_branch_warehouse_selection",
		"Date Range",
		"More filters",
		"Salesperson",
		"Warehouse",
		"Bounded server dataset",
	):
		assert contract in component
	assert "<table" not in component
	assert "pagination-footer" not in component
	assert "new Blob" not in component
	assert "createObjectURL" not in component
	assert "setInterval(" not in component


def test_sales_drilldowns_and_filter_cascades_remain_product_owned():
	component = read(COMPONENT)
	for contract in (
		'frappe.set_route("Form", "Sales Invoice", value)',
		'frappe.set_route("Form", "Item", value)',
		'frappe.set_route("Form", "Customer", value)',
		'this.filters.branch = ""',
		'this.filters.warehouse = ""',
		'this.filters.item_code = ""',
		'this.filters.date_range_preset = "Custom Period"',
	):
		assert contract in component


def test_original_sales_component_is_retained_as_rollback_reference():
	assert LEGACY_COMPONENT.exists()
	legacy = read(LEGACY_COMPONENT)
	assert 'name: "SalesReportingPage"' in legacy
	assert "get_sales_by_item" in legacy
	assert "get_sales_invoice_register" in legacy
