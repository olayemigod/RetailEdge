from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JS = APP_ROOT / "public" / "js"

CANONICAL_REPORT_COMPONENTS = {
    "cash_movement.bundle.js": "./cash_movement/CashMovementReport.vue",
    "expense_register.bundle.js": "./expense_register/ExpenseRegisterReport.vue",
    "sales_reporting.bundle.js": "./sales_reporting/SalesReportingReport.vue",
    "stock_position.bundle.js": "./stock_position/StockPositionReport.vue",
}

SUPERSEDED_COMPONENTS = (
    PUBLIC_JS / "cash_movement" / "CashMovement.vue",
    PUBLIC_JS / "expense_register" / "ExpenseRegister.vue",
    PUBLIC_JS / "sales_reporting" / "SalesReportingPage.vue",
    PUBLIC_JS / "stock_position" / "StockPosition.vue",
)


def test_r1_r4_report_bundles_have_one_canonical_component_owner():
    for bundle_name, component_path in CANONICAL_REPORT_COMPONENTS.items():
        source = (PUBLIC_JS / bundle_name).read_text(encoding="utf-8")
        assert component_path in source


def test_superseded_parallel_report_components_are_removed():
    for path in SUPERSEDED_COMPONENTS:
        assert not path.exists(), f"Superseded parallel UI implementation still exists: {path}"


def test_frappe_pages_mount_bundles_instead_of_parallel_vue_implementations():
    page_assets = {
        "cash_movement": "cash_movement.bundle.js",
        "expense_register": "expense_register.bundle.js",
        "sales_by_item": "sales_reporting.bundle.js",
        "sales_invoice_register": "sales_reporting.bundle.js",
        "stock_position": "stock_position.bundle.js",
    }
    for page_name, asset in page_assets.items():
        page_js = APP_ROOT / "retailedge" / "page" / page_name / f"{page_name}.js"
        source = page_js.read_text(encoding="utf-8")
        assert asset in source
        assert ".vue" not in source
