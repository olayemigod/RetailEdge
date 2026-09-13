from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


APP_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_TARGET = "pricing-promotions-control"
APPROVED_NATIVE_TARGETS = [
	"Price List",
	"Item Price",
	"Pricing Rule",
	"Promotional Scheme",
	"Coupon Code",
	"Loyalty Program",
]


class TestPricingPromotionsNavigationContract(TestCase):
	def test_pricing_promotions_uses_edgesuite_overview_then_native_fallbacks(self):
		groups = [group for group in NAVIGATION_GROUPS if group["key"] == "pricing-promotions"]
		self.assertEqual(len(groups), 1)

		group = groups[0]
		items = list(group["items"])
		self.assertEqual(group["label"], "Pricing & Promotions")
		self.assertEqual((items[0]["target_type"], items[0]["target"]), ("Page", OVERVIEW_TARGET))
		self.assertEqual([item["target"] for item in items[1:]], APPROVED_NATIVE_TARGETS)
		self.assertTrue(all(item["target_type"] == "DocType" for item in items[1:]))

		all_targets = [
			(item["target_type"], item["target"])
			for navigation_group in NAVIGATION_GROUPS
			for item in navigation_group["items"]
		]
		self.assertEqual(all_targets.count(("Page", OVERVIEW_TARGET)), 1)
		for target in APPROVED_NATIVE_TARGETS:
			self.assertEqual(all_targets.count(("DocType", target)), 1)

	def test_pricing_promotions_workspace_uses_governed_edgesuite_runtime(self):
		page_dir = APP_ROOT / "retailedge" / "page" / "pricing_promotions_control"
		self.assertTrue((page_dir / "pricing_promotions_control.json").exists())
		page = (page_dir / "pricing_promotions_control.js").read_text()
		self.assertIn('"edgeui.bundle.js"', page)
		self.assertIn('"native_visual_workspaces.bundle.js"', page)
		self.assertIn('"pricing-promotions"', page)
		self.assertIn("mountNativeERPNextWorkspace", page)
		self.assertNotIn("window.EdgeUI", page)
		self.assertNotIn("frappe.ui.Dialog", page)
		self.assertNotIn("frappe.prompt", page)
		self.assertNotIn("frappe.msgprint", page)

	def test_pricing_promotions_remains_permission_aware_and_erpnext_authoritative(self):
		navigation_source = (APP_ROOT / "edgesuite_ui.py").read_text()
		workspace_source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		group_start = navigation_source.index('"key": "pricing-promotions"')
		group_end = navigation_source.index('"key": "buy"', group_start)
		group = navigation_source[group_start:group_end]

		self.assertNotIn("required_roles", group)
		self.assertIn('"target_type": "Page"', group)
		self.assertIn('if target_type == "DocType":', navigation_source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', navigation_source)
		for target in APPROVED_NATIVE_TARGETS:
			self.assertIn(f'"target": "{target}"', workspace_source)
		self.assertIn('frappe.has_permission(doctype, "read")', workspace_source)
		self.assertIn("frappe.get_list(", workspace_source)
		for forbidden in (
			"ignore_permissions",
			"frappe.db.commit",
			".insert(",
			".submit(",
			"GL Entry",
			"Stock Ledger Entry",
		):
			self.assertNotIn(forbidden, workspace_source)


if __name__ == "__main__":
	import unittest

	unittest.main()
