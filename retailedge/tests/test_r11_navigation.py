from __future__ import annotations

import unittest

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


class TestR11Navigation(unittest.TestCase):
	def test_customer_intelligence_pages_live_in_customers_group_only(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		customers = groups["customers"]
		targets = [item.get("target") for item in customers["items"]]

		self.assertIn("customer-sales-intelligence", targets)
		self.assertIn("customer-360", targets)
		self.assertLess(targets.index("customer-receivables"), targets.index("customer-sales-intelligence"))
		self.assertLess(targets.index("customer-sales-intelligence"), targets.index("customer-360"))

		for key, group in groups.items():
			if key == "customers":
				continue
			other_targets = {item.get("target") for item in group["items"]}
			self.assertNotIn("customer-sales-intelligence", other_targets)
			self.assertNotIn("customer-360", other_targets)


if __name__ == "__main__":
	unittest.main()
