from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
PAGE_CSS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.css"
DENSE_CSS = APP_ROOT / "public/css/bank_matching_dense_workspace.css"
ENHANCEMENTS_CSS = APP_ROOT / "public/css/bank_matching_page_enhancements.css"
WORKSPACE_JS = APP_ROOT / "public/js/bank_matching_edgesuite_workspace.js"
OUTCOME_JS = APP_ROOT / "public/js/bank_candidate_outcome_notifications.js"
CATEGORY_JS = APP_ROOT / "public/js/bank_review_category_adapter.js"
FUZZY_JS = APP_ROOT / "public/js/bank_matching_fuzzy_discovery_adapter.js"
BRANCH_SEARCH_JS = APP_ROOT / "public/js/bank_matching_branch_search_adapter.js"
COMPLETION_JS = APP_ROOT / "public/js/bank_matching_edgesuite_completion_adapter.js"
ENHANCEMENTS_JS = APP_ROOT / "public/js/bank_matching_page_enhancements.js"


class BankingPageContractTests(unittest.TestCase):
	def test_page_controller_is_thin_edgesuite_loader(self):
		page_js = PAGE_JS.read_text()
		for asset in (
			"/assets/retailedge/js/bank_candidate_outcome_notifications.js",
			"/assets/retailedge/js/bank_review_category_adapter.js",
			"/assets/retailedge/js/bank_matching_fuzzy_discovery_adapter.js",
			"/assets/retailedge/js/bank_matching_branch_search_adapter.js",
			"/assets/retailedge/css/bank_matching_dense_workspace.css",
			"/assets/retailedge/css/bank_matching_edgesuite_completion.css",
			"/assets/retailedge/css/bank_matching_page_enhancements.css",
			"/assets/retailedge/js/bank_matching_edgesuite_workspace.js",
			"/assets/retailedge/js/bank_matching_edgesuite_completion_adapter.js",
			"/assets/retailedge/js/bank_matching_page_enhancements.js",
		):
			self.assertIn(asset, page_js)
		self.assertIn("retailedgeBootBankingWorkspace", page_js)
		self.assertNotIn("/assets/retailedge/js/bank_match_review_ui.js", page_js)
		self.assertNotIn("/assets/retailedge/js/bank_reconciliation_confirmation.js", page_js)
		for raw_tag in ("<table", "<tr", "<td", "<div", "<button", "<a "):
			self.assertNotIn(raw_tag, page_js)

	def test_page_controller_load_order_preserves_adapters_before_workspace(self):
		page_js = PAGE_JS.read_text()
		markers = (
			"Promise.resolve(frappe.require(OUTCOME_ASSET))",
			".then(() => Promise.resolve(frappe.require(REVIEW_CATEGORY_ASSET)))",
			".then(() => Promise.resolve(frappe.require(FUZZY_DISCOVERY_ASSET)))",
			".then(() => Promise.resolve(frappe.require(BRANCH_SEARCH_ASSET)))",
			".then(() => loadBankingStyles())",
			".then(() => Promise.resolve(frappe.require(WORKSPACE_ASSET)))",
			".then(() => Promise.resolve(frappe.require(COMPLETION_ASSET)))",
			".then(() => Promise.resolve(frappe.require(PAGE_ENHANCEMENTS_ASSET)))",
			".then(() => startWorkspace(wrapper))",
		)
		positions = [page_js.index(marker) for marker in markers]
		self.assertEqual(positions, sorted(positions))
		self.assertIn("STYLE_VERSION", page_js)
		self.assertIn("loadVersionedStylesheet", page_js)
		self.assertIn(".catch((error) =>", page_js)

	def test_live_banking_assets_are_valid_javascript(self):
		for asset in (
			PAGE_JS,
			WORKSPACE_JS,
			OUTCOME_JS,
			CATEGORY_JS,
			FUZZY_JS,
			BRANCH_SEARCH_JS,
			COMPLETION_JS,
			ENHANCEMENTS_JS,
		):
			completed = subprocess.run(
				["node", "--check", str(asset)],
				capture_output=True,
				text=True,
				check=False,
			)
			self.assertEqual(completed.returncode, 0, completed.stderr)

	def test_workspace_requires_edgesuite_components_and_no_frappe_dialogs(self):
		asset = WORKSPACE_JS.read_text()
		self.assertIn("EdgeSuiteUI", asset)
		for component in (
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeFilterBar",
			"EdgeLinkField",
			"EdgeInput",
			"EdgeDropdown",
			"EdgeStatCard",
			"EdgeStatusBadge",
			"EdgeModal",
			"EdgeTextarea",
		):
			self.assertIn(f'getComponent("{component}")', asset)
		self.assertNotIn("new frappe.ui.Dialog", asset)
		self.assertNotIn("frappe.confirm(", asset)

	def test_workspace_uses_permission_aware_context_filters(self):
		asset = WORKSPACE_JS.read_text()
		self.assertIn("frappe.desk.search.search_link", asset)
		for fieldname in ("company", "branch", "bank_account", "from_date", "to_date", "search"):
			self.assertIn(fieldname, asset)
		self.assertIn('if (field === "company")', asset)
		self.assertIn('state.filters.branch = ""', asset)
		self.assertIn('state.filters.bank_account = ""', asset)
		self.assertIn("retailedge.banking_workspace.get_banking_workspace_rows", asset)

	def test_banking_table_is_sortable_compact_and_responsive(self):
		asset = WORKSPACE_JS.read_text()
		page_css = PAGE_CSS.read_text()
		dense_css = DENSE_CSS.read_text()
		for class_name in (
			"retailedge-col-transaction",
			"retailedge-col-candidate",
			"retailedge-bank-narration",
			"retailedge-bank-meta",
			"retailedge-bank-sort",
		):
			self.assertIn(class_name, asset)
			self.assertTrue(class_name in page_css or class_name in dense_css)
		self.assertIn("toggleSort", asset)
		self.assertIn("sortedRows", asset)
		self.assertIn("table-layout: fixed", dense_css)
		self.assertIn("-webkit-line-clamp: 2", dense_css)
		self.assertIn("@media (max-width: 900px)", dense_css)

	def test_candidate_selection_is_edgesuite_and_keeps_fuzzy_supplemental(self):
		asset = WORKSPACE_JS.read_text()
		self.assertIn("get_direction_aware_bank_candidates", asset)
		self.assertIn("prepare_direction_aware_bank_candidate", asset)
		self.assertIn('h(EdgeDropdown, {', asset)
		self.assertIn("Accounting / Hard Score", asset)
		self.assertIn("Supplemental Fuzzy Score", asset)
		self.assertIn("Fuzzy evidence is supplemental only", asset)

	def test_fuzzy_date_tolerance_is_visible_and_configurable_without_changing_hard_eligibility(self):
		fuzzy = FUZZY_JS.read_text()
		enhancements = ENHANCEMENTS_JS.read_text()
		for marker in (
			"retailedgeBankingFuzzyDateToleranceDays",
			"configuredTolerance",
			"MAX_DATE_TOLERANCE_DAYS = 7",
			"Supplemental evidence only; accounting eligibility is unchanged.",
		):
			self.assertIn(marker, fuzzy)
		for marker in (
			"Smart Match",
			"Same day",
			"±1 day",
			"±3 days",
			"±7 days",
			"Date proximity is supplemental only; bank/accounting eligibility still controls.",
		):
			self.assertIn(marker, enhancements)

	def test_page_enhancements_compact_filters_and_use_native_statement_import(self):
		enhancements = ENHANCEMENTS_JS.read_text()
		css = ENHANCEMENTS_CSS.read_text()
		self.assertIn("removeFilterHeading", enhancements)
		self.assertIn("Reset filters", enhancements)
		self.assertIn("Upload Statement", enhancements)
		self.assertIn('IMPORT_DOCTYPE = "Bank Statement Import"', enhancements)
		self.assertIn("frappe.new_doc", enhancements)
		self.assertIn('reference_doctype: "Bank Transaction"', enhancements)
		self.assertIn('import_type: "Insert New Records"', enhancements)
		self.assertNotIn("frappe.ui.Dialog", enhancements)
		self.assertIn("retailedge-bank-reset-link", css)
		self.assertIn("retailedge-bank-smart-match", css)
		self.assertIn("retailedge-bank-layout", css)

	def test_review_stays_in_edgesuite_workspace_and_uses_existing_workflow_actions(self):
		asset = WORKSPACE_JS.read_text()
		self.assertIn("showReviewMatchDialog", asset)
		self.assertIn('method: "frappe.client.get"', asset)
		self.assertIn("get_reconciliation_approval_state", asset)
		self.assertIn("get_match_account_evidence", asset)
		for method in (
			"retailedge.api.confirm_bank_transaction_match",
			"retailedge.api.reject_bank_transaction_match",
			"retailedge.api.mark_bank_transaction_match_needs_review",
			"retailedge.reconciliation_approval.request_reconciliation_approval",
			"retailedge.reconciliation_approval.approve_reconciliation_for_match",
			"retailedge.reconciliation_approval.decline_reconciliation_for_match",
		):
			self.assertIn(method, asset)

	def test_review_is_comparison_first_and_humanizes_technical_categories(self):
		asset = WORKSPACE_JS.read_text()
		page_css = PAGE_CSS.read_text()
		for label in (
			"Bank Statement",
			"Accounting Record",
			"Bank Identity & Accounting Safety",
			"Why this matches",
			"Business Category",
			"Confirmed Candidate",
			"Reconciled Record",
		):
			self.assertIn(label, asset)
		for technical, label in (
			("payment_entry_match", "Payment Entry"),
			("invoice_payment_row_match", "Invoice Payment Row"),
			("journal_entry_match", "Journal Entry"),
		):
			self.assertIn(technical, asset)
			self.assertIn(label, asset)
		for class_name in (
			"retailedge-bank-compare-grid",
			"retailedge-bank-compare-card",
			"retailedge-bank-detail-grid",
			"retailedge-bank-safety-grid",
		):
			self.assertIn(class_name, asset)
			self.assertIn(class_name, page_css)
		self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", page_css)

	def test_final_reconciliation_requires_explicit_edgesuite_confirmation(self):
		asset = WORKSPACE_JS.read_text()
		self.assertIn("Final Reconciliation", asset)
		self.assertIn("ERPNext remains the reconciliation authority", asset)
		self.assertIn("Submitted accounting documents will not be mutated", asset)
		self.assertIn("state.reconcile.confirmed", asset)
		self.assertIn('type: "checkbox"', asset)
		self.assertIn("Reconcile Through ERPNext", asset)
		self.assertIn("retailedge.banking_operations.match_and_reconcile", asset)
		self.assertIn("confirm_match: 0", asset)
		self.assertIn("confirm_reconciliation: 1", asset)
		self.assertIn("state.reconcile.busy || !state.reconcile.confirmed", asset)


if __name__ == "__main__":
	unittest.main()
