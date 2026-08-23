from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import inventory_location_exceptions as location_exceptions


class TestInventoryLocationExceptions(unittest.TestCase):
	def test_negative_location_hidden_by_positive_warehouse_is_detected(self):
		result = location_exceptions._classify_hidden_location_exceptions(
			aggregate_by_item={
				"ITEM-1": {
					"item_code": "ITEM-1",
					"actual_qty": 8,
					"available_qty": 8,
					"stock_status": "Available",
				}
			},
			location_rows=[
				{"item_code": "ITEM-1", "warehouse": "A", "actual_qty": -2, "reserved_qty": 0},
				{"item_code": "ITEM-1", "warehouse": "B", "actual_qty": 10, "reserved_qty": 0},
			],
		)

		self.assertEqual(result["summary"]["hidden_negative_location_count"], 1)
		self.assertEqual(result["hidden_negative_locations"][0]["warehouse"], "A")
		self.assertEqual(result["summary"]["hidden_fully_reserved_location_count"], 0)

	def test_fully_reserved_location_hidden_by_available_warehouse_is_detected(self):
		result = location_exceptions._classify_hidden_location_exceptions(
			aggregate_by_item={
				"ITEM-1": {
					"item_code": "ITEM-1",
					"actual_qty": 15,
					"available_qty": 5,
					"stock_status": "Available",
				}
			},
			location_rows=[
				{"item_code": "ITEM-1", "warehouse": "A", "actual_qty": 5, "reserved_qty": 5},
				{"item_code": "ITEM-1", "warehouse": "B", "actual_qty": 10, "reserved_qty": 0},
			],
		)

		self.assertEqual(result["summary"]["hidden_fully_reserved_location_count"], 1)
		self.assertEqual(result["hidden_fully_reserved_locations"][0]["warehouse"], "A")
		self.assertEqual(result["summary"]["hidden_negative_location_count"], 0)

	def test_location_exception_is_not_duplicated_when_aggregate_has_same_status(self):
		negative = location_exceptions._classify_hidden_location_exceptions(
			aggregate_by_item={"ITEM-1": {"item_code": "ITEM-1", "stock_status": "Negative"}},
			location_rows=[
				{"item_code": "ITEM-1", "warehouse": "A", "actual_qty": -2, "reserved_qty": 0}
			],
		)
		reserved = location_exceptions._classify_hidden_location_exceptions(
			aggregate_by_item={"ITEM-2": {"item_code": "ITEM-2", "stock_status": "Fully Reserved"}},
			location_rows=[
				{"item_code": "ITEM-2", "warehouse": "B", "actual_qty": 5, "reserved_qty": 5}
			],
		)

		self.assertEqual(negative["summary"]["hidden_negative_location_count"], 0)
		self.assertEqual(reserved["summary"]["hidden_fully_reserved_location_count"], 0)

	def test_zero_bin_row_is_not_inferred_as_a_location_stockout(self):
		result = location_exceptions._classify_hidden_location_exceptions(
			aggregate_by_item={"ITEM-1": {"item_code": "ITEM-1", "stock_status": "Available"}},
			location_rows=[
				{"item_code": "ITEM-1", "warehouse": "OLD", "actual_qty": 0, "reserved_qty": 0}
			],
		)

		self.assertEqual(result["hidden_negative_locations"], [])
		self.assertEqual(result["hidden_fully_reserved_locations"], [])

	@patch("retailedge.inventory_location_exceptions._resolve_warehouse_scope", return_value=["A", "B"])
	@patch("retailedge.inventory_location_exceptions._assert_report_access")
	@patch("retailedge.inventory_location_exceptions._validate_filters")
	@patch("retailedge.inventory_location_exceptions.frappe.get_list")
	def test_service_reads_only_permitted_items_warehouses_and_non_cost_bin_fields(
		self, get_list, _validate, _access, _warehouses
	):
		get_list.return_value = [
			frappe._dict(item_code="ITEM-1", warehouse="A", actual_qty=-1, reserved_qty=0)
		]

		result = location_exceptions.get_hidden_inventory_location_exceptions(
			{"company": "Test Company"},
			aggregate_rows=[
				{"item_code": "ITEM-1", "actual_qty": 5, "available_qty": 5, "stock_status": "Available"}
			],
		)

		self.assertEqual(result["summary"]["hidden_negative_location_count"], 1)
		_, kwargs = get_list.call_args
		self.assertEqual(kwargs["filters"]["item_code"], ["in", ["ITEM-1"]])
		self.assertEqual(kwargs["filters"]["warehouse"], ["in", ["A", "B"]])
		self.assertEqual(kwargs["fields"], ["item_code", "warehouse", "actual_qty", "reserved_qty"])
		self.assertNotIn("valuation_rate", kwargs["fields"])
		self.assertNotIn("stock_value", kwargs["fields"])
		self.assertFalse(result["metadata"]["zero_bin_stockout_inference"])

	def test_source_is_bounded_read_only_and_reuses_stock_position_scope(self):
		text = Path(location_exceptions.__file__).read_text(encoding="utf-8")
		self.assertIn("_resolve_warehouse_scope", text)
		self.assertIn("_assert_report_access", text)
		self.assertIn("MAX_BIN_SCAN_ROWS + 1", text)
		self.assertIn('fields=["item_code", "warehouse", "actual_qty", "reserved_qty"]', text)
		self.assertNotIn("valuation_rate", text)
		self.assertNotIn("stock_value", text)
		self.assertNotIn("frappe.get_all", text)
		self.assertNotIn("ignore_permissions=True", text)
		self.assertNotIn("frappe.db.commit", text)
		self.assertNotIn(".submit(", text)
		self.assertNotIn(".insert(", text)


if __name__ == "__main__":
	unittest.main()
