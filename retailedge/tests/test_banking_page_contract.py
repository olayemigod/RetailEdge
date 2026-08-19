from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
PAGE_CSS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.css"
ASSET_JS = APP_ROOT / "public/js/bank_matching_reconciliation.js"


class BankingPageContractTests(unittest.TestCase):
	def test_page_controller_is_thin_edgesuite_loader(self):
		page_js = PAGE_JS.read_text()
		self.assertIn("/assets/retailedge/js/bank_matching_reconciliation.js", page_js)
		self.assertIn("retailedgeBootBankingWorkspace", page_js)
		for raw_tag in ("<table", "<tr", "<td", "<div", "<button", "<a "):
			self.assertNotIn(raw_tag, page_js)

	def test_page_controller_uses_promise_based_frappe_require(self):
		page_js = PAGE_JS.read_text()
		self.assertIn("Promise.resolve(frappe.require(ASSET))", page_js)
		self.assertIn(".then(() => startWorkspace(wrapper))", page_js)
		self.assertIn(".catch((error) =>", page_js)
		self.assertNotIn("frappe.require(ASSET,", page_js)

	def test_banking_asset_is_valid_javascript(self):
		completed = subprocess.run(
			["node", "--check", str(ASSET_JS)],
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

	def test_banking_asset_does_not_inject_raw_html_template_strings(self):
		asset_js = ASSET_JS.read_text()
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
		for label in (
			"Accounting / Hard Score",
			"Supplemental Fuzzy Evidence",
			"Confirm Match",
			"Reject Match",
			"Keep for Review",
			"Open Audit Record",
		):
			self.assertIn(label, asset_js)
		self.assertIn("Match confirmed. Reconciliation is still required.", asset_js)


if __name__ == "__main__":
	unittest.main()
