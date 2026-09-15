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
        "--edge-color-brand-600",
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


def test_retailedge_sidebar_and_product_name_follow_edgesuite_appearance():
    source = IDENTITY_CSS.read_text(encoding="utf-8")

    for contract in (
        "--retailedge-sidebar: var(--edge-color-surface);",
        "--retailedge-sidebar-muted: var(--edge-color-ink-500);",
        "background: var(--edge-color-surface);",
        "border-right: 1px solid var(--edge-color-border);",
        "color: var(--edge-color-ink-950);",
        ".edge-sidebar__brand-copy strong",
        ".edge-topbar__title-copy strong",
        "background: var(--edge-color-surface-muted);",
        "color: var(--edge-color-brand-700);",
        'edge-sidebar-item[aria-current="page"]',
    ):
        assert contract in source

    for legacy_dark_sidebar_contract in (
        "color: #f7fbfc;",
        "color: #dce6ec;",
        "background: rgba(255, 255, 255, 0.07);",
        "border-right: 0;",
    ):
        assert legacy_dark_sidebar_contract not in source


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
