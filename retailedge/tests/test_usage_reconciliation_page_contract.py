from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class UsageReconciliationPageContractTests(unittest.TestCase):
	def test_page_is_role_restricted_and_uses_generic_product_wording(self):
		page_root = APP_ROOT / "retailedge" / "page" / "usage_reconciliation"
		metadata = json.loads((page_root / "usage_reconciliation.json").read_text())
		script = (page_root / "usage_reconciliation.js").read_text()

		self.assertEqual(metadata["name"], "usage-reconciliation")
		self.assertEqual(metadata["title"], "Usage Reconciliation")
		roles = {row["role"] for row in metadata["roles"]}
		self.assertIn("System Manager", roles)
		self.assertIn("RetailEdge Manager", roles)
		self.assertIn("RetailEdge Auditor", roles)
		self.assertNotIn("Sales User", roles)
		self.assertNotIn("RetailEdge Branch Manager", roles)
		self.assertIn('frappe.pages[PAGE_NAME]', script)
		self.assertIn("retailedge.usage_reconciliation.get_usage_reconciliation", script)
		self.assertIn("retailedge.usage_reconciliation.retry_usage_finalization", script)
		self.assertNotIn("CoreEdge", script)

	def test_page_exposes_safe_actions_only(self):
		script = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "usage_reconciliation"
			/ "usage_reconciliation.js"
		).read_text()
		self.assertIn("Open Sale", script)
		self.assertIn("Retry Finalization", script)
		self.assertIn('type: "POST"', script)
		self.assertIn("No new reservation will be created", script)
		self.assertNotIn("reserve_usage", script)
		self.assertNotIn("cancel(", script)

	def test_navigation_places_page_in_operations_review(self):
		edgesuite = (APP_ROOT / "edgesuite_ui.py").read_text()
		master = (APP_ROOT / "master_experience.py").read_text()
		self.assertIn('"label": "Usage Reconciliation"', edgesuite)
		self.assertIn('"target": "usage-reconciliation"', edgesuite)
		self.assertIn("USAGE_RECONCILIATION_ROLES", edgesuite)
		self.assertIn('"usage-reconciliation"', master)
		operations = master.index("OPERATIONS_REVIEW_TARGETS")
		usage = master.index('"usage-reconciliation"', operations)
		banking = master.index("BANKING_RECONCILIATION_TARGETS", operations)
		self.assertLess(usage, banking)

	def test_company_branch_cascade_and_pagination_are_visible(self):
		script = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "usage_reconciliation"
			/ "usage_reconciliation.js"
		).read_text()
		self.assertIn('label: t("Company")', script)
		self.assertIn('label: t("Branch")', script)
		self.assertIn('state.branch = "";', script)
		self.assertIn("page_length: PAGE_LENGTH", script)
		self.assertIn("Load More", script)


if __name__ == "__main__":
	unittest.main()
