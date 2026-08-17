from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = APP_ROOT / "reporting_capabilities.py"
ACTIONS = APP_ROOT / "reporting_actions.py"
FILES = APP_ROOT / "reporting_files.py"
BROWSER_ACTIONS = APP_ROOT / "public" / "js" / "retailedge_reporting_actions.js"
PATCH = APP_ROOT / "patches" / "add_reporting_action_settings.py"
PATCHES = APP_ROOT / "patches.txt"

BUNDLES = (
	APP_ROOT / "public" / "js" / "cash_movement.bundle.js",
	APP_ROOT / "public" / "js" / "expense_register.bundle.js",
	APP_ROOT / "public" / "js" / "sales_reporting.bundle.js",
	APP_ROOT / "public" / "js" / "purchase_reporting.bundle.js",
	APP_ROOT / "public" / "js" / "stock_position.bundle.js",
	APP_ROOT / "public" / "js" / "stock_movement_history.bundle.js",
)


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_reporting_capabilities_use_settings_scope_roles_and_document_read_permission():
	source = _read(CAPABILITIES)
	for expected in (
		'PRINT_SETTING = "enable_reporting_print"',
		'EXPORT_SETTING = "enable_reporting_export"',
		'"can_view": can_view',
		'"can_print": can_print',
		'"can_export": can_export',
		'"authorization_model": "settings_scope_role_and_document_permission"',
		'frappe.has_permission(spec.ref_doctype, ptype="read", user=user)',
		"validate_user_branch_access",
		"require_report_action",
	):
		assert expected in source

	for report_key in (
		"sales-by-item",
		"sales-invoice-register",
		"purchase-register",
		"supplier-payables",
		"stock-position",
		"stock-movement-history",
		"expense-register",
		"cash-movement",
	):
		assert f'"{report_key}"' in source

	for forbidden in ("ignore_permissions", "frappe.db.commit()"):
		assert forbidden not in source


def test_reporting_action_settings_are_idempotent_and_registered():
	patch = _read(PATCH)
	patches = _read(PATCHES)
	for expected in (
		'"enable_reporting_print"',
		'"enable_reporting_export"',
		'"RetailEdge Settings"',
		'frappe.db.exists("Custom Field", name)',
	):
		assert expected in patch
	assert "retailedge.patches.add_reporting_action_settings" in patches


def test_export_wrapper_rechecks_action_before_existing_bounded_report_backend():
	source = _read(ACTIONS)
	assert 'action="export"' in source
	assert "require_report_action(" in source
	assert "get_report_dataset" in source
	assert "handler = _export_handler(report_key)" in source
	assert "return handler(filters=resolved_filters)" in source
	for backend in (
		"get_sales_by_item_export",
		"get_sales_invoice_register_export",
		"get_purchase_register_export",
		"get_supplier_payables_export",
		"get_stock_position_export",
		"get_stock_movement_export",
		"get_expense_register_export",
		"get_cash_movement_export",
	):
		assert backend in source
	assert "ignore_permissions" not in source


def test_report_file_service_keeps_print_and_export_permissions_independent():
	source = _read(FILES)
	assert 'require_report_action(report_key, action="export"' in source
	assert 'require_report_action(report_key, action="print"' in source
	assert "get_report_dataset(report_key, filters)" in source
	assert "get_report_export_data" not in source
	for expected in (
		'"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"',
		'"csv": "text/csv; charset=utf-8"',
		'"pdf": "application/pdf"',
		"make_xlsx",
		"get_pdf",
		"frappe.local.response.filecontent",
		"get_report_print_html",
		"_report_html",
	):
		assert expected in source
	assert "ignore_permissions" not in source


def test_all_registered_retailedge_report_providers_use_governed_export_route():
	for bundle in BUNDLES:
		source = _read(bundle)
		assert "retailedge.reporting_actions.get_report_export_data" in source
		assert "report_key:" in source


def test_browser_reporting_actions_use_native_shell_builder_and_verified_download():
	source = _read(BROWSER_ACTIONS)
	for expected in (
		"retailedge.reporting_capabilities.get_shell_capabilities",
		"retailedge.reporting_files.download_report",
		"retailedge.reporting_files.get_report_print_html",
		"EdgeSuiteReportExport",
		"downloadVerified",
		'registerComponent("EdgeReportShell", GovernedReportShell, { replace: true })',
		'registerComponent("EdgeExportMenu", GovernedLegacyExportMenu, { replace: true })',
		'"/app/purchase-register": "purchase-register"',
		'"/app/supplier-payables": "supplier-payables"',
		"exportEnabled",
		"printEnabled",
		"exportInitialOptions",
	):
		assert expected in source
	assert "ignore_permissions" not in source
