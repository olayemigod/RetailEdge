from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
HUB = APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"


class TestSimpleMasterCreateSurfaceBridge(unittest.TestCase):
	def test_master_actions_delegate_to_native_create_surface(self):
		bridge = (APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js").read_text(
			encoding="utf-8"
		)
		self.assertIn('const GENERIC_MASTER_CREATE_DOCTYPES = new Set(["Customer", "Supplier", "Item"]);', bridge)
		self.assertIn("action?.master_entry", bridge)
		self.assertIn("global.EdgeSuiteUI?.openCreateSurface", bridge)
		self.assertIn("openCreate(doctype, { allowRestricted: true })", bridge)
		self.assertNotIn("global.frappe?.new_doc?.(doctype)", bridge)
		self.assertIn('return "Quick / Full form";', bridge)
		self.assertNotIn("frappe.ui.form.make_quick_entry", bridge)
		self.assertNotIn("global.frappe.new_doc =", bridge)


	def test_business_hub_uses_shared_create_surface_without_forcing_quick_entry(self):
		hub = HUB.read_text(encoding="utf-8")
		self.assertIn("GENERIC_MASTER_CREATE_ACTIONS", hub)
		self.assertIn("window.EdgeSuiteUI", hub)
		self.assertIn("edgeUI?.openCreateSurface", hub)
		self.assertIn("allowRestricted: true", hub)
		self.assertIn("allowRestricted = false", hub)\n\t\tself.assertIn("EdgeSuite create navigation is unavailable.", hub)
		self.assertNotIn("frappe.new_doc(doctype, defaults)", hub)
		self.assertNotIn("openQuickEntryMaster", hub)
		self.assertNotIn("frappe.ui.form.make_quick_entry", hub)
		self.assertIn("try {", hub)
		self.assertIn("Unable to create ${action.doctype}.", hub)

	def test_complex_setup_masters_are_not_generic_create_promoted(self):
		bridge = (APP_ROOT / "public" / "js" / "retailedge_business_hub_route_bridge.js").read_text(
			encoding="utf-8"
		)
		for doctype in ("Warehouse", "Bank Account", "RetailEdge Expense Category"):
			self.assertNotIn(f'"{doctype}"]', bridge)


if __name__ == "__main__":
	unittest.main()
