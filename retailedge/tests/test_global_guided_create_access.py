from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CONTEXT = APP_ROOT / "edgesuite_ui.py"
PRODUCT_MENU = APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js"
ROUTE_BRIDGE = APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js"
BUSINESS_HUB = APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"


def test_business_hub_context_exposes_only_permitted_quick_actions():
    source = CONTEXT.read_text(encoding="utf-8")
    assert "_get_permitted_quick_actions" in source
    assert '"quick_actions": quick_actions' in source
    assert '_has_permission_cached(doctype, "create"' in source


def test_product_menu_exposes_permission_aware_global_create_action():
    source = PRODUCT_MENU.read_text(encoding="utf-8")
    assert 'const GUIDED_CREATE_ACTION = "guided-create"' in source
    assert "guidedCreateSection(quickActions)" in source
    assert "buildSections(data.navigation_groups, data.quick_actions)" in source
    assert 'label: "+ Create"' in source
    assert 'link_type: "Action"' in source
    assert "requestGuidedCreate()" in source
    assert "__retailedgeOpenGuidedCreate = true" in source


def test_global_create_reuses_canonical_business_hub_guided_host():
    bridge = ROUTE_BRIDGE.read_text(encoding="utf-8")
    hub = BUSINESS_HUB.read_text(encoding="utf-8")
    assert 'const GUIDED_CREATE_EVENT = "retailedge-open-guided-create"' in bridge
    assert "openPendingGuidedCreate" in bridge
    assert "proxy.openCreatePicker()" in bridge
    assert "__retailedgeOpenGuidedCreate = false" in bridge
    for component in (
        "SimpleSalesInvoiceDialog",
        "SimplePaymentDialog",
        "SimpleCashDepositDialog",
        "SimpleCashTransferDialog",
        "SimplePurchaseInvoiceDialog",
        "SimpleCashierExpenseDialog",
        "SimpleStockTransferDialog",
        "SimpleStockAdjustmentDialog",
    ):
        assert component in hub
