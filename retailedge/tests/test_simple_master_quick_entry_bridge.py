from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSimpleMasterQuickEntryBridge(unittest.TestCase):
	def test_master_actions_are_page_scoped_quick_entries(self):
		bridge = (APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js").read_text(
			encoding="utf-8"
		)
		self.assertIn('const SIMPLE_MASTER_DOCTYPES = new Set(["Customer", "Supplier", "Item"]);', bridge)
		self.assertIn("action?.master_entry", bridge)
		self.assertIn("frappe.ui.form.make_quick_entry", bridge)
		self.assertIn('return "Quick entry";', bridge)
		self.assertNotIn("global.frappe.new_doc =", bridge)

	def test_complex_setup_masters_are_not_quick_entry_promoted(self):
		bridge = (APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js").read_text(
			encoding="utf-8"
		)
		for doctype in ("Warehouse", "Bank Account", "RetailEdge Expense Category"):
			self.assertNotIn(f'"{doctype}"]', bridge)


if __name__ == "__main__":
	unittest.main()
