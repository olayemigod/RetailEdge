from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "retailedge" / "page" / "banking_readiness" / "banking_readiness.js"
MATCHING = ROOT / "public" / "js" / "bank_matching_edgesuite_workspace.js"
ACTION_CENTER = ROOT / "action_center.py"


def test_banking_readiness_uses_shared_retailedge_shell():
	source = READINESS.read_text(encoding="utf-8")
	for contract in (
		'getComponent("EdgeAppShell")',
		'activeRoute: "/app/banking-readiness"',
		"hideNativeSidebar: true",
		"menuItems: state.menuItems",
		"onNavigate: handleNavigation",
		'method: "retailedge.edgesuite_ui.get_retailedge_business_hub_context"',
	):
		assert contract in source


def test_bank_matching_uses_shared_retailedge_shell_and_valid_context_endpoint():
	source = MATCHING.read_text(encoding="utf-8")
	for contract in (
		'getComponent("EdgeAppShell")',
		'activeRoute: "/app/bank-matching-reconciliation"',
		"hideNativeSidebar: true",
		"menuItems: state.menuItems",
		"onNavigate: handleNavigation",
		'method: "retailedge.edgesuite_ui.get_retailedge_business_hub_context"',
	):
		assert contract in source
	assert "get_master_retailedge_business_hub_context" not in source


def test_banking_shell_navigation_fails_closed_for_edgesuite_only_users():
	for path in (READINESS, MATCHING):
		source = path.read_text(encoding="utf-8")
		assert '["DocType", "Report"].includes(item.target_type)' in source
		assert "!state.canUseNativeDesk" in source


def test_banking_pages_apply_shell_scope_before_first_data_refresh():
	for path in (READINESS, MATCHING):
		source = path.read_text(encoding="utf-8")
		mount = source.index("onMounted(async () =>")
		load = source.index("await loadShellContext();", mount)
		refresh = source.index("await refresh();", load)
		assert mount < load < refresh
		assert "Promise.all([loadShellContext(), refresh()])" not in source


def test_banking_readiness_native_drill_through_requires_native_desk_capability():
	source = READINESS.read_text(encoding="utf-8")
	assert 'state.canUseNativeDesk && row.resolved_gl_account ? actionButton(t("Open GL Account")' in source
	assert 'state.canUseNativeDesk ? actionButton(t("Open ERPNext Bank Account")' in source


def test_action_center_bank_exceptions_use_canonical_edgesuite_page():
	source = ACTION_CENTER.read_text(encoding="utf-8")
	start = source.index("def _append_bank_exceptions(")
	end = source.index("\ndef _action_from_financial_exposure(", start)
	block = source[start:end]
	assert block.count('"/app/bank-matching-reconciliation"') == 3
	assert block.count('"bank-matching-reconciliation"') >= 3
	assert block.count('"Page"') >= 3
	for stale in (
		"/app/query-report/RetailEdge Reconciliation Handoff",
		"/app/retail-edge-bank-transaction-match",
		"/app/query-report/RetailEdge Bank Match Reconciliation Readiness",
	):
		assert stale not in block
