from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_API = APP_ROOT / "branch_performance_dashboard.py"
CAPABILITIES = APP_ROOT / "dashboard_capabilities.py"
DASHBOARD_FILES = APP_ROOT / "dashboard_files.py"
DASHBOARD_ACTIONS = APP_ROOT / "public" / "js" / "retailedge_dashboard_actions.js"
COMPONENT = APP_ROOT / "public" / "js" / "branch_performance_dashboard" / "BranchPerformanceDashboard.vue"
BUNDLE = APP_ROOT / "public" / "js" / "branch_performance_dashboard.bundle.js"
PAGE = APP_ROOT / "retailedge" / "page" / "branch_performance_dashboard" / "branch_performance_dashboard.js"
LEGACY_REPORT = (
	APP_ROOT
	/ "retailedge"
	/ "report"
	/ "retailedge_branch_performance_summary"
	/ "retailedge_branch_performance_summary.py"
)


def test_dashboard_reuses_existing_branch_performance_engine():
	source = DASHBOARD_API.read_text()
	assert "get_branch_performance_rows" in source
	assert "get_report_summary" in source
	assert "get_columns" in source
	assert "assert_can_access_branch_performance()" in source
	assert 'require_dashboard_action(DASHBOARD_KEY, "view"' in source
	assert "frappe.get_list" in source
	assert "MAX_LINK_RESULTS = 20" in source
	assert "frappe.get_all" not in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit()" not in source


def test_dashboard_uses_edgesuite_dashboard_shell_without_reimplementing_business_math():
	source = COMPONENT.read_text()
	for component in (
		"EdgeAppShell",
		"EdgeDashboardShell",
		"EdgeDashboardGrid",
		"EdgeDashboardSection",
		"EdgeReportTable",
		"EdgeLinkField",
	):
		assert component in source
	assert "retailedge.branch_performance_dashboard.get_branch_performance_dashboard_data" in source
	assert 'frappe.set_route("query-report", "RetailEdge Branch Performance Summary")' in source
	assert ':exportEnabled="rows.length > 0 && capabilities.can_export"' in source
	assert ':printEnabled="rows.length > 0 && capabilities.can_print"' in source
	assert '@export="handleExport"' in source
	assert '@print="handlePrint"' in source
	assert "payment_issues" in source
	assert "audit_variance" in source
	assert "gross_sales +" not in source
	assert "cash_sales -" not in source
	assert "frappe.db" not in source


def test_dashboard_page_mounts_shared_edgesuite_runtime():
	page = PAGE.read_text()
	bundle = BUNDLE.read_text()
	assert 'const EDGEUI_ASSET = "edgeui.bundle.js"' in page
	assert 'const DASHBOARD_ASSET = "branch_performance_dashboard.bundle.js"' in page
	assert "hideNativePageSidebar" in page
	assert "window.mountBranchPerformanceDashboard" in page
	assert "createEdgeApp(BranchPerformanceDashboard)" in bundle


def test_dashboard_capability_matrix_reuses_reporting_master_switches():
	source = CAPABILITIES.read_text()
	assert "EXPORT_SETTING" in source
	assert "PRINT_SETTING" in source
	assert '"branch-performance"' in source
	assert '"salesperson-performance"' in source
	assert '"scope_type": "dashboard"' in source
	assert '"can_print": can_print' in source
	assert '"can_export": can_export' in source
	assert "validate_user_branch_access" in source
	assert "ignore_permissions" not in source


def test_dashboard_file_service_rechecks_print_and_export_permissions():
	source = DASHBOARD_FILES.read_text()
	assert 'require_dashboard_action(\n\t\tscope_key,\n\t\t"export"' in source
	assert 'require_dashboard_action(\n\t\tscope_key,\n\t\t"print"' in source
	assert "get_branch_performance_dashboard_data" in source
	assert "get_pdf" in source
	assert "_xlsx_bytes" in source
	assert "_csv_bytes" in source
	assert "ignore_permissions" not in source


def test_dashboard_browser_actions_use_edgesuite_verified_download():
	source = DASHBOARD_ACTIONS.read_text()
	assert "retailedge.dashboard_capabilities.get_dashboard_shell_capabilities" in source
	assert "retailedge.dashboard_files.download_dashboard" in source
	assert "retailedge.dashboard_files.get_dashboard_print_html" in source
	assert "downloadVerified" in source
	assert "X-Frappe-CSRF-Token" in source


def test_native_branch_performance_report_is_retained_as_detail_fallback():
	assert LEGACY_REPORT.exists()
	legacy = LEGACY_REPORT.read_text()
	assert "get_branch_performance_rows" in legacy
	assert "get_report_summary" in legacy
