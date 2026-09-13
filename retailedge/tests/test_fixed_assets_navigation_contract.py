from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


APP_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_TARGET = "assets-control"
APPROVED_NATIVE_TARGETS = ["Asset", "Asset Category"]


class TestFixedAssetsNavigationContract(TestCase):
	def test_assets_use_edgesuite_overview_then_native_fallbacks(self):
		groups = [group for group in NAVIGATION_GROUPS if group["key"] == "assets"]
		self.assertEqual(len(groups), 1)
		group = groups[0]
		items = list(group["items"])

		self.assertEqual(group["label"], "Assets")
		self.assertEqual((items[0]["target_type"], items[0]["target"]), ("Page", OVERVIEW_TARGET))
		self.assertEqual([item["target"] for item in items[1:]], APPROVED_NATIVE_TARGETS)
		self.assertTrue(all(item["target_type"] == "DocType" for item in items[1:]))
		self.assertNotIn("required_roles", group)

		all_targets = [
			(item["target_type"], item["target"])
			for navigation_group in NAVIGATION_GROUPS
			for item in navigation_group["items"]
		]
		self.assertEqual(all_targets.count(("Page", OVERVIEW_TARGET)), 1)
		for target in APPROVED_NATIVE_TARGETS:
			self.assertEqual(all_targets.count(("DocType", target)), 1)

	def test_assets_workspace_uses_governed_edgesuite_runtime(self):
		page_dir = APP_ROOT / "retailedge" / "page" / "assets_control"
		self.assertTrue((page_dir / "assets_control.json").exists())
		page = (page_dir / "assets_control.js").read_text()
		self.assertIn('"edgeui.bundle.js"', page)
		self.assertIn('"native_visual_workspaces.bundle.js"', page)
		self.assertIn('"assets"', page)
		self.assertIn("mountNativeERPNextWorkspace", page)
		self.assertNotIn("window.EdgeUI", page)
		self.assertNotIn("frappe.ui.Dialog", page)
		self.assertNotIn("frappe.prompt", page)
		self.assertNotIn("frappe.msgprint", page)

	def test_assets_remain_permission_aware_and_erpnext_authoritative(self):
		navigation_source = (APP_ROOT / "edgesuite_ui.py").read_text()
		workspace_source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		group_start = navigation_source.index('"key": "assets"')
		group_end = navigation_source.index('"key": "money"', group_start)
		group = navigation_source[group_start:group_end]

		self.assertNotIn("required_roles", group)
		self.assertIn('if target_type == "DocType":', navigation_source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', navigation_source)
		self.assertIn('"target": "Asset"', workspace_source)
		self.assertIn('"target": "Asset Category"', workspace_source)
		self.assertIn('frappe.has_permission(doctype, "read")', workspace_source)
		self.assertIn("frappe.get_list(", workspace_source)

	def test_retailedge_does_not_wrap_native_asset_lifecycle(self):
		workspace_source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		for forbidden in (
			"create_asset_movement",
			"create_asset_repair",
			"create_asset_maintenance",
			"create_asset_value_adjustment",
			"sell_asset",
			"scrap_asset",
			"restore_asset",
			"make_journal_entry",
			"ignore_permissions",
			"frappe.db.commit",
			".insert(",
			".submit(",
		):
			self.assertNotIn(forbidden, workspace_source)


if __name__ == "__main__":
	import unittest

	unittest.main()
