from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
ADAPTER_JS = APP_ROOT / "public/js/bank_matching_branch_search_adapter.js"
COMPLETION_CSS = APP_ROOT / "public/css/bank_matching_edgesuite_completion.css"


class BankingBranchSearchAdapterContractTests(unittest.TestCase):
	def test_branch_adapter_is_loaded_before_workspace(self):
		page = PAGE_JS.read_text()
		self.assertIn("bank_matching_branch_search_adapter.js", page)
		self.assertLess(page.index("frappe.require(BRANCH_SEARCH_ASSET)"), page.index("frappe.require(WORKSPACE_ASSET)"))

	def test_branch_adapter_redirects_only_banking_branch_search(self):
		asset = ADAPTER_JS.read_text()
		self.assertIn('const PAGE_NAME = "bank-matching-reconciliation"', asset)
		self.assertIn('request?.args?.doctype === "Branch"', asset)
		self.assertIn("retailedge.banking_link_search.search_banking_branches", asset)
		self.assertIn("request.args.filters.company", asset)

	def test_branch_adapter_javascript_is_valid(self):
		completed = subprocess.run(
			["node", "--check", str(ADAPTER_JS)],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)

	def test_density_pass_preserves_typography_and_styles_links_as_navigation(self):
		css = COMPLETION_CSS.read_text()
		self.assertIn("Bank Transaction and Candidate are navigation controls", css)
		self.assertIn(".retailedge-bank-table .edge-link-button", css)
		self.assertIn("background: transparent", css)
		self.assertIn("padding-top", css)
		# This density pass must not repeat the earlier app-wide typography regression.
		for selector in (
			".retailedge-bank-layout {\n\tfont-size:",
			".retailedge-bank-layout .edge-filter-bar,\n.retailedge-bank-layout .edge-action-bar,\n.retailedge-bank-layout .edge-stat-card {\n\tfont-size:",
		):
			self.assertNotIn(selector, css)


if __name__ == "__main__":
	unittest.main()
