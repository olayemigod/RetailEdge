from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "daily_sales_audit_page.py"
BUNDLE = APP_ROOT / "public" / "js" / "daily_sales_audit.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "daily_sales_audit" / "DailySalesAuditReport.vue"
PAGE_JS = APP_ROOT / "retailedge" / "page" / "daily_sales_audit" / "daily_sales_audit.js"
PAGE_JSON = APP_ROOT / "retailedge" / "page" / "daily_sales_audit" / "daily_sales_audit.json"
NAVIGATION = APP_ROOT / "edgesuite_ui.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_daily_sales_audit_preview_reuses_existing_audit_engine_with_bounded_dataset():
	source = _read(BACKEND)
	for expected in (
		"MAX_AUDIT_ROWS = 1000",
		"MAX_PAGE_SIZE = 100",
		"MAX_LINK_RESULTS = 20",
		"get_data(filters, limit_page_length=MAX_AUDIT_ROWS + 1)",
		"validate_filters(filters)",
		'frappe.has_permission("RetailEdge Daily Sales Audit", "read")',
		"get_daily_sales_audit_page_export",
	):
		assert expected in source
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source


def test_daily_sales_audit_uses_canonical_edgesuite_shell_provider_and_smart_links():
	component = _read(COMPONENT)
	bundle = _read(BUNDLE)
	loader = _read(PAGE_JS)

	for expected in (
		"EdgeAppShell",
		"EdgeReportShell",
		"EdgeLinkField",
		':hideNativeSidebar="true"',
		"search_daily_sales_audit_page_options",
		"providerDatasetLimit",
		"Legacy Daily Sales Audit Register retained for detailed comparison",
	):
		assert expected in component

	for expected in (
		"createBoundedPaginatedReportProvider",
		"maxDatasetRows: 1000",
		"maxPageLength: 100",
		"retailedge.reporting_actions.get_report_export_data",
		"createEdgeApp",
	):
		assert expected in bundle

	for expected in (
		'const EDGEUI_ASSET = "edgeui.bundle.js"',
		'const REPORTING_ASSET = "daily_sales_audit.bundle.js"',
		"hideNativePageSidebar",
		"renderLoadError",
		"window.mountDailySalesAuditPage",
	):
		assert expected in loader


def test_daily_sales_audit_preview_exists_but_primary_navigation_remains_native_until_browser_qa():
	page_json = _read(PAGE_JSON)
	navigation = _read(NAVIGATION)
	assert '"page_name": "daily-sales-audit"' in page_json
	assert '"label": "Daily Sales Audit", "target_type": "DocType", "target": "RetailEdge Daily Sales Audit"' in navigation
	assert '"target": "daily-sales-audit"' not in navigation
