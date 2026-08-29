from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
COMPLETION_JS = APP_ROOT / "public/js/bank_matching_edgesuite_completion_adapter.js"
COMPLETION_CSS = APP_ROOT / "public/css/bank_matching_edgesuite_completion.css"
READINESS_JS = APP_ROOT / "retailedge/page/banking_readiness/banking_readiness.js"


class BankingEdgeSuiteCompletionContractTests(unittest.TestCase):
	def test_completion_assets_are_loaded_before_workspace_start(self):
		page_js = PAGE_JS.read_text()
		self.assertIn("bank_matching_edgesuite_completion.css", page_js)
		self.assertIn("bank_matching_edgesuite_completion_adapter.js", page_js)
		workspace = page_js.index("frappe.require(WORKSPACE_ASSET)")
		completion = page_js.index("frappe.require(COMPLETION_ASSET)")
		start = page_js.index("startWorkspace(wrapper)", completion)
		self.assertLess(workspace, completion)
		self.assertLess(completion, start)

	def test_completion_javascript_is_valid(self):
		completed = subprocess.run(
			["node", "--check", str(COMPLETION_JS)],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)

	def test_review_restores_planned_operational_context(self):
		asset = COMPLETION_JS.read_text()
		for label in (
			"Bank Narration",
			"Branch",
			"Mode of Payment",
			"Payment Event Source",
			"Business Category",
			"Accounting / Hard Match Evidence",
			"Fuzzy / Supplemental Evidence",
			"Operational Guidance",
		):
			self.assertIn(label, asset)
		self.assertIn("Supporting evidence only; it cannot override a bank/GL mismatch.", asset)
		self.assertIn("Matching does not reconcile the Bank Transaction", asset)
		self.assertIn("recommended_action", asset)

	def test_completion_is_read_only_and_page_scoped(self):
		asset = COMPLETION_JS.read_text()
		self.assertIn('const PAGE_NAME = "bank-matching-reconciliation"', asset)
		self.assertIn("get_bank_match_operational_status", asset)
		for forbidden in (
			"frappe.ui.Dialog",
			"match_and_reconcile",
			"confirm_bank_transaction_match",
			"approve_reconciliation_for_match",
			"frappe.db.set_value",
			"frappe.client.set_value",
		):
			self.assertNotIn(forbidden, asset)

	def test_completion_css_uses_edgesuite_semantic_tokens_and_responsive_layout(self):
		css = COMPLETION_CSS.read_text()
		self.assertIn("var(--edge-color-", css)
		self.assertIn("var(--edge-space-", css)
		self.assertIn("@media (max-width: 760px)", css)

	def test_readiness_adds_state_filter_and_gl_drill_through(self):
		asset = READINESS_JS.read_text()
		self.assertIn('getComponent("EdgeDropdown")', asset)
		self.assertIn("Readiness State", asset)
		self.assertIn("All States", asset)
		self.assertIn("visibleRows", asset)
		self.assertIn("Open GL Account", asset)
		self.assertIn('frappe.set_route("Form", "Account", row.resolved_gl_account)', asset)
		self.assertIn("Open ERPNext Bank Account", asset)


if __name__ == "__main__":
	unittest.main()
