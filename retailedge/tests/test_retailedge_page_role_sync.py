from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestRetailEdgePageRoleSync(unittest.TestCase):
	def test_cashier_alias_is_a_governed_role_variant(self):
		source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
		self.assertIn('"RetailEdgeCashier": ("RetailEdge Cashier",)', source)

	def test_after_migrate_role_setup_repairs_page_role_variants(self):
		source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")

		self.assertIn('"retailedge.setup_roles.ensure_retailedge_roles"', hooks)
		self.assertIn("_ensure_retailedge_page_role_variants()", source)
		self.assertIn('filters={"module": "RetailEdge"}', source)
		self.assertIn('"parenttype": "Page"', source)
		self.assertIn('"parentfield": "roles"', source)
		self.assertIn('not frappe.db.exists("Role", variant)', source)
		self.assertIn(").db_insert()", source)
		self.assertIn('frappe.get_doc("Page", page_name).clear_cache()', source)

	def test_page_role_reconciliation_does_not_resave_entire_page(self):
		source = (APP_ROOT / "setup_roles.py").read_text(encoding="utf-8")
		function_source = source.split("def _ensure_retailedge_page_role_variants()", 1)[1]

		self.assertNotIn('page.save(ignore_permissions=True)', function_source)
		self.assertNotIn('page.append("roles"', function_source)

	def test_business_hub_declares_both_cashier_role_variants(self):
		source = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "retailedge_business_hub"
			/ "retailedge_business_hub.json"
		).read_text(encoding="utf-8")
		self.assertIn('"role": "RetailEdge Cashier"', source)
		self.assertIn('"role": "RetailEdgeCashier"', source)

	def test_stale_accounts_reviewer_is_not_declared_on_pages(self):
		for relative_path in (
			"retailedge/page/retailedge_business_hub/retailedge_business_hub.json",
			"retailedge/page/reports_centre/reports_centre.json",
		):
			source = (APP_ROOT / relative_path).read_text(encoding="utf-8")
			self.assertNotIn("RetailEdge Accounts Reviewer", source)

	def test_stale_accounts_reviewer_cleanup_is_bounded_and_registered(self):
		patch_source = (
			APP_ROOT / "patches" / "remove_stale_accounts_reviewer_page_roles.py"
		).read_text(encoding="utf-8")
		patches = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")

		self.assertIn("retailedge.patches.remove_stale_accounts_reviewer_page_roles", patches)
		self.assertIn('STALE_ROLE = "RetailEdge Accounts Reviewer"', patch_source)
		self.assertIn('"retailedge-business-hub"', patch_source)
		self.assertIn('"reports-centre"', patch_source)
		self.assertIn('"parenttype": "Page"', patch_source)
		self.assertIn('"parentfield": "roles"', patch_source)
		self.assertNotIn('frappe.db.delete("Role"', patch_source)


if __name__ == "__main__":
	unittest.main()
