from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks.py"
IDENTITY_CSS = ROOT / "public" / "css" / "retailedge_product_identity.css"
BUSINESS_HUB = (
    ROOT
    / "public"
    / "js"
    / "retailedge_business_hub"
    / "RetailEdgeBusinessHub.vue"
)


def test_retailedge_identity_layer_is_loaded_after_existing_product_styles():
    hooks = HOOKS.read_text(encoding="utf-8")

    cards = hooks.index("/assets/retailedge/css/retailedge_cards.css")
    workspace = hooks.index("/assets/retailedge/css/retailedge_workspace_home.css")
    guided = hooks.index("/assets/retailedge/css/retailedge_guided_create_menu.css")
    identity = hooks.index("/assets/retailedge/css/retailedge_product_identity.css")

    assert cards < workspace < guided < identity


def test_identity_layer_is_scoped_to_retailedge_and_does_not_clone_shared_shell():
    source = IDENTITY_CSS.read_text(encoding="utf-8")

    for contract in (
        "body.edge-suite-product-retailedge",
        '[data-edge-product="retailedge"]',
        "--retailedge-brand",
        "--retailedge-sidebar",
        "--retailedge-brand: var(--edge-color-brand-600",
        ".edge-app-shell__sidebar",
        ".edge-page-header",
        ".edge-stat-card",
        ".edge-filter-bar",
        ".edge-data-table",
        ".retailedge-business-hub .hub-banner",
        ".home-kpi-card",
        ".home-attention-card",
        'data-edge-appearance="dark"',
    ):
        assert contract in source

    assert "vetedge" not in source.lower()
    assert "eduedge" not in source.lower()


def test_business_hub_declares_product_identity_through_shared_edgesuite_shell():
    source = BUSINESS_HUB.read_text(encoding="utf-8")

    assert '<EdgeAppShell' in source
    assert 'product="retailedge"' in source
    assert 'title="RetailEdge"' in source
    assert 'subtitle="Retail operations & control"' in source
    assert ':hideNativeSidebar="true"' in source


def test_visual_identity_does_not_replace_business_or_accounting_authorities():
    source = IDENTITY_CSS.read_text(encoding="utf-8").lower()

    for forbidden in (
        "sales invoice",
        "purchase invoice",
        "payment entry",
        "stock entry",
        "frappe.call",
        "ignore_permissions",
        "frappe.db",
    ):
        assert forbidden not in source


def test_light_appearance_does_not_force_dark_sidebar_and_title_remains_readable():
    source = IDENTITY_CSS.read_text(encoding="utf-8")
    assert "--retailedge-sidebar: color-mix" in source
    assert ".edge-topbar__title-copy strong" in source
    assert "var(--edge-color-surface" in source
    assert "var(--edge-color-ink-950" in source


def test_business_hub_large_money_cards_are_non_wrapping_and_roomy():
    source = IDENTITY_CSS.read_text(encoding="utf-8")
    component = BUSINESS_HUB.read_text(encoding="utf-8")
    assert "repeat(auto-fit, minmax(13.5rem, 1fr))" in source
    assert "white-space: nowrap;" in source
    assert "repeat(auto-fit, minmax(13.5rem, 1fr))" in component
