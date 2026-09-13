from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JS = ROOT / "public" / "js"
BUSINESS_HUB = PUBLIC_JS / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
MASTER_EXPERIENCE = ROOT / "master_experience.py"
HOOKS = ROOT / "hooks.py"
GLOBAL_JS = PUBLIC_JS / "retailedge.js"

EDGE_DROPDOWN_MVP_SURFACES = (
    PUBLIC_JS / "operating_context" / "OperatingContext.vue",
    PUBLIC_JS / "stock_position" / "StockPositionReport.vue",
    PUBLIC_JS / "action_center" / "ActionCenter.vue",
    PUBLIC_JS / "branch_performance_dashboard" / "BranchPerformanceDashboard.vue",
    PUBLIC_JS / "customer_receivables" / "CustomerReceivablesReport.vue",
    PUBLIC_JS / "purchase_reporting" / "PurchaseReportingReport.vue",
    PUBLIC_JS / "sales_reporting" / "SalesReportingReport.vue",
    PUBLIC_JS / "business_control_center" / "BusinessControlCenter.vue",
)

PLAIN_VALUE_MVP_SURFACES = (
    BUSINESS_HUB,
    PUBLIC_JS / "owner_dashboard" / "OwnerDashboard.vue",
    PUBLIC_JS / "sales_dashboard" / "SalesDashboard.vue",
    PUBLIC_JS / "money_overview" / "MoneyOverview.vue",
    PUBLIC_JS / "stock_position" / "StockPositionReport.vue",
    PUBLIC_JS / "branch_performance_dashboard" / "BranchPerformanceDashboard.vue",
    PUBLIC_JS / "expense_dashboard" / "ExpenseDashboard.vue",
    PUBLIC_JS / "customer_receivables" / "CustomerReceivablesReport.vue",
    PUBLIC_JS / "purchase_reporting" / "PurchaseReportingReport.vue",
    PUBLIC_JS / "sales_reporting" / "SalesReportingReport.vue",
    PUBLIC_JS / "business_control_center" / "BusinessControlCenter.vue",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_business_hub_is_the_retailedge_app_home_and_legacy_workspace_is_contained():
    hooks = read(HOOKS)
    global_js = read(GLOBAL_JS)

    assert 'app_home = "/desk/retailedge-business-hub"' in hooks
    assert 'const RETAILEDGE_BUSINESS_HUB_ROUTE = "retailedge-business-hub"' in global_js
    assert "redirectLegacyRetailEdgeWorkspace" in global_js
    assert '"workspace/retailedge"' in global_js
    assert '"workspaces/retailedge"' in global_js
    assert '"/app/retailedge"' in global_js


def test_business_hub_exposes_company_identity_and_permission_safe_branch_switcher():
    backend = read(MASTER_EXPERIENCE)
    frontend = read(BUSINESS_HUB)

    for contract in (
        "get_allowed_operating_contexts",
        "company_label",
        "company_logo",
        "company_currency",
        "branch_options",
        "can_switch_branch",
    ):
        assert contract in backend

    for contract in (
        "retailedge-context-bar",
        "retailedge-company-identity",
        "context.company_logo",
        "context.company_label",
        "<EdgeDropdown",
        'label="Working branch"',
        "switch_operating_context",
        "branchSwitching",
    ):
        assert contract in frontend


def test_create_picker_uses_product_menu_visual_language_and_shared_icons():
    source = read(BUSINESS_HUB)

    for contract in (
        "create-product-menu",
        "create-product-menu-header",
        "create-picker-list",
        "<EdgeIcon",
        "create-picker-icon",
        "home-kpi-card-icon",
        "home-signal-icon",
        "kpiIcon(",
        "signalIcon(",
    ):
        assert contract in source


def test_primary_mvp_dropdowns_use_shared_edge_dropdown():
    for path in EDGE_DROPDOWN_MVP_SURFACES:
        source = read(path)
        assert "EdgeDropdown" in source, path
        assert "<select" not in source, path


def test_primary_mvp_vue_surfaces_never_render_frappe_formatter_html():
    global_js = read(GLOBAL_JS)
    assert "formatPlainValue" in global_js
    assert "toPlainText" in global_js

    for path in PLAIN_VALUE_MVP_SURFACES:
        source = read(path)
        assert "frappe.format(" not in source, path
        assert "formatPlainValue" in source or path == BUSINESS_HUB, path
