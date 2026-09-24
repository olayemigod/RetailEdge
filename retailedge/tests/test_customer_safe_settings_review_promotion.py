from __future__ import annotations

from pathlib import Path

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


ROOT = Path(__file__).resolve().parents[1]


def test_customer_facing_error_helper_never_returns_raw_tracebacks():
    source = (ROOT / "public" / "js" / "retailedge.js").read_text(encoding="utf-8")
    business = (
        ROOT / "public" / "js" / "business_expenses" / "BusinessExpenses.vue"
    ).read_text(encoding="utf-8")

    for contract in (
        "window.retailedge.userErrorMessage",
        "traceback",
        "frappe\\.exceptions",
        "apps\\/frappe\\/",
        "apps\\/retailedge\\/",
    ):
        assert contract in source
    assert "userErrorMessage?.(error, fallback)" in business
    assert "error?.message || error?.exc || error?.exception" not in business


def test_business_expenses_disabled_state_is_normal_ui_not_an_exception():
    backend = (ROOT / "business_expense.py").read_text(encoding="utf-8")
    frontend = (
        ROOT / "public" / "js" / "business_expenses" / "BusinessExpenses.vue"
    ).read_text(encoding="utf-8")

    context_start = backend.index("def get_business_expense_context(")
    context_end = backend.index("\n\n@frappe.whitelist()", context_start)
    context = backend[context_start:context_end]
    assert "_assert_feature_enabled()" not in context
    assert '"can_manage_settings"' in context
    assert '"feature": {' in context
    assert "get_operating_context()" in context

    assert 'v-else-if="!settings.enabled"' in frontend
    assert "Business Expenses are turned off" in frontend
    assert 'frappe.set_route("retail-settings")' in frontend


def test_settings_use_vertical_section_navigation_workspace():
    backend = (
        ROOT / "retailedge" / "page" / "retail_settings" / "retail_settings.py"
    ).read_text(encoding="utf-8")
    page = (
        ROOT / "retailedge" / "page" / "retail_settings" / "retail_settings.js"
    ).read_text(encoding="utf-8")
    vue = (ROOT / "public" / "js" / "retail_settings" / "RetailSettings.vue").read_text(encoding="utf-8")

    for key in (
        '"sales-operations"',
        '"cashier-expenses"',
        '"business-expenses"',
        '"audit-controls"',
        '"banking-reconciliation"',
        '"financial-dashboard"',
        '"platform-integration"',
    ):
        assert key in backend
    for contract in (
        "frappe.has_permission",
        "frappe.get_single(SETTINGS_DOCTYPE)",
        "doc.save()",
        "_set_role_rows",
    ):
        assert contract in backend
    assert "ignore_permissions" not in backend
    assert "frappe.db.set_value" not in backend

    assert "edgeui.bundle.js" in page
    assert "retail_settings.bundle.js" in page
    assert 'class="settings-tabs"' in vue
    assert 'aria-orientation="vertical"' in vue
    assert "grid-template-columns:minmax(220px, 280px) minmax(0, 1fr)" in vue
    assert "position:sticky" in vue
    assert "text-align:left" in vue
    assert "@media (max-width:980px)" in vue
    assert "Save Changes" in vue
    assert "EdgeLinkField" in vue
    assert "RoleList" in vue


def test_sidebar_and_waffle_use_managed_settings_and_review_pages():
    groups = {group["key"]: group for group in NAVIGATION_GROUPS}
    setup = {(item["label"], item["target_type"], item["target"]) for item in groups["setup"]["items"]}
    assert ("Settings", "Page", "retail-settings") in setup
    assert ("Settings", "DocType", "RetailEdge Settings") not in setup

    review = {
        (item["label"], item["target_type"], item["target"])
        for item in groups["review-approvals"]["items"]
    }
    for item in (
        ("Business Control Centre", "Page", "business-control-center"),
        ("Action Centre", "Page", "action-center"),
        ("Supplier Document Review", "Page", "supplier-document-review"),
        ("Bank Match Reviews", "Page", "bank-matching-reconciliation"),
        ("Daily Sales Audit", "Page", "daily-sales-audit"),
        ("Expense Review", "Page", "expense-review"),
        ("Cash Shift Verification", "Page", "cash-shift-verification"),
        ("Banking Readiness", "Page", "banking-readiness"),
        ("POS Closing Variance & Expenses", "Page", "pos-closing-variance"),
        ("Unmatched Bank Transactions", "Page", "unmatched-bank-transactions"),
        ("Unmatched Bank Payments", "Page", "unmatched-bank-payments"),
        ("Reconciliation Handoff", "Page", "reconciliation-handoff"),
        ("Daily Sales Audit Register", "Page", "daily-sales-audit-register"),
    ):
        assert item in review

    legacy_report_targets = {
        "POS Closing Variance vs Expenses",
        "RetailEdge Unmatched Bank Transactions",
        "RetailEdge Unmatched Bank Payment Events",
        "RetailEdge Reconciliation Handoff",
        "RetailEdge Daily Sales Audit Register",
    }
    assert not any(
        item["target_type"] == "Report" and item["target"] in legacy_report_targets
        for item in groups["review-approvals"]["items"]
    )


def test_remaining_review_reports_use_shared_managed_report_workspace():
    backend = (ROOT / "managed_review_reports.py").read_text(encoding="utf-8")
    vue = (
        ROOT / "public" / "js" / "managed_review_reports" / "ManagedReviewReport.vue"
    ).read_text(encoding="utf-8")
    bundle = (ROOT / "public" / "js" / "managed_review_report.bundle.js").read_text(
        encoding="utf-8"
    )

    for surface in (
        "pos-closing-variance",
        "unmatched-bank-transactions",
        "unmatched-bank-payments",
        "reconciliation-handoff",
        "daily-sales-audit-register",
    ):
        assert surface in backend
        page_folder = surface.replace("-", "_")
        page_json = (
            ROOT
            / "retailedge"
            / "page"
            / page_folder
            / f"{page_folder}.json"
        )
        page_js = (
            ROOT
            / "retailedge"
            / "page"
            / page_folder
            / f"{page_folder}.js"
        )
        assert page_json.exists()
        assert page_js.exists()
        assert "managed_review_report.bundle.js" in page_js.read_text(encoding="utf-8")

    for contract in (
        "run_query_report",
        "get_operating_context",
        "get_allowed_operating_branches",
        "MAX_VISIBLE_ROWS",
        "ALLOWED_LINK_DOCTYPES",
        "Unsupported review filter search.",
        'filters["company"] = company',
        'filters["is_group"] = 0',
        "search_review_report_options",
    ):
        assert contract in backend

    for component in (
        "<EdgeAppShell",
        "<EdgeReportShell",
        "<EdgeLinkField",
        "<EdgeDropdown",
        "More filters",
        "userErrorMessage",
    ):
        assert component in vue

    assert "window.mountManagedReviewReport" in bundle


def test_financial_dashboard_settings_are_additive_and_non_authorising():
    backend = (
        ROOT / "retailedge" / "page" / "retail_settings" / "retail_settings.py"
    ).read_text(encoding="utf-8")
    patch = (ROOT / "patches" / "add_financial_dashboard_settings.py").read_text(encoding="utf-8")
    patches = (ROOT / "patches.txt").read_text(encoding="utf-8")

    assert '"key": "financial-dashboard"' in backend
    for fieldname in (
        "financial_dashboard_comparison_mode",
        "financial_dashboard_composition_dimension",
        "financial_dashboard_show_collection",
        "financial_dashboard_show_financial_health",
        "financial_dashboard_show_outstanding",
    ):
        assert fieldname in backend
        assert fieldname in patch
    assert "Previous Period\\nOff" in patch
    assert "Item Group\\nBrand\\nBranch" in patch
    assert "Accounting definitions and permissions remain fixed." in backend
    assert "retailedge.patches.add_financial_dashboard_settings" in patches
    assert "ignore_permissions" not in patch
