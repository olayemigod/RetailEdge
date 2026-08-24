from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
PAGE_CSS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.css"
ASSET_JS = APP_ROOT / "public/js/bank_matching_reconciliation.js"
REVIEW_ASSET_JS = APP_ROOT / "public/js/bank_match_review_ui.js"
CONFIRMATION_ASSET_JS = APP_ROOT / "public/js/bank_reconciliation_confirmation.js"


class BankingPageContractTests(unittest.TestCase):
	def test_page_controller_is_thin_edgesuite_loader(self):
		page_js = PAGE_JS.read_text()
		self.assertIn("/assets/retailedge/js/bank_matching_reconciliation.js", page_js)
		self.assertIn("/assets/retailedge/js/bank_match_review_ui.js", page_js)
		self.assertIn("/assets/retailedge/js/bank_reconciliation_confirmation.js", page_js)
		self.assertIn("retailedgeBootBankingWorkspace", page_js)
		for raw_tag in ("<table", "<tr", "<td", "<div", "<button", "<a "):
			self.assertNotIn(raw_tag, page_js)

	def test_page_controller_uses_promise_based_frappe_require(self):
		page_js = PAGE_JS.read_text()
		self.assertIn("Promise.resolve(frappe.require(ASSET))", page_js)
		self.assertIn("Promise.resolve(frappe.require(REVIEW_ASSET))", page_js)
		self.assertIn("Promise.resolve(frappe.require(CONFIRMATION_ASSET))", page_js)
		self.assertIn(".then(() => startWorkspace(wrapper))", page_js)
		self.assertIn(".catch((error) =>", page_js)
		self.assertNotIn("frappe.require(ASSET,", page_js)

	def test_banking_assets_are_valid_javascript(self):
		for asset in (ASSET_JS, REVIEW_ASSET_JS, CONFIRMATION_ASSET_JS):
			completed = subprocess.run(
				["node", "--check", str(asset)],
				capture_output=True,
				text=True,
				check=False,
			)
			self.assertEqual(completed.returncode, 0, completed.stderr)

	def test_banking_asset_calls_workspace_and_direction_aware_candidate_services(self):
		asset_js = ASSET_JS.read_text()
		self.assertIn("retailedge.banking_workspace.get_banking_workspace_rows", asset_js)
		self.assertIn("retailedge.bank_candidate_engine.get_direction_aware_bank_candidates", asset_js)
		for label in ("All", "Inflows", "Outflows", "To Match", "To Reconcile", "Exceptions", "Reconciled"):
			self.assertIn(label, asset_js)
		self.assertIn("EdgeSuiteUI", asset_js)

	def test_banking_assets_do_not_inject_raw_html_template_strings(self):
		for asset in (ASSET_JS, REVIEW_ASSET_JS, CONFIRMATION_ASSET_JS):
			asset_js = asset.read_text()
			for raw_tag in ("<table", "<tr", "<td", "<div", "<button", "<a ", "<span"):
				self.assertNotIn(raw_tag, asset_js)
			self.assertNotIn("fieldtype: \"HTML\"", asset_js)
			self.assertNotIn(".html(`", asset_js)

	def test_filters_and_accounting_evidence_are_visible_contracts(self):
		asset_js = ASSET_JS.read_text()
		for fieldname in ("company", "branch", "bank_account", "from_date", "to_date", "search"):
			self.assertIn(fieldname, asset_js)
		self.assertIn('options: "Branch"', asset_js)
		self.assertIn('options: "Bank Account"', asset_js)
		self.assertIn("companyFilter", asset_js)
		for label in (
			"Bank Transaction",
			"Bank Amount",
			"Difference",
			"Workflow Status",
			"Direction",
			"Reconcile",
			"Review Suggestion",
			"Find Match",
		):
			self.assertIn(label, asset_js)

	def test_banking_table_is_compact_and_narration_is_clamped(self):
		asset_js = ASSET_JS.read_text()
		page_css = PAGE_CSS.read_text()
		for class_name in (
			"retailedge-col-transaction",
			"retailedge-col-candidate",
			"retailedge-bank-narration",
			"retailedge-bank-meta",
		):
			self.assertIn(class_name, asset_js)
			self.assertIn(class_name, page_css)
		self.assertIn("-webkit-line-clamp: 2", page_css)
		self.assertIn("table-layout: fixed", page_css)

	def test_candidate_select_uses_frappe_string_options_not_object_options(self):
		asset_js = ASSET_JS.read_text()
		self.assertIn('options: optionLabels.join("\\n")', asset_js)
		self.assertNotIn("options: candidates.map((row, index) => ({", asset_js)
		self.assertNotIn("`${index} ·", asset_js)

	def test_review_match_stays_in_banking_workspace_and_uses_existing_workflow_actions(self):
		asset_js = ASSET_JS.read_text()
		self.assertIn("showReviewMatchDialog", asset_js)
		self.assertIn('method: "frappe.client.get"', asset_js)
		self.assertIn('"retailedge.api.confirm_bank_transaction_match"', asset_js)
		self.assertIn('"retailedge.api.reject_bank_transaction_match"', asset_js)
		self.assertIn('"retailedge.api.mark_bank_transaction_match_needs_review"', asset_js)
		self.assertIn("Match confirmed. Reconciliation is still required.", asset_js)

	def test_final_reconciliation_confirmation_is_single_submit_and_fails_visibly(self):
		confirmation_js = CONFIRMATION_ASSET_JS.read_text()
		self.assertIn("Final Reconciliation Confirmation", confirmation_js)
		self.assertIn("Reconcile Through ERPNext", confirmation_js)
		self.assertIn("const originalConfirm = frappe.confirm.bind(frappe)", confirmation_js)
		self.assertIn("if (message !== BANK_RECONCILIATION_CONFIRM_MESSAGE)", confirmation_js)
		self.assertIn("return originalConfirm(message, ifYes, ifNo)", confirmation_js)
		self.assertIn("let submitting = false", confirmation_js)
		self.assertIn("if (submitting) return", confirmation_js)
		self.assertIn("await Promise.resolve(ifYes?.())", confirmation_js)
		self.assertIn("setPrimaryDisabled(dialog, true)", confirmation_js)
		self.assertIn("setPrimaryDisabled(dialog, false)", confirmation_js)
		self.assertIn("do not retry blindly", confirmation_js)
		self.assertIn("secondary_action_label: __(\"Cancel\")", confirmation_js)

	def test_review_ui_is_side_by_side_and_comparison_first(self):
		review_js = REVIEW_ASSET_JS.read_text()
		page_css = PAGE_CSS.read_text()
		for label in (
			"Bank Statement",
			"Accounting Record",
			"Bank Identity & Accounting Safety",
			"Bank Account",
			"GL Account",
			"Additional Context",
			"Why this matches",
			"Accounting / Hard Match Evidence",
			"Fuzzy / Supplemental Evidence",
			"Matching does not reconcile the bank transaction",
		):
			self.assertIn(label, review_js)

		statement_rows = (
			'valueRow("Bank Transaction", statementRecord)',
			'valueRow("Bank", statement.bank)',
			'valueRow("Bank Account", statement.bank_account',
			'valueRow("GL Account", statement.gl_account)',
			'valueRow("Company", statement.company',
			'valueRow("Branch", statement.branch',
			'valueRow("Direction", direction',
			'valueRow("Amount", money(statement.amount ?? doc.bank_amount',
			'valueRow("Date", statement.date || doc.transaction_date)',
			'valueRow("Reference", statement.reference',
		)
		accounting_rows = (
			'valueRow("Accounting Document", accountingRecord',
			'valueRow("Bank", accounting.bank)',
			'valueRow("Bank Account", accounting.bank_account',
			'valueRow(accounting.gl_account_label || "Bank-side Account", accounting.gl_account)',
			'valueRow("Company", accounting.company)',
			'valueRow("Branch", accounting.branch)',
			'valueRow("Direction", direction',
			'valueRow("Amount", money(accounting.amount ?? doc.candidate_amount',
			'valueRow("Date", accounting.date)',
			'valueRow("Reference", accounting.reference)',
		)

		bank_rows_start = review_js.index("\t\tbankRows.append(")
		bank_rows_end = review_js.index("\n\n\t\tcandidateRows.append(", bank_rows_start)
		bank_rows_block = review_js[bank_rows_start:bank_rows_end]

		candidate_rows_start = review_js.index("\t\tcandidateRows.append(", bank_rows_end)
		candidate_rows_end = review_js.index("\n\n\t\tbankCard.appendChild(bankRows)", candidate_rows_start)
		candidate_rows_block = review_js[candidate_rows_start:candidate_rows_end]

		for block, rows in (
			(bank_rows_block, statement_rows),
			(candidate_rows_block, accounting_rows),
		):
			positions = [block.index(snippet) for snippet in rows]
			self.assertEqual(positions, sorted(positions))

		self.assertIn('valueRow(accounting.gl_account_label || "Bank-side Account", accounting.gl_account)', review_js)
		self.assertIn('[__("Bank Narration"), doc.bank_narration || bank.description]', review_js)
		self.assertIn('[__("Mode of Payment"), accounting.mode_of_payment || doc.payment_mode || candidate.payment_mode]', review_js)
		self.assertNotIn("Proposed Match (Accounting)", review_js)
		for class_name in (
			"retailedge-review-compare",
			"retailedge-review-card",
			"retailedge-review-card-rows",
			"retailedge-review-evidence-grid",
			"retailedge-review-info-banner",
		):
			self.assertIn(class_name, review_js)
			self.assertIn(class_name, page_css)
		self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", page_css)


if __name__ == "__main__":
	unittest.main()
