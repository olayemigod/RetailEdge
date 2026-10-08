from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENHANCEMENTS = ROOT / "public/js/bank_matching_page_enhancements.js"
LEGACY_RECONCILIATION = ROOT / "public/js/bank_matching_reconciliation.js"
WORKSPACE = ROOT / "public/js/bank_matching_edgesuite_workspace.js"
LOADER = ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"


def test_bank_matching_uses_business_copy_and_preserves_banking_workflows():
	enhancements = ENHANCEMENTS.read_text(encoding="utf-8")
	legacy = LEGACY_RECONCILIATION.read_text(encoding="utf-8")
	workspace = WORKSPACE.read_text(encoding="utf-8")
	loader = LOADER.read_text(encoding="utf-8")

	assert "bank_matching_edgesuite_workspace.js" in loader

	for marker in (
		"Smart Date is unavailable. Refresh the page or contact your administrator.",
		"The bank statement template download service is unavailable.",
		"The Bank Statement Import draft could not be created.",
		"The statement preview was validated. Review it before starting import.",
		"The statement import is being processed.",
		"Import started. Use Check Status to refresh the import result.",
		"Bank Transactions are being imported. Matching and reconciliation remain separate actions.",
		"Unable to start the bank statement import.",
		"The file was validated. No preview rows were returned for display.",
		"Preview and import Bank Transactions without leaving Bank Matching.",
		"Bank statement import controls are unavailable.",
		"Upload, preview, and import a statement without leaving Bank Matching.",
	):
		assert marker in enhancements

	for forbidden in (
		"Smart date requires the EdgeSuite Reporting Standard component.",
		"The ERPNext template download service is unavailable.",
		"ERPNext did not create a Bank Statement Import draft.",
		"ERPNext validated the statement preview.",
		"ERPNext is processing the statement import.",
		"refresh the ERPNext import result",
		"ERPNext is importing Bank Transactions",
		"Unable to start the ERPNext bank statement import.",
		"ERPNext validated the file.",
		"through ERPNext Banking",
		"current ERPNext mapping",
		"EdgeSuite modal components are unavailable",
		"in an EdgeSuite modal",
	):
		assert forbidden not in enhancements

	for marker in (
		"Reconciliation could not be completed.",
		"Confirmed match — reconciliation remains governed by approval and fresh accounting safety checks.",
		"Reconciliation uses the current accounting records.",
		"RetailEdge will run a fresh safety check against current accounting data before reconciliation. Submitted accounting documents will not be mutated.",
		"Reconcile Match",
		"Match bank inflows and outflows to valid accounting events, then complete reconciliation.",
		"The Bank Matching & Reconciliation interface is unavailable. Refresh the page or contact your administrator.",
		"Bank Matching & Reconciliation cannot start because required interface components are unavailable. Refresh the page or contact your administrator.",
	):
		assert marker in workspace

	for forbidden in (
		"ERPNext reconciliation could not be completed.",
		"fresh ERPNext safety checks",
		"ERPNext remains the reconciliation authority.",
		"before ERPNext Banking reconciliation",
		"Reconcile Through ERPNext",
		"valid ERPNext accounting events",
		"reconcile through ERPNext Banking",
		"EdgeSuite UI runtime is required for Bank Matching & Reconciliation.",
		"EdgeSuite UI is missing required banking components",
	):
		assert forbidden not in workspace

	for marker in (
		"This match is confirmed and approved. Reconcile it after a fresh safety check?",
		"Reconciling...",
		"Match bank inflows and outflows to valid accounting events, then complete reconciliation.",
		"The Bank Matching & Reconciliation interface is unavailable.",
	):
		assert marker in legacy

	for forbidden in (
		"Reconcile it through ERPNext",
		"Reconciling through ERPNext",
		"valid ERPNext accounting events",
		"reconcile through ERPNext Banking",
		"EdgeSuite UI runtime is required for Bank Matching & Reconciliation",
	):
		assert forbidden not in legacy

	for marker in (
		"erpnext.accounts.doctype.bank_statement_import.bank_statement_import.get_preview_from_template",
		"erpnext.accounts.doctype.bank_statement_import.bank_statement_import.form_start_import",
		"X-Frappe-CSRF-Token",
		"global.EdgeSuiteUI || global.EdgeUI || null",
	):
		assert marker in enhancements

	for marker in (
		"retailedge.bank_candidate_engine.get_direction_aware_bank_candidates",
		"retailedge.bank_candidate_engine.prepare_direction_aware_bank_candidate",
		"retailedge.reconciliation_approval.approve_reconciliation_for_match",
		"retailedge.banking_operations.match_and_reconcile",
		"confirm_match: 0",
		"confirm_reconciliation: 1",
		"global.EdgeSuiteUI || global.EdgeUI || null",
		"canUseNativeDesk",
		"routeToNativeDocument",
	):
		assert marker in workspace
