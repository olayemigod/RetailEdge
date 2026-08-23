from __future__ import annotations

import unittest
from unittest.mock import patch

from frappe.utils import today

from retailedge import inventory_health


class TestInventoryHealthFilters(unittest.TestCase):
	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_movement_filter_recalculates_stock_summary_on_visible_rows(self, stock, demand):
		stock.return_value = {
			"columns": [
				{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"},
				{"fieldname": "stock_value", "label": "Stock Value", "fieldtype": "Currency"},
			],
			"rows": [
				{
					"item_code": "DEAD",
					"actual_qty": 10,
					"reserved_qty": 0,
					"available_qty": 10,
					"ordered_qty": 0,
					"projected_qty": 10,
					"stock_value": 1000,
				},
				{
					"item_code": "ACTIVE",
					"actual_qty": 20,
					"reserved_qty": 0,
					"available_qty": 20,
					"ordered_qty": 0,
					"projected_qty": 20,
					"stock_value": 4000,
				},
			],
			"summary": [],
			"company_currency": "NGN",
			"show_costs": 1,
			"scope": {"company": "Test Company", "warehouse_count": 1},
			"scan": {},
		}
		demand.return_value = {
			"rows": [
				{
					"item_code": "ACTIVE",
					"demand_qty": 90,
					"average_daily_demand": 1,
					"last_demand_on": today(),
					"days_since_demand": 0,
				}
			],
			"scope": {"lookback_days": 90, "from_date": "2026-05-26", "to_date": today()},
			"scan": {},
			"metadata": {},
		}

		result = inventory_health.get_inventory_health(
			{
				"company": "Test Company",
				"movement_class": "Non-moving",
				"lookback_days": 90,
			},
			page=1,
			page_size=25,
		)

		self.assertEqual([row["item_code"] for row in result["rows"]], ["DEAD"])
		summary = {card["label"]: card["value"] for card in result["summary"]}
		self.assertEqual(summary["Items in Scope"], 1)
		self.assertEqual(summary["Stock Value"], 1000)
		self.assertEqual(summary["Non-moving"], 1)


if __name__ == "__main__":
	unittest.main()
