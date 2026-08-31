from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


APP_ROOT = Path(__file__).resolve().parents[1]
APPROVED_TARGETS = [
	"Price List",
	"Item Price",
	"Pricing Rule",
	"Promotional Scheme",
	"Coupon Code",
]


class TestPricingPromotionsNavigationContract(TestCase):
	def test_pricing_promotions_group_uses_native_targets_in_approved_order(self):
		groups = [group for group in NAVIGATION_GROUPS if group["key"] == "pricing-promotions"]
		self.assertEqual(len(groups), 1)

		group = groups[0]
		items = list(group["items"])
		self.assertEqual(group["label"], "Pricing & Promotions")
		self.assertEqual([item["target"] for item in items], APPROVED_TARGETS)
		self.assertTrue(all(item["target_type"] == "DocType" for item in items))

		all_targets = [
			(item["target_type"], item["target"])
			for navigation_group in NAVIGATION_GROUPS
			for item in navigation_group["items"]
		]
		for target in APPROVED_TARGETS:
			self.assertEqual(all_targets.count(("DocType", target)), 1)

	def test_pricing_promotions_remains_native_and_permission_aware(self):
		source = (APP_ROOT / "edgesuite_ui.py").read_text()
		group_start = source.index('"key": "pricing-promotions"')
		group_end = source.index('"key": "buy"', group_start)
		group = source[group_start:group_end]

		self.assertNotIn("required_roles", group)
		self.assertNotIn('"target_type": "Page"', group)
		self.assertNotIn('"target_type": "Report"', group)
		self.assertNotIn('"target_type": "URL"', group)
		self.assertIn('if target_type == "DocType":', source)
		self.assertIn('_has_permission_cached(target, "read", permission_cache)', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
