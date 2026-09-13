import unittest

from retailedge import edgesuite_ui


def _group(key):
	return next(group for group in edgesuite_ui.NAVIGATION_GROUPS if group["key"] == key)


class TestInventoryNavigationContract(unittest.TestCase):
	def test_r10_inventory_pages_are_classified_without_hiding_native_detail_report(self):
		stock = _group("stock")
		stock_items = {item["label"]: item for item in stock["items"]}
		self.assertEqual(stock_items["Inventory Intelligence"]["target"], "inventory-intelligence")
		self.assertEqual(
			stock_items["Transfer Opportunities"]["target"],
			"inventory-transfer-opportunities",
		)
		self.assertEqual(stock_items["Inventory Ageing"]["target"], "inventory-ageing")
		self.assertEqual(stock_items["Stock Ageing (Detailed)"]["target_type"], "Report")
		self.assertEqual(stock_items["Stock Ageing (Detailed)"]["target"], "Stock Ageing")

		insights = _group("insights")
		insight_items = {item["label"]: item for item in insights["items"]}
		self.assertEqual(insight_items["Inventory + Profitability"]["target_type"], "Page")
		self.assertEqual(
			insight_items["Inventory + Profitability"]["target"],
			"inventory-profitability",
		)


if __name__ == "__main__":
	unittest.main()
