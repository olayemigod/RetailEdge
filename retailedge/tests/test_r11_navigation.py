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
		self.assertIn("customer-opportunity-intelligence", targets)
		self.assertLess(targets.index("customer-receivables"), targets.index("customer-sales-intelligence"))
		self.assertLess(targets.index("customer-sales-intelligence"), targets.index("customer-360"))
		self.assertLess(targets.index("customer-360"), targets.index("customer-opportunity-intelligence"))

		for key, group in groups.items():
			if key == "customers":
				continue
			other_targets = {item.get("target") for item in group["items"]}
			self.assertNotIn("customer-sales-intelligence", other_targets)
			self.assertNotIn("customer-360", other_targets)
			self.assertNotIn("customer-opportunity-intelligence", other_targets)

	def test_sales_intelligence_pages_live_in_insights_group_only(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		insights_targets = [item.get("target") for item in groups["insights"]["items"]]
		self.assertIn("basket-affinity", insights_targets)
		self.assertIn("sales-quality-intelligence", insights_targets)
		self.assertLess(insights_targets.index("sales-by-item"), insights_targets.index("basket-affinity"))
		self.assertLess(insights_targets.index("basket-affinity"), insights_targets.index("sales-quality-intelligence"))
		self.assertLess(insights_targets.index("sales-quality-intelligence"), insights_targets.index("sales-invoice-register"))

		for key, group in groups.items():
			if key == "insights":
				continue
			other_targets = {item.get("target") for item in group["items"]}
			self.assertNotIn("basket-affinity", other_targets)
			self.assertNotIn("sales-quality-intelligence", other_targets)


if __name__ == "__main__":
	unittest.main()
