from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "salesperson_performance.py"
DASHBOARD_API = APP_ROOT / "salesperson_performance_dashboard.py"
DASHBOARD_FILES = APP_ROOT / "dashboard_files.py"
COMPONENT = (
	APP_ROOT
	/ "public"
	/ "js"
	/ "salesperson_performance_dashboard"
	/ "SalespersonPerformanceDashboardV2.vue"
)
LEGACY_COMPONENT = (
	APP_ROOT
	/ "public"
	/ "js"
	/ "salesperson_performance_dashboard"
	/ "SalespersonPerformanceDashboard.vue"
)
BUNDLE = APP_ROOT / "public" / "js" / "salesperson_performance.bundle.js"


def test_salesperson_backend_enforces_company_and_branch_scope():
	source = BACKEND.read_text()
	assert 'conditions.append("si.company = %s")' in source
	assert "company=company or None" in source
	assert 'branch=filters.get("branch")' in source
	assert "MAX_PAGE_SIZE = 100" in source
	assert "MAX_EXPORT_ROWS = 500" in source
	assert "si.docstatus = 1" in source
	assert "allocated_percentage" in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit()" not in source


def test_salesperson_dashboard_adapter_uses_existing_engine_and_bounded_searches():
	source = DASHBOARD_API.read_text()
	assert "get_salesperson_performance" in source
	assert "MAX_EXPORT_ROWS" in source
	assert "MAX_LINK_RESULTS" in source
	assert 'DASHBOARD_KEY = "salesperson-performance"' in source
	assert "require_dashboard_action(" in source
	assert '"view"' in source
	assert "frappe.get_list(" in source
	assert "limit_page_length=MAX_LINK_RESULTS" in source
	assert "frappe.get_all(" not in source
	assert "ignore_permissions" not in source


def test_mounted_salesperson_dashboard_uses_shared_dashboard_shell():
	bundle = BUNDLE.read_text()
	component = COMPONENT.read_text()
	assert "SalespersonPerformanceDashboardV2.vue" in bundle
	assert 'SalespersonPerformanceDashboard.vue"' not in bundle
	for expected in (
		"EdgeAppShell",
		"EdgeDashboardShell",
		"EdgeDashboardGrid",
		"EdgeDashboardSection",
		"EdgeReportTable",
		"EdgeLinkField",
	):
		assert expected in component
	assert ':exportEnabled="rows.length > 0 && capabilities.can_export"' in component
	assert ':printEnabled="rows.length > 0 && capabilities.can_print"' in component
	assert '@export="handleExport"' in component
	assert '@print="handlePrint"' in component
	assert "getDashboardCapabilities" in component
	assert "exportDashboard" in component
	assert "printDashboard" in component
	assert "<table" not in component
	assert "frappe.db" not in component


def test_salesperson_dashboard_keeps_source_drilldowns_and_pagination():
	source = COMPONENT.read_text()
	for expected in (
		'frappe.set_route("Form", "Sales Person", row.salesperson)',
		'frappe.set_route("Form", "Sales Invoice", row.sales_invoice)',
		'frappe.set_route("Form", "Customer", row.customer)',
		"pagination.has_previous",
		"pagination.has_next",
		"changePage(-1)",
		"changePage(1)",
	):
		assert expected in source


def test_governed_dashboard_file_service_has_salesperson_export_adapter():
	source = DASHBOARD_FILES.read_text()
	assert '"salesperson-performance"' in source
	assert "_build_salesperson_dashboard_dataset" in source
	assert "export_mode=True" in source
	assert "require_dashboard_action(" in source
	assert '"export"' in source
	assert '"print"' in source


def test_legacy_salesperson_component_is_retained_for_rollback_reference():
	assert LEGACY_COMPONENT.exists()
	legacy = LEGACY_COMPONENT.read_text()
	assert "get_salesperson_performance" in legacy
	assert "Salesperson Performance Dashboard" in legacy
