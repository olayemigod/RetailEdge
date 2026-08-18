from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JS = APP_ROOT / "public" / "js"
PAGE_ROOT = APP_ROOT / "retailedge" / "page"
CAPABILITIES = APP_ROOT / "reporting_capabilities.py"
ACTIONS = APP_ROOT / "reporting_actions.py"
BROWSER_ACTIONS = PUBLIC_JS / "retailedge_reporting_actions.js"


@dataclass(frozen=True)
class ReportingSurface:
	key: str
	route: str
	bundle: str
	component: str
	provider_factory: str
	max_dataset_rows: int | None = None


REPORTING_SURFACES = (
	ReportingSurface(
		key="cash-movement",
		route="cash-movement",
		bundle="cash_movement.bundle.js",
		component="cash_movement/CashMovementReport.vue",
		provider_factory="createPaginatedReportProvider",
	),
	ReportingSurface(
		key="expense-register",
		route="expense-register",
		bundle="expense_register.bundle.js",
		component="expense_register/ExpenseRegisterReport.vue",
		provider_factory="createPaginatedReportProvider",
	),
	ReportingSurface(
		key="sales-by-item",
		route="sales-by-item",
		bundle="sales_reporting.bundle.js",
		component="sales_reporting/SalesReportingReport.vue",
		provider_factory="createBoundedPaginatedReportProvider",
		max_dataset_rows=10000,
	),
	ReportingSurface(
		key="sales-invoice-register",
		route="sales-invoice-register",
		bundle="sales_reporting.bundle.js",
		component="sales_reporting/SalesReportingReport.vue",
		provider_factory="createBoundedPaginatedReportProvider",
		max_dataset_rows=2000,
	),
	ReportingSurface(
		key="stock-position",
		route="stock-position",
		bundle="stock_position.bundle.js",
		component="stock_position/StockPositionReport.vue",
		provider_factory="createBoundedPaginatedReportProvider",
		max_dataset_rows=10000,
	),
	ReportingSurface(
		key="purchase-register",
		route="purchase-register",
		bundle="purchase_reporting.bundle.js",
		component="purchase_reporting/PurchaseReportingReport.vue",
		provider_factory="createBoundedPaginatedReportProvider",
		max_dataset_rows=2000,
	),
	ReportingSurface(
		key="supplier-payables",
		route="supplier-payables",
		bundle="purchase_reporting.bundle.js",
		component="purchase_reporting/PurchaseReportingReport.vue",
		provider_factory="createBoundedPaginatedReportProvider",
		max_dataset_rows=2000,
	),
	ReportingSurface(
		key="customer-receivables",
		route="customer-receivables",
		bundle="customer_receivables.bundle.js",
		component="customer_receivables/CustomerReceivablesReport.vue",
		provider_factory="createBoundedPaginatedReportProvider",
		max_dataset_rows=2000,
	),
)


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_owner_facing_reporting_pages_use_shared_edgesuite_shell_and_no_manual_tables():
	checked_components: set[str] = set()
	for surface in REPORTING_SURFACES:
		if surface.component in checked_components:
			continue
		checked_components.add(surface.component)
		source = _read(PUBLIC_JS / surface.component)
		assert "EdgeReportShell" in source, surface.component
		assert "<table" not in source.lower(), surface.component
		assert "ignore_permissions" not in source


def test_reporting_page_loaders_keep_edgesuite_as_the_single_shell():
	for surface in REPORTING_SURFACES:
		page_dir = PAGE_ROOT / surface.route.replace("-", "_")
		loader = _read(page_dir / f'{surface.route.replace("-", "_")}.js')
		page_json = _read(page_dir / f'{surface.route.replace("-", "_")}.json')
		assert 'edgeui.bundle.js' in loader
		assert surface.bundle in loader
		assert "hideNativePageSidebar" in loader
		assert f'"page_name": "{surface.route}"' in page_json


def test_registered_report_providers_use_the_declared_pagination_model_and_governed_export():
	for surface in REPORTING_SURFACES:
		bundle = _read(PUBLIC_JS / surface.bundle)
		assert surface.provider_factory in bundle, surface.key
		assert surface.key in bundle
		assert "retailedge.reporting_actions.get_report_export_data" in bundle
		assert "maxPageLength: 100" in bundle
		if surface.max_dataset_rows is not None:
			assert f"maxDatasetRows: {surface.max_dataset_rows}" in bundle, surface.key


def test_all_owner_facing_report_keys_are_governed_for_view_print_and_export():
	capabilities = _read(CAPABILITIES)
	actions = _read(ACTIONS)
	browser_actions = _read(BROWSER_ACTIONS)
	for surface in REPORTING_SURFACES:
		assert f'"{surface.key}"' in capabilities, surface.key
		assert surface.key in actions, surface.key
		assert f'"/app/{surface.route}": "{surface.key}"' in browser_actions, surface.key
	for forbidden in ("ignore_permissions", "frappe.db.commit()"):
		assert forbidden not in capabilities
		assert forbidden not in actions


def test_current_balance_reports_do_not_offer_fake_historical_as_of_semantics():
	for relative_path in (
		"customer_receivables/CustomerReceivablesReport.vue",
		"purchase_reporting/PurchaseReportingReport.vue",
	):
		source = _read(PUBLIC_JS / relative_path)
		assert 'type="date"' not in source or "As of Date" not in source
	for backend in (
		APP_ROOT / "customer_receivables.py",
		APP_ROOT / "supplier_payables.py",
	):
		source = _read(backend)
		assert "historical_balance_supported" in source
		assert "outstanding_amount" in source


def test_stock_movement_remains_an_explicit_preview_until_deferred_qa_resumes():
	preview_page = PAGE_ROOT / "stock_movement_history"
	assert preview_page.exists()
	browser_actions = _read(BROWSER_ACTIONS)
	assert '"/app/stock-movement-history": "stock-movement-history"' not in browser_actions
