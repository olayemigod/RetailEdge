from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge import inventory_health


class TestInventoryHealthSorting(unittest.TestCase):
	def test_numeric_sort_keeps_missing_values_last_in_both_directions(self):
		rows = [
			{"item_code": "B", "stock_cover_days": 20},
			{"item_code": "MISSING", "stock_cover_days": None},
			{"item_code": "A", "stock_cover_days": 5},
		]
		ascending = inventory_health._sort_rows(
			rows,
			{"field": "stock_cover_days", "direction": "asc", "fieldtype": "Float"},
		)
		descending = inventory_health._sort_rows(
			rows,
			{"field": "stock_cover_days", "direction": "desc", "fieldtype": "Float"},
		)

		self.assertEqual([row["item_code"] for row in ascending], ["A", "B", "MISSING"])
		self.assertEqual([row["item_code"] for row in descending], ["B", "A", "MISSING"])

	@patch("retailedge.inventory_health._build_inventory_health_dataset")
	def test_public_service_sorts_complete_dataset_before_pagination(self, build_dataset):
		build_dataset.return_value = {
			"columns": [
				{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"},
				{"fieldname": "available_qty", "label": "Available", "fieldtype": "Float"},
			],
			"rows": [
				{"item_code": "LOW", "available_qty": 1},
				{"item_code": "HIGH", "available_qty": 50},
				{"item_code": "MID", "available_qty": 10},
			],
			"summary": [],
			"metadata": {},
		}

		result = inventory_health.get_inventory_health(
			{"company": "Test Company"},
			page=1,
			page_size=25,
			sort_field="available_qty",
			sort_direction="desc",
		)

		self.assertEqual([row["item_code"] for row in result["rows"]], ["HIGH", "MID", "LOW"])
		self.assertEqual(
			result["metadata"]["sort"],
			{
				"field": "available_qty",
				"direction": "desc",
				"fieldtype": "Float",
			},
		)

	@patch("retailedge.inventory_health._build_inventory_health_dataset")
	def test_public_service_rejects_unknown_sort_field(self, build_dataset):
		build_dataset.return_value = {
			"columns": [{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"}],
			"rows": [],
			"summary": [],
			"metadata": {},
		}

		with self.assertRaises(frappe.ValidationError):
			inventory_health.get_inventory_health(
				{"company": "Test Company"},
				sort_field="not_a_column",
				sort_direction="asc",
			)


if __name__ == "__main__":
	unittest.main()
