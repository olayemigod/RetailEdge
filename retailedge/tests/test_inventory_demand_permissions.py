from __future__ import annotations

import unittest

import frappe

from retailedge.inventory_demand import _aggregate_demand


class TestInventoryDemandPermissions(unittest.TestCase):
	def test_unreadable_items_are_not_returned_from_sle_aggregation(self):
		rows = [
			frappe._dict(
				item_code="VISIBLE-ITEM",
				warehouse="Stores - TC",
				actual_qty=-5,
				posting_date="2026-08-20",
			),
			frappe._dict(
				item_code="HIDDEN-ITEM",
				warehouse="Stores - TC",
				actual_qty=-9,
				posting_date="2026-08-21",
			),
		]
		item_map = {
			"VISIBLE-ITEM": frappe._dict(
				item_name="Visible Item",
				item_group="Products",
				stock_uom="Nos",
			)
		}

		locations, items = _aggregate_demand(
			rows,
			item_map=item_map,
			to_date=frappe.utils.getdate("2026-08-23"),
			lookback_days=30,
		)

		self.assertEqual([row["item_code"] for row in items], ["VISIBLE-ITEM"])
		self.assertEqual([row["item_code"] for row in locations], ["VISIBLE-ITEM"])
		self.assertEqual(items[0]["demand_qty"], 5)


if __name__ == "__main__":
	unittest.main()
