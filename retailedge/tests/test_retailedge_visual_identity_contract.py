from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "hooks.py"
IDENTITY_CSS = ROOT / "public" / "css" / "retailedge_product_identity.css"
NAV_COMPAT_CSS = ROOT / "public" / "css" / "retailedge_navigation_shell_compat.css"
PRODUCT_MARK = ROOT / "public" / "images" / "processedge_retail" / "processedge-retail-mark.svg"
APP_ICON = ROOT / "public" / "images" / "processedge_retail" / "pedge-retail-app-icon-dark.png"
DESKTOP_IDENTITY = ROOT / "desktop_identity.py"
SHELL_CONTEXT = ROOT / "public" / "js" / "retailedge_shell_context.js"
COMPANY_PROFILE = ROOT / "company_profile.py"
WORKSPACE = ROOT / "retailedge" / "workspace" / "retailedge" / "retailedge.json"
PROFESSIONAL_SELLING = ROOT / "public" / "js" / "professional_selling" / "ProfessionalSelling.vue"
DOCUMENT_OUTPUT = ROOT / "public" / "js" / "document_output_sharing" / "DocumentOutputSharing.vue"

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
    nav_compat = hooks.index("/assets/retailedge/css/retailedge_navigation_shell_compat.css")

    assert cards < workspace < guided < identity < nav_compat


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


def test_retailedge_navigation_compat_matches_vetedge_theme_owned_menu_contract():
    source = NAV_COMPAT_CSS.read_text(encoding="utf-8")

    for contract in (
        ".edge-app-shell.edge-nav-shell-v2",
        "background: var(--edge-color-surface);",
        "color: var(--edge-color-ink-950);",
        ".edge-sidebar__section.is-expanded .edge-sidebar__section-toggle",
        ".edge-sidebar__section:has(.edge-sidebar-item.active) .edge-sidebar__section-toggle",
        "background: transparent;",
        "color: var(--edge-color-brand-600);",
        "background: color-mix(in srgb, var(--edge-color-brand-50) 78%, var(--edge-color-surface));",
        'data-edge-appearance="dark"',
        "background: color-mix(in srgb, var(--edge-color-brand-700) 22%, var(--edge-color-surface));",
        "outline: 3px solid color-mix(in srgb, var(--edge-color-brand-500) 25%, transparent);",
    ):
        assert contract in source

    for forbidden in (
        "#0b1f33",
        "#f7fbfc",
        "#dce6ec",
        "rgba(255, 255, 255",
        "--retailedge-sidebar-active",
    ):
        assert forbidden not in source



def test_business_hub_declares_product_identity_through_shared_edgesuite_shell():
    source = BUSINESS_HUB.read_text(encoding="utf-8")

    assert '<EdgeAppShell' in source
    assert 'product="retailedge"' in source
    assert 'title="ProcessEdge Retail"' in source
    assert 'subtitle="Structured for Scale."' in source
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


def test_approved_processedge_retail_brand_assets_and_visible_identity_are_wired():
    hooks = HOOKS.read_text(encoding="utf-8")
    profile = COMPANY_PROFILE.read_text(encoding="utf-8")
    shell = SHELL_CONTEXT.read_text(encoding="utf-8")
    workspace = WORKSPACE.read_text(encoding="utf-8")
    mark = PRODUCT_MARK.read_text(encoding="utf-8")

    assert PRODUCT_MARK.exists()
    assert APP_ICON.exists()
    assert 'app_title = "PEdge Retail"' in hooks
    assert '"title": "PEdge Retail"' in hooks
    assert "pedge-retail-app-icon-dark.png" in hooks
    assert '"route": "/desk/retailedge-business-hub"' in hooks
    assert "retailedge.desktop_identity.sync_retailedge_desktop_identity" in hooks
    assert '"product_code": "retailedge"' in profile
    assert '"product_name": "ProcessEdge Retail"' in profile
    assert '"product_subtitle": "Structured for Scale."' in profile
    assert "processedge-retail-mark.svg" in profile
    assert 'title.textContent = "ProcessEdge Retail"' in shell
    assert '"name": "RetailEdge"' in workspace
    assert '"module": "RetailEdge"' in workspace
    assert '"label": "ProcessEdge Retail"' in workspace
    assert '"title": "ProcessEdge Retail"' in workspace
    assert "Shelf R mark" in mark


def test_desktop_launcher_repairs_existing_frappe_desktop_state_without_renaming_workspace():
    source = DESKTOP_IDENTITY.read_text(encoding="utf-8")

    for contract in (
        'DESKTOP_LABEL = "PEdge Retail"',
        'DESKTOP_ROUTE = "/desk/retailedge-business-hub"',
        'pedge-retail-app-icon-dark.png',
        '"Desktop Icon"',
        '"Workspace Sidebar"',
        'WORKSPACE_NAME = "RetailEdge"',
        'frappe.cache.delete_key("desktop_icons")',
        'frappe.cache.delete_key("bootinfo")',
    ):
        assert contract in source

    assert 'frappe.delete_doc("Workspace"' not in source
    assert 'frappe.rename_doc("Workspace"' not in source


def test_desktop_launcher_opens_business_hub_in_same_tab():
    source = (ROOT / "public" / "js" / "retailedge.js").read_text(encoding="utf-8")

    for contract in (
        'const RETAILEDGE_DESKTOP_LABEL = "PEdge Retail"',
        'const RETAILEDGE_DESKTOP_PATH = "/desk/retailedge-business-hub"',
        "keepRetailDesktopLauncherInSameTab",
        'link.removeAttribute("target")',
        'link.setAttribute("href", RETAILEDGE_DESKTOP_PATH)',
        "MutationObserver",
    ):
        assert contract in source


def test_processedge_retail_palette_uses_approved_master_brand_colours():
    source = IDENTITY_CSS.read_text(encoding="utf-8")
    assert "--retailedge-brand: #0056A6;" in source
    assert "--retailedge-brand-strong: #003E73;" in source
    assert "--retailedge-money: #1C9C5D;" in source


def test_file_uploader_dark_mode_uses_retail_surface_and_text_tokens():
    source = IDENTITY_CSS.read_text(encoding="utf-8")

    for contract in (
        ".modal-content:has(.file-uploader)",
        ".file-uploader .file-upload-area",
        "--bg-color: var(--retailedge-surface-muted);",
        "--text-color: var(--retailedge-ink);",
        "--subtle-fg:",
        "background: var(--retailedge-surface-muted) !important;",
        ".file-uploader .btn-file-upload",
        ".file-uploader .form-control",
        ".modal-footer .btn-default",
    ):
        assert contract in source


def test_invoice_edit_and_print_surfaces_are_stacked_on_production_identity():
    selling = PROFESSIONAL_SELLING.read_text(encoding="utf-8")
    output = DOCUMENT_OUTPUT.read_text(encoding="utf-8")

    assert 'product="retailedge"' in selling
    assert 'product="retailedge"' in output
    assert 'product="RetailEdge"' not in selling
    assert 'product="Retail"' not in output
