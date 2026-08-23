from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.utils import today

from retailedge import inventory_health
from retailedge.inventory_intelligence import MovementThresholds


class TestInventoryHealth(unittest.TestCase):
	def test_enrichment_uses_available_stock_and_observed_demand(self):
		row = {
			"item_code": "ITEM-1",
			"actual_qty": 20,
			"reserved_qty": 5,
			"available_qty": 15,
			"projected_qty": 18,
		}
		demand = {
			"demand_qty": 30,
			"average_daily_demand": 1,
			"last_demand_on": "2026-08-22",
			"days_since_demand": 1,
		}
		result = inventory_health._enrich_stock_row(
			row,
			demand=demand,
			lookback_days=30,
			thresholds=MovementThresholds(slow_days=30, non_moving_days=90),
		)
		self.assertEqual(result["stock_cover_days"], 15)
		self.assertEqual(result["observed_demand_qty"], 30)
		self.assertEqual(result["movement_class"], "Normal")
		self.assertEqual(result["actual_qty"], 20)
		self.assertEqual(result["projected_qty"], 18)

	def test_no_demand_in_short_window_is_not_falsely_non_moving(self):
		result = inventory_health._enrich_stock_row(
			{"item_code": "ITEM-1", "available_qty": 10},
			demand=None,
			lookback_days=30,
			thresholds=MovementThresholds(slow_days=30, non_moving_days=90),
		)
		self.assertEqual(result["movement_class"], "No demand in window")
		self.assertIsNone(result["stock_cover_days"])

	def test_no_demand_in_sufficient_window_can_be_non_moving(self):
		result = inventory_health._enrich_stock_row(
			{"item_code": "ITEM-1", "available_qty": 10},
			demand=None,
			lookback_days=90,
			thresholds=MovementThresholds(slow_days=30, non_moving_days=90),
		)
		self.assertEqual(result["movement_class"], "Non-moving")

	def test_historical_as_of_date_is_rejected_for_current_bin_view(self):
		with self.assertRaises(frappe.ValidationError):
			inventory_health._normalise_health_filters(
				{"company": "Test Company", "as_of_date": "2026-01-01"}
			)

	def test_today_as_of_date_is_allowed(self):
		filters = inventory_health._normalise_health_filters(
			{"company": "Test Company", "as_of_date": today()}
		)
		self.assertEqual(filters.as_of_date, today())
		self.assertEqual(filters.lookback_days, inventory_health.DEFAULT_LOOKBACK_DAYS)

	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_public_service_composes_existing_stock_truth_and_demand_once(self, stock, demand):
		stock.return_value = {
			"columns": [
				{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"},
				{"fieldname": "stock_value", "label": "Stock Value", "fieldtype": "Currency"},
			],
			"rows": [
				{
					"item_code": "ITEM-1",
					"actual_qty": 20,
					"reserved_qty": 5,
					"available_qty": 15,
					"projected_qty": 18,
					"stock_value": 3000,
					"stock_status": "Available",
				}
			],
			"summary": [{"label": "Stock Value", "value": 3000, "datatype": "Currency"}],
			"company_currency": "NGN",
			"show_costs": 1,
			"scope": {"company": "Test Company", "branch": "Lagos", "warehouse_count": 1},
			"scan": {"bin_rows": 1},
		}
		demand.return_value = {
			"rows": [
				{
					"item_code": "ITEM-1",
					"demand_qty": 30,
					"average_daily_demand": 1,
					"last_demand_on": today(),
					"days_since_demand": 0,
				}
			],
			"scope": {"lookback_days": 30, "from_date": "2026-07-25", "to_date": today()},
			"scan": {"demand_sle_rows": 1},
			"metadata": {"forecast": False},
		}

		result = inventory_health.get_inventory_health(
			{
				"company": "Test Company",
				"branch": "Lagos",
				"lookback_days": 30,
				"slow_days": 30,
				"non_moving_days": 90,
			},
			page=1,
			page_size=25,
		)

		stock.assert_called_once()
		demand.assert_called_once()
		self.assertEqual(result["rows"][0]["stock_cover_days"], 15)
		self.assertEqual(result["rows"][0]["stock_value"], 3000)
		self.assertEqual(result["show_costs"], 1)
		self.assertFalse(result["metadata"]["stock_cover_is_forecast"])
		self.assertEqual(result["metadata"]["current_stock_truth"], "ERPNext Bin")
		self.assertEqual(result["pagination"]["total_rows"], 1)

	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_hidden_cost_contract_does_not_reintroduce_cost_fields(self, stock, demand):
		stock.return_value = {
			"columns": [{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"}],
			"rows": [{"item_code": "ITEM-1", "actual_qty": 10, "available_qty": 10, "stock_status": "Available"}],
			"summary": [],
			"company_currency": "",
			"show_costs": 0,
			"scope": {"company": "Test Company", "warehouse_count": 1},
			"scan": {},
		}
		demand.return_value = {
			"rows": [],
			"scope": {"lookback_days": 90, "from_date": "2026-05-26", "to_date": today()},
			"scan": {},
			"metadata": {"forecast": False},
		}

		result = inventory_health.get_inventory_health({"company": "Test Company"})
		self.assertEqual(result["show_costs"], 0)
		self.assertNotIn("stock_value", result["rows"][0])
		self.assertNotIn("valuation_rate", result["rows"][0])
		self.assertNotIn("stock_value", {column["fieldname"] for column in result["columns"]})

	def test_source_is_read_only_and_reuses_existing_stock_dataset(self):
		source = Path(inventory_health.__file__).read_text(encoding="utf-8")
		self.assertIn("_build_stock_position_dataset", source)
		self.assertIn("get_historical_inventory_demand", source)
		for forbidden in (
			"frappe.db.sql(",
			"frappe.get_all(",
			"ignore_permissions=True",
			"frappe.db.commit(",
			".submit(",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
