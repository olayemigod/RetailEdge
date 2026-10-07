from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SHELL_CONTEXT = APP_ROOT / "public" / "js" / "retailedge_shell_context.js"
HOOKS = APP_ROOT / "hooks.py"
NAVIGATION_CONSOLIDATION = APP_ROOT / "navigation_consolidation.py"


def test_retailedge_registers_permission_aware_shared_shell_adapter():
    source = SHELL_CONTEXT.read_text(encoding="utf-8")

    for expected in (
        'const SHELL_ADAPTER_NAME = "shell:retailedge"',
        '"retailedge.master_experience.get_retailedge_business_hub_context"',
        "edgeUI.registerAdapter(SHELL_ADAPTER_NAME, adapter, { replace: true })",
        "data.navigation_groups || []",
        "data.access?.can_use_native_desk",
        "data.feature_flags?.native_document_fallback_enabled !== false",
        'title: "ProcessEdge Retail"',
        "tenantName: context.company_label || context.company || \"\"",
        "branchName: context.branch || \"\"",
        "userName: context.user_name || \"\"",
        "menuItems: shellMenuItems(data)",
    ):
        assert expected in source


def test_shared_shell_navigation_matches_business_hub_target_rules():
    source = SHELL_CONTEXT.read_text(encoding="utf-8")

    for expected in (
        'if (item.target_type === "URL")',
        'if (item.target_type === "DocType")',
        'if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`',
        'if (item.target_type === "Page") return `/app/${item.target}`',
        '!["DocType", "Report"].includes(item.target_type)',
        "window.location.assign(`${url.pathname}${url.search}${url.hash}`)",
        "frappe.set_route(...parts)",
    ):
        assert expected in source


def test_shell_adapter_keeps_retailedge_branch_identity_in_sync():
    source = SHELL_CONTEXT.read_text(encoding="utf-8")

    for expected in (
        "window.retailedgeSyncShellIdentity",
        "active_company: context.company || \"\"",
        "active_branch: context.branch || \"\"",
        "branch_options: Array.isArray(context.branch_options) ? context.branch_options : []",
        "can_switch_branch: Boolean(context.can_switch_branch)",
    ):
        assert expected in source


def test_current_navigation_consolidation_remains_final_hook_and_applies_printing_normalization():
    hooks = HOOKS.read_text(encoding="utf-8")
    navigation = NAVIGATION_CONSOLIDATION.read_text(encoding="utf-8")
    target = "retailedge.navigation_consolidation.get_retailedge_business_hub_context"

    assert f'"retailedge.edgesuite_ui.get_retailedge_business_hub_context": "{target}"' in hooks
    assert f'"retailedge.master_experience.get_retailedge_business_hub_context": "{target}"' in hooks
    assert "get_retailedge_business_hub_context as _get_master_business_hub_context" in navigation
    assert "from retailedge.printing_navigation import normalize_printing_navigation" in navigation
    assert "_consolidate_shift_review_navigation(navigation_groups)" in navigation
    assert "return normalize_printing_navigation(context)" in navigation
