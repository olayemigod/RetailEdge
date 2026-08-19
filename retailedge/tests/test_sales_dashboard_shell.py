from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
API = APP_ROOT / "sales_dashboard.py"
CAPABILITIES = APP_ROOT / "dashboard_capabilities.py"
FILES = APP_ROOT / "dashboard_files.py"
COMPONENT = APP_ROOT / "public" / "js" / "sales_dashboard" / "SalesDashboard.vue"
BUNDLE = APP_ROOT / "public" / "js" / "sales_dashboard.bundle.js"
PAGE = APP_ROOT / "retailedge" / "page" / "sales_overview" / "sales_overview.js"
EDGE_NAVIGATION = APP_ROOT / "edgesuite_ui.py"


def test_sales_overview_uses_shared_edgesuite_dashboard_shell_and_downloads():
	source = COMPONENT.read_text()
	for component in ("EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"):
		assert component in source
	assert 'const DASHBOARD_KEY = "sales-overview"' in source
	assert "getDashboardCapabilities" in source
	assert "exportDashboard" in source
	assert "printDashboard" in source
	assert ':exportEnabled="Boolean(headlineSummary.length) && capabilities.can_export"' in source
	assert ':printEnabled="Boolean(headlineSummary.length) && capabilities.can_print"' in source
	assert "retailedge.sales_dashboard.get_sales_dashboard_data" in source
	assert "frappe.db" not in source


def test_sales_overview_page_mounts_edgesuite_runtime():
	page = PAGE.read_text()
	bundle = BUNDLE.read_text()
	assert 'const EDGEUI_ASSET = "edgeui.bundle.js"' in page
	assert 'const DASHBOARD_ASSET = "sales_dashboard.bundle.js"' in page
	assert "window.mountSalesDashboard" in page
	assert "createEdgeApp(SalesDashboard)" in bundle


def test_sales_overview_is_registered_in_shared_permission_and_file_matrix():
	capabilities = CAPABILITIES.read_text()
	files = FILES.read_text()
	assert '"sales-overview": DashboardCapabilitySpec(' in capabilities
	assert 'key="sales-overview"' in capabilities
	assert '"sales-overview": lambda filters, _all_filtered: build_sales_dashboard_export_dataset(filters)' in files
	assert "require_dashboard_action" in files


def test_sales_overview_reuses_existing_sales_reports_only():
	source = API.read_text()
	assert "get_sales_invoice_register" in source
	assert "get_sales_by_item" in source
	assert "frappe.db.sql" not in source
	assert "frappe.get_list" not in source
	assert "frappe.get_all" not in source


def test_sales_overview_preview_is_not_promoted_before_browser_qa():
	navigation = EDGE_NAVIGATION.read_text()
	assert '"target": "sales-overview"' not in navigation
