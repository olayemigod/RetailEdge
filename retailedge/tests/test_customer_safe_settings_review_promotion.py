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


def test_settings_are_managed_in_horizontal_tab_workspace():
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
    assert "flex-wrap:nowrap" in vue
    assert "overflow-x:auto" in vue
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
    ):
        assert item in review
