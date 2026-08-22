from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_MENU = APP_ROOT / "public" / "js" / "retailedge_product_menu.bundle.js"
BUSINESS_HUB_PAGE = APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js"
R7_DOC = APP_ROOT.parent / "docs" / "r7_route_consolidation.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_inherited_native_destinations_open_in_new_tab():
    source = _source(PRODUCT_MENU)

    assert 'item.link_type === "Report" || item.link_type === "DocType"' in source
    assert 'window.open(url, "_blank", "noopener,noreferrer")' in source
    assert 'frappe.set_route("List", item.link_to)' not in source
    assert 'frappe.set_route("query-report", item.link_to)' not in source


def test_inherited_guided_create_is_global_and_permission_aware():
    source = _source(PRODUCT_MENU)

    assert "guidedCreateSection(quickActions)" in source
    assert 'label: "+ Create"' in source
    assert 'link_type: "Action"' in source
    assert 'GUIDED_CREATE_ACTION = "guided-create"' in source
    assert "buildSections(data.navigation_groups, data.quick_actions)" in source


def test_exact_operational_replacements_are_promoted_to_retailedge_pages():
    source = _source(PRODUCT_MENU)

    expected = {
        '"Report:RetailEdge Cashier Expense Review"': 'target: "expense-review"',
        '"Report:RetailEdge Cash Shift Verification"': 'target: "cash-shift-verification"',
        '"DocType:RetailEdge Daily Sales Audit"': 'target: "daily-sales-audit"',
    }
    for legacy_target, page_target in expected.items():
        assert legacy_target in source
        assert page_target in source

    assert '"Report:RetailEdge Daily Sales Audit Register": null' in source
    assert "consolidateNavigationGroups(normalized.navigation_groups)" in source


def test_stock_movement_and_r6_banking_routes_are_not_prematurely_promoted():
    source = _source(PRODUCT_MENU)

    assert "RetailEdge Stock Movement History" not in source
    assert "RetailEdge Bank Transaction Matching" not in source
    assert "RetailEdge Bank Match Reconciliation Readiness" not in source
    assert "RetailEdge Reconciliation Handoff" not in source


def test_setup_masters_promote_to_managed_retailedge_setup_with_native_fallbacks():
    documentation = _source(R7_DOC)

    for doctype in (
        "RetailEdge Settings",
        "RetailEdge Branch Profile",
        "RetailEdge Expense Category",
        "RetailEdge Statement Mapping Template",
    ):
        assert f"**{doctype}**" in documentation

    assert "dedicated **RetailEdge Setup** page" in documentation
    assert "existing DocTypes and their controllers remain the source of truth" in documentation
    assert "Open Full Form" in documentation
    assert "No dedicated RetailEdge setup page currently exists" not in documentation
    assert "must not invent that surface" not in documentation


def test_legacy_frappe_workspace_is_not_extended_as_primary_navigation():
    documentation = _source(R7_DOC)

    assert "old Frappe RetailEdge Workspace is treated as a legacy launcher" in documentation
    assert "legacy workspace should not receive new operational shortcuts" in documentation
    assert "Do not add global Desk route monkey-patches" in documentation


def test_user_facing_r7_copy_uses_retailedge_business_naming():
    product_menu = _source(PRODUCT_MENU)
    business_hub = _source(BUSINESS_HUB_PAGE)
    documentation = _source(R7_DOC)

    assert "Standalone EdgeSuite UI product-menu runtime is unavailable." not in product_menu
    assert "Standalone EdgeSuite UI runtime is unavailable or incompatible." not in business_hub
    assert "EdgeSuite UI is missing required components" not in business_hub
    assert '"RetailEdge interface runtime is unavailable or incompatible."' in business_hub
    assert '"RetailEdge interface is missing required components: {0}"' in business_hub
    assert "EdgeSuite Pages" not in documentation
    assert "EdgeSuite workspace" not in documentation
    assert "tested EdgeSuite replacement" not in documentation


def test_route_consolidation_does_not_add_business_document_writes():
    source = _source(PRODUCT_MENU)

    forbidden = (
        "ignore_permissions",
        "frappe.db.set_value",
        "frappe.client.insert",
        "frappe.client.save",
        ".submit()",
        ".cancel()",
    )
    for token in forbidden:
        assert token not in source
