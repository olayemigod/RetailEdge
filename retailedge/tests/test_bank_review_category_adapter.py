from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_ASSET = APP_ROOT / "public/js/bank_review_category_adapter.js"
PAGE_LOADER = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"


class BankReviewCategoryAdapterTests(unittest.TestCase):
	def test_category_adapter_is_valid_javascript(self):
		completed = subprocess.run(
			["node", "--check", str(CATEGORY_ASSET)],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)

	def test_internal_transfer_categories_are_direction_aware(self):
		asset = CATEGORY_ASSET.read_text()
		self.assertIn('paymentType === "Internal Transfer"', asset)
		self.assertIn('direction === "Inflow") return "Deposit to Bank"', asset)
		self.assertIn('direction === "Outflow") return "Bank Transfer"', asset)

	def test_normal_payment_entry_business_categories_are_preserved(self):
		asset = CATEGORY_ASSET.read_text()
		for label in (
			"Customer Receipt",
			"Supplier Payment",
			"Expense",
			"Other Income",
			"Other Outflow",
		):
			self.assertIn(label, asset)
		self.assertIn("BUSINESS_CATEGORIES.has(existingCategory)", asset)

	def test_adapter_is_page_scoped_and_reads_live_payment_entry(self):
		asset = CATEGORY_ASSET.read_text()
		self.assertIn('const PAGE_NAME = "bank-matching-reconciliation"', asset)
		self.assertIn("get_match_account_evidence", asset)
		self.assertIn('method: "frappe.client.get"', asset)
		self.assertIn('doctype: "Payment Entry"', asset)
		self.assertIn("isBankMatchingPage()", asset)

	def test_loader_installs_category_adapter_before_edgesuite_workspace(self):
		loader = PAGE_LOADER.read_text()
		self.assertIn("bank_review_category_adapter.js", loader)
		self.assertIn("bank_matching_edgesuite_workspace.js", loader)
		self.assertLess(
			loader.index("frappe.require(REVIEW_CATEGORY_ASSET)"),
			loader.index("frappe.require(WORKSPACE_ASSET)"),
		)


if __name__ == "__main__":
	unittest.main()
