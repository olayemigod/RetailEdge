from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.utils import today

from retailedge import inventory_health
from retailedge.inventory_intelligence import MovementThresholds


class TestInventoryHealth(unittest.TestCase):
	def test_enrichment_uses_available_stock_demand_and_replenishment(self):
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
		replenishment = {
			"configured_location_count": 2,
			"triggered_location_count": 1,
			"unavailable_rule_count": 0,
			"recommended_reorder_qty": 20,
			"replenishment_status": "Reorder Now",
		}
		result = inventory_health._enrich_stock_row(
			row,
			demand=demand,
			replenishment=replenishment,
			lookback_days=30,
			thresholds=MovementThresholds(slow_days=30, non_moving_days=90),
		)
		self.assertEqual(result["stock_cover_days"], 15)
		self.assertEqual(result["stock_cover_review"], "Within Evidence Window")
		self.assertEqual(result["observed_demand_qty"], 30)
		self.assertEqual(result["movement_class"], "Normal")
		self.assertEqual(result["replenishment_status"], "Reorder Now")
		self.assertEqual(result["reorder_triggered_locations"], 1)
		self.assertEqual(result["recommended_reorder_qty"], 20)
		self.assertEqual(result["actual_qty"], 20)
		self.assertEqual(result["projected_qty"], 18)

	def test_high_cover_review_uses_evidence_window_without_claiming_overstock(self):
		self.assertEqual(
			inventory_health._stock_cover_review(
				cover_days=31,
				daily_demand=1,
				lookback_days=30,
			),
			"High Cover Review",
		)
		self.assertEqual(
			inventory_health._stock_cover_review(
				cover_days=30,
				daily_demand=1,
				lookback_days=30,
			),
			"Within Evidence Window",
		)
		self.assertEqual(
			inventory_health._stock_cover_review(
				cover_days=None,
				daily_demand=0,
				lookback_days=30,
			),
			"No Demand Evidence",
		)

	def test_no_demand_in_short_window_is_not_falsely_non_moving(self):
		result = inventory_health._enrich_stock_row(
			{"item_code": "ITEM-1", "available_qty": 10},
			demand=None,
			replenishment=None,
			lookback_days=30,
			thresholds=MovementThresholds(slow_days=30, non_moving_days=90),
		)
		self.assertEqual(result["movement_class"], "No demand in window")
		self.assertEqual(result["replenishment_status"], "No reorder rule")
		self.assertIsNone(result["stock_cover_days"])
		self.assertEqual(result["stock_cover_review"], "No Demand Evidence")

	def test_no_demand_in_sufficient_window_can_be_non_moving(self):
		result = inventory_health._enrich_stock_row(
			{"item_code": "ITEM-1", "available_qty": 10},
			demand=None,
			replenishment=None,
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
		self.assertEqual(filters.replenishment_status, "All")
		self.assertEqual(filters.include_zero, 1)

	def test_zero_balance_demand_item_is_kept_as_out_of_stock_without_cost_leakage(self):
		rows, added = inventory_health._with_zero_balance_intelligence_rows(
			[],
			demand_by_item={
				"SOLD-OUT": {
					"item_code": "SOLD-OUT",
					"item_name": "Sold Out Item",
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			},
			replenishment_by_item={},
			show_costs=False,
			stock_status="All",
		)
		self.assertEqual(added, 1)
		self.assertEqual(rows[0]["item_code"], "SOLD-OUT")
		self.assertEqual(rows[0]["actual_qty"], 0)
		self.assertEqual(rows[0]["available_qty"], 0)
		self.assertEqual(rows[0]["stock_status"], "Out of Stock")
		self.assertNotIn("stock_value", rows[0])
		self.assertNotIn("valuation_rate", rows[0])

	def test_zero_balance_item_respects_canonical_stock_status_filter(self):
		rows, added = inventory_health._with_zero_balance_intelligence_rows(
			[],
			demand_by_item={"SOLD-OUT": {"item_code": "SOLD-OUT"}},
			replenishment_by_item={},
			show_costs=True,
			stock_status="Available",
		)
		self.assertEqual(rows, [])
		self.assertEqual(added, 0)

	@patch("retailedge.inventory_health.get_inventory_replenishment")
	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_public_service_composes_existing_stock_demand_and_replenishment_once(
		self, stock, demand, replenishment
	):
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
		replenishment.return_value = {
			"items": [
				{
					"item_code": "ITEM-1",
					"configured_location_count": 1,
					"triggered_location_count": 1,
					"unavailable_rule_count": 0,
					"recommended_reorder_qty": 20,
					"replenishment_status": "Reorder Now",
				}
			],
			"scan": {"reorder_rules": 1},
			"metadata": {"configuration_truth": "ERPNext Item.reorder_levels / Item Reorder"},
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
		replenishment.assert_called_once()
		self.assertEqual(result["rows"][0]["stock_cover_days"], 15)
		self.assertEqual(result["rows"][0]["stock_cover_review"], "Within Evidence Window")
		self.assertEqual(result["rows"][0]["replenishment_status"], "Reorder Now")
		self.assertEqual(result["rows"][0]["recommended_reorder_qty"], 20)
		self.assertEqual(result["rows"][0]["stock_value"], 3000)
		self.assertEqual(result["show_costs"], 1)
		self.assertFalse(result["metadata"]["stock_cover_is_forecast"])
		self.assertIn("not an overstock assertion", result["metadata"]["stock_cover_review_contract"])
		self.assertEqual(result["scope"]["high_cover_review_threshold_days"], 30)
		self.assertEqual(result["metadata"]["current_stock_truth"], "ERPNext Bin")
		self.assertEqual(result["pagination"]["total_rows"], 1)

	@patch("retailedge.inventory_health.get_inventory_replenishment", return_value={"items": [], "scan": {}, "metadata": {}})
	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_hidden_cost_contract_does_not_reintroduce_cost_fields(self, stock, demand, _replenishment):
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

	@patch("retailedge.inventory_health.get_inventory_replenishment")
	@patch("retailedge.inventory_health.get_historical_inventory_demand")
	@patch("retailedge.inventory_health._build_stock_position_dataset")
	def test_replenishment_filter_recalculates_summary_on_filtered_rows(self, stock, demand, replenishment):
		stock.return_value = {
			"columns": [{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"}],
			"rows": [
				{"item_code": "ITEM-1", "actual_qty": 10, "available_qty": 10, "stock_status": "Available"},
				{"item_code": "ITEM-2", "actual_qty": 5, "available_qty": 5, "stock_status": "Available"},
			],
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
		replenishment.return_value = {
			"items": [
				{"item_code": "ITEM-1", "configured_location_count": 1, "triggered_location_count": 1, "unavailable_rule_count": 0, "recommended_reorder_qty": 20, "replenishment_status": "Reorder Now"},
				{"item_code": "ITEM-2", "configured_location_count": 1, "triggered_location_count": 0, "unavailable_rule_count": 0, "recommended_reorder_qty": 0, "replenishment_status": "Healthy"},
			],
			"scan": {},
			"metadata": {},
		}
		result = inventory_health.get_inventory_health(
			{"company": "Test Company", "replenishment_status": "Reorder Now"}
		)
		self.assertEqual([row["item_code"] for row in result["rows"]], ["ITEM-1"])
		cards = {card["label"]: card["value"] for card in result["summary"]}
		self.assertEqual(cards["Items in Scope"], 1)
		self.assertEqual(cards["High Cover Review"], 0)
		self.assertEqual(cards["Items Requiring Reorder"], 1)

	def test_source_is_read_only_and_reuses_existing_stock_dataset(self):
		source = Path(inventory_health.__file__).read_text(encoding="utf-8")
		self.assertIn("_build_stock_position_dataset", source)
		self.assertIn("get_historical_inventory_demand", source)
		self.assertIn("get_inventory_replenishment", source)
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