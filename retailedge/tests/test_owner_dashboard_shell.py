from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
API = APP_ROOT / "owner_dashboard.py"
CAPABILITIES = APP_ROOT / "dashboard_capabilities.py"
FILES = APP_ROOT / "dashboard_files.py"
COMPONENT = APP_ROOT / "public" / "js" / "owner_dashboard" / "OwnerDashboard.vue"
BUNDLE = APP_ROOT / "public" / "js" / "owner_dashboard.bundle.js"
PAGE = APP_ROOT / "retailedge" / "page" / "owner_dashboard" / "owner_dashboard.js"
PAGE_JSON = APP_ROOT / "retailedge" / "page" / "owner_dashboard" / "owner_dashboard.json"
EDGE_NAVIGATION = APP_ROOT / "edgesuite_ui.py"


def test_owner_dashboard_fallback_composes_existing_reporting_services_only():
	source = API.read_text()
	for token in (
		"get_sales_invoice_register",
		"get_expense_register",
		"get_cash_movement",
		"get_customer_receivables",
		"get_supplier_payables",
		"get_stock_position",
		"get_branch_performance_dashboard_data",
	):
		assert token in source
	assert "frappe.db.sql" not in source
	assert "frappe.get_list" not in source
	assert 'require_dashboard_action(DASHBOARD_KEY, "view"' in source
	assert '"include_unposted_cashier_expenses": 0' in source


def test_financial_dashboard_uses_shared_signature_component_and_downloads():
	source = COMPONENT.read_text()
	for component in ("EdgeAppShell", "EdgeFinancialDashboard", "EdgeDropdown"):
		assert component in source
	assert 'const DASHBOARD_KEY = "owner-dashboard"' in source
	assert "getDashboardCapabilities" in source
	assert "exportDashboard" in source
	assert "printDashboard" in source
	assert ':exportEnabled="hasData && capabilities.can_export"' in source
	assert ':printEnabled="hasData && capabilities.can_print"' in source
	assert "retailedge.financial_dashboard.get_financial_dashboard_data" in source
	assert "EdgeDashboardGrid" not in source
	assert "frappe.db" not in source


def test_financial_dashboard_page_mounts_current_edgesuite_runtime_and_cached_refresh():
	page = PAGE.read_text()
	bundle = BUNDLE.read_text()
	assert 'const EDGEUI_ASSET = "edgeui.bundle.js"' in page
	assert 'const DASHBOARD_ASSET = "owner_dashboard.bundle.js"' in page
	assert 'const PAGE_TITLE = "Financial Dashboard"' in page
	assert "window.mountOwnerDashboard" in page
	assert "refreshPendingBusinessHubHandoff" in page
	assert 'window.addEventListener("retailedge:business-hub-handoff", refreshFromHandoff)' in page
	assert "createEdgeApp(OwnerDashboard)" in bundle
	assert "app.__retailedgeRootComponent = rootComponent" in bundle
	assert '"title": "Financial Dashboard"' in PAGE_JSON.read_text()


def test_financial_dashboard_is_registered_in_shared_permission_and_file_matrix():
	capabilities = CAPABILITIES.read_text()
	files = FILES.read_text()
	assert '"owner-dashboard": DashboardCapabilitySpec(' in capabilities
	assert 'key="owner-dashboard"' in capabilities
	assert "build_financial_dashboard_export_dataset" in files
	assert '"owner-dashboard": lambda filters, _all_filtered: build_financial_dashboard_export_dataset(filters)' in files
	assert "require_dashboard_action" in files


def test_financial_dashboard_is_promoted_to_insights_navigation():
	navigation = EDGE_NAVIGATION.read_text()
	assert '{"label": "Financial Dashboard", "target_type": "Page", "target": "owner-dashboard"' in navigation
