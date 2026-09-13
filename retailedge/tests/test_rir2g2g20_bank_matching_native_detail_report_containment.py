from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "public/js/bank_matching_edgesuite_workspace.js"
PAGE_LOADER = ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"


def _workspace() -> str:
	return WORKSPACE.read_text(encoding="utf-8")


def test_active_page_uses_edgesuite_workspace_not_legacy_banking_scripts():
	source = PAGE_LOADER.read_text(encoding="utf-8")
	assert 'const WORKSPACE_ASSET = "/assets/retailedge/js/bank_matching_edgesuite_workspace.js";' in source
	assert "bank_matching_reconciliation.js" not in source
	assert "bank_match_review_ui.js" not in source


def test_native_desk_access_resolution_is_shared_and_fail_closed():
	source = _workspace()
	assert "let nativeDeskAccessPromise = null;" in source
	assert "async function resolveNativeDeskAccess()" in source
	assert 'typeof global.retailedgeGetBusinessHubContext === "function"' in source
	assert 'method: "retailedge.master_experience.get_master_retailedge_business_hub_context"' in source
	assert "return Boolean(context?.access?.can_use_native_desk);" in source
	assert "return false;" in source
	assert "state.canUseNativeDesk = await resolveNativeDeskAccess();" in source


def test_native_document_actions_fail_closed_and_audit_record_is_gated():
	source = _workspace()
	start = source.index("function routeToNativeDocument")
	block = source[start : start + 320]
	assert "if (!state.canUseNativeDesk) return;" in block
	assert 'global.frappe.set_route("Form", doctype, name)' in block
	assert "routeToDocument(" not in source
	assert "if (state.canUseNativeDesk && state.review.matchName)" in source
	assert 'routeToNativeDocument("RetailEdge Bank Transaction Match", state.review.matchName)' in source


def test_native_report_menu_is_added_only_after_capability_check():
	source = _workspace()
	start = source.index("async function configureNativeReportMenu")
	block = source[start : start + 800]
	assert "if (!(await resolveNativeDeskAccess())) return;" in block
	assert 'page.add_menu_item(t("Open Matching Report")' in block
	assert 'page.add_menu_item(t("Open Reconciliation Readiness Report")' in block
	assert "void configureNativeReportMenu(page);" in source


def test_edgesuite_banking_action_remains_available():
	source = _workspace()
	assert 'actionButton(t("Banking Setup & Readiness"), "secondary", () => global.frappe.set_route("banking-readiness"))' in source
