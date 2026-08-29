from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CONTEXT = APP_ROOT / "edgesuite_ui.py"
HOOKS = APP_ROOT / "hooks.py"
BOOTSTRAP = APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js"
PRODUCT_MENU = APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js"
ROUTE_BRIDGE = APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js"
BUSINESS_HUB = APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
GUIDED_CREATE_CSS = APP_ROOT / "public" / "css" / "retailedge_guided_create_menu.css"


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


def test_guided_create_picker_is_fuzzy_searchable_from_both_entry_points():
    source = ROUTE_BRIDGE.read_text(encoding="utf-8")
    assert "function fuzzyActionScore(query, action)" in source
    assert "function editDistance(left, right)" in source
    assert "function isSubsequence(needle, haystack)" in source
    assert "function installGuidedCreateSearch(wrapper)" in source
    assert 'class="edge-input guided-create-search-input"' in source
    assert 'placeholder="Search sales, payment, stock, customer…"' in source
    assert "applyGuidedCreateSearch(list, proxy, input.value)" in source
    assert "visible.length === 1" in source
    assert "visible[0].click()" in source
    assert "installGuidedCreateSearch(wrapper);" in source
    assert "proxy.openCreatePicker();" in source


def test_guided_create_picker_matches_waffle_theme_and_is_responsive():
    hooks = HOOKS.read_text(encoding="utf-8")
    css = GUIDED_CREATE_CSS.read_text(encoding="utf-8")
    assert '"/assets/retailedge/css/retailedge_guided_create_menu.css"' in hooks
    assert ".edge-modal:has(.create-picker-list)" in css
    assert "--edge-color-surface" in css
    assert "--edge-color-surface-muted" in css
    assert "--edge-color-border" in css
    assert "--edge-color-ink-950" in css
    assert "--edge-color-ink-500" in css
    assert "--edge-color-brand-500" in css
    assert "--edge-color-brand-600" in css
    assert ".guided-create-search" in css
    assert ".create-picker-item:hover" in css
    assert "@media (max-width: 36rem)" in css
    assert "100dvh" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_product_menu_opens_native_desk_targets_in_new_tabs():
    source = PRODUCT_MENU.read_text(encoding="utf-8")
    assert "function openNativeDeskTarget(linkType, linkTo)" in source
    assert 'if (linkType === "Report")' in source
    assert 'else if (linkType === "DocType")' in source
    assert 'window.open(url, "_blank", "noopener,noreferrer")' in source
    assert "window.retailedgeOpenNativeTarget = openNativeDeskTarget" in source
    assert 'if (item.link_type === "Report" || item.link_type === "DocType")' in source


def test_edgesuite_sidebar_native_links_use_same_new_tab_policy():
    source = PRODUCT_MENU.read_text(encoding="utf-8")
    assert "function nativeSidebarTarget(label)" in source
    assert "if (matches.length !== 1) return null" in source
    assert "function handleNativeSidebarClick(event)" in source
    assert 'event.target?.closest?.(".edge-app-shell .edge-sidebar-item")' in source
    assert "event.stopImmediatePropagation()" in source
    assert "openNativeDeskTarget(item.link_type, item.link_to)" in source
    assert 'document.addEventListener("click", handleNativeSidebarClick, true)' in source


def test_product_menu_and_guided_route_bridge_boot_globally_on_retailedge_desk():
    hooks = HOOKS.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert '"/assets/retailedge/js/retailedge_business_hub_page.js"' in hooks
    assert 'const PRODUCT_MENU_ASSET = "retailedge_product_menu.bundle.js"' in bootstrap
    assert "bootProductMenu();" in bootstrap
    assert "bootRouteBridge();" in bootstrap
    assert "initialiseDeskFeatures()" in bootstrap
