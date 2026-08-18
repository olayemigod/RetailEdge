from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
ASSET_JS = APP_ROOT / "public/js/bank_matching_reconciliation.js"


class BankingPageContractTests(unittest.TestCase):
	def test_page_controller_is_thin_edgesuite_loader(self):
		page_js = PAGE_JS.read_text()
		self.assertIn("/assets/retailedge/js/bank_matching_reconciliation.js", page_js)
		self.assertIn("retailedgeBootBankingWorkspace", page_js)
		for raw_tag in ("<table", "<tr", "<td", "<div", "<button", "<a "):
			self.assertNotIn(raw_tag, page_js)

	def test_banking_asset_calls_workspace_and_direction_aware_candidate_services(self):
		asset_js = ASSET_JS.read_text()
		self.assertIn("retailedge.banking_workspace.get_banking_workspace_rows", asset_js)
		self.assertIn("retailedge.bank_candidate_engine.get_direction_aware_bank_candidates", asset_js)
		self.assertIn("All", asset_js)
		self.assertIn("Inflows", asset_js)
		self.assertIn("Outflows", asset_js)
		self.assertIn("To Match", asset_js)
		self.assertIn("To Reconcile", asset_js)
		self.assertIn("Exceptions", asset_js)
		self.assertIn("Reconciled", asset_js)
		self.assertIn("EdgeSuiteUI", asset_js)

	def test_banking_asset_does_not_inject_raw_html_template_strings(self):
		asset_js = ASSET_JS.read_text()
		for raw_tag in ("<table", "<tr", "<td", "<div", "<button", "<a ", "<span"):
			self.assertNotIn(raw_tag, asset_js)
		self.assertNotIn("fieldtype: \"HTML\"", asset_js)
		self.assertNotIn(".html(`", asset_js)

	def test_filters_and_accounting_evidence_are_visible_contracts(self):
		asset_js = ASSET_JS.read_text()
		for fieldname in ("company", "bank_account", "from_date", "to_date", "search"):
			self.assertIn(fieldname, asset_js)
		for label in (
			"Narration / Reference",
			"Bank Amount",
			"Candidate Amount",
			"Difference",
			"Reconcile",
			"Review Suggestion",
			"Find Match",
		):
			self.assertIn(label, asset_js)


if __name__ == "__main__":
	unittest.main()
