from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BRANCH_SETUP_VUE = APP_ROOT / "public" / "js" / "branch_setup" / "BranchSetup.vue"
BRANCH_PRINT_VISIBILITY = APP_ROOT / "branch_print_visibility.py"


class TestBranchPrintVisibilityEdgeSuite(unittest.TestCase):
	def test_branch_setup_exposes_customer_facing_branch_visibility(self):
		source = BRANCH_SETUP_VUE.read_text(encoding="utf-8")
		for contract in (
			"Show Branch on Printed Documents",
			"show_branch_on_printed_documents",
			"retailedge.branch_print_visibility.get_branch_setup_with_print_visibility",
			"retailedge.branch_print_visibility.save_branch_setup_with_print_visibility",
		):
			self.assertIn(contract, source)

	def test_visibility_bridge_reuses_branch_setup_validation_and_permissions(self):
		source = BRANCH_PRINT_VISIBILITY.read_text(encoding="utf-8")
		for contract in (
			"from retailedge.branch_setup import get_branch_setup, save_branch_setup",
			"BRANCH_PRINT_VISIBILITY_FIELD",
			'doc.check_permission("read")',
			'doc.check_permission("write")',
			"result = save_branch_setup(values)",
			"doc.set(BRANCH_PRINT_VISIBILITY_FIELD, show_branch)",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit", source)


if __name__ == "__main__":
	unittest.main()
