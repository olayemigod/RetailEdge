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
		self.assertIn('page.append("roles", {"role": role_name})', source)
		self.assertIn("page.flags.do_not_update_json = True", source)
		self.assertIn("page.save(ignore_permissions=True)", source)

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


if __name__ == "__main__":
	unittest.main()
