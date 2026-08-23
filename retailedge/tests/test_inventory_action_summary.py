from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe
from frappe.utils import today

from retailedge import inventory_health


def _stock_payload(row):
	return {
		"columns": [{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"}],
		"rows": [row],
		"summary": [],
		"company_currency": "",
		"show_costs": 0,
		"scope": {"company": "Test Company", "warehouse_count": 1},
		"scan": {"bin_rows": 1},
	}


def _cards(result):
	return {card["label"]: card["value"] for card in result["summary"]}


class TestInventoryActionSummary(unittest.TestCase):
	@patch(
		"retailedge.inventory_health.get_historical_inventory_demand",
		side_effect=frappe.ValidationError("demand scope too broad"),
	)
	@patch("retailedge.inventory_health.get_inventory_replenishment")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_demand_failure_does_not_remove_current_stock_or_reorder_actions(
		self, stock, replenishment, _demand
	):
		stock.return_value = _stock_payload(
			{
				"item_code": "ITEM-1",
				"item_name": "Item One",
				"actual_qty": -2,
				"reserved_qty": 0,
				"available_qty": -2,
				"stock_status": "Negative",
			}
		)
		replenishment.return_value = {
			"items": [
				{
					"item_code": "ITEM-1",
					"configured_location_count": 1,
					"triggered_location_count": 1,
					"unavailable_rule_count": 0,
					"recommended_reorder_qty": 12,
					"replenishment_status": "Reorder Now",
				}
			],
			"scan": {},
			"metadata": {},
		}

		result = inventory_health.get_inventory_action_summary({"company": "Test Company"})
		cards = _cards(result)

		self.assertEqual(cards["Negative Stock"], 1)
		self.assertEqual(cards["Items Requiring Reorder"], 1)
		self.assertNotIn("Non-moving", cards)
		self.assertTrue(result["metadata"]["current_stock_available"])
		self.assertTrue(result["metadata"]["replenishment"]["available"])
		self.assertFalse(result["metadata"]["movement"]["available"])
		self.assertTrue(result["metadata"]["degraded"])

	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch(
		"retailedge.inventory_health.get_inventory_replenishment",
		side_effect=frappe.ValidationError("reorder schema unavailable"),
	)
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_reorder_failure_does_not_remove_current_stock_or_movement_actions(
		self, stock, _replenishment, demand
	):
		stock.return_value = _stock_payload(
			{
				"item_code": "ITEM-2",
				"item_name": "Item Two",
				"actual_qty": 10,
				"reserved_qty": 0,
				"available_qty": 10,
				"stock_status": "Available",
			}
		)
		demand.return_value = {
			"rows": [],
			"scope": {"lookback_days": 90, "from_date": "2026-05-26", "to_date": today()},
			"scan": {},
			"metadata": {},
		}

		result = inventory_health.get_inventory_action_summary({"company": "Test Company"})
		cards = _cards(result)

		self.assertEqual(cards["Available Items"], 1)
		self.assertEqual(cards["Non-moving"], 1)
		self.assertEqual(cards["Items Requiring Reorder"], 0)
		self.assertTrue(result["metadata"]["current_stock_available"])
		self.assertFalse(result["metadata"]["replenishment"]["available"])
		self.assertTrue(result["metadata"]["movement"]["available"])
		self.assertTrue(result["metadata"]["degraded"])


if __name__ == "__main__":
	unittest.main()
