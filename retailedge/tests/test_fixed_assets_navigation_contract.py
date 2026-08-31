from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFixedAssetsNavigationContract(TestCase):
	def test_assets_group_uses_native_permission_aware_destinations(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "assets"')
		group_end = source.index('"key": "money"', group_start)
		group = source[group_start:group_end]

		self.assertEqual(group.count('"key": "assets"'), 1)
		self.assertEqual(group.count('"label": "Fixed Assets"'), 1)
		self.assertEqual(group.count('"label": "Asset Categories"'), 1)
		self.assertIn('"target_type": "DocType", "target": "Asset"', group)
		self.assertIn('"target_type": "DocType", "target": "Asset Category"', group)
		self.assertNotIn("required_roles", group)

		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)

	def test_retailedge_does_not_wrap_native_asset_lifecycle(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()

		for forbidden in (
			"create_asset_movement",
			"create_asset_repair",
			"create_asset_maintenance",
			"create_asset_value_adjustment",
			"sell_asset",
			"scrap_asset",
			"restore_asset",
			"make_journal_entry",
			'frappe.get_doc("Asset"',
			'"doctype": "Asset"',
			"ignore_permissions",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	import unittest

	unittest.main()
