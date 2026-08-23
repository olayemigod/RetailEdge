import unittest
from unittest.mock import patch

import frappe

from retailedge import inventory_insight_views


class TestInventoryInsightViews(unittest.TestCase):
	def test_invalid_inventory_insight_view_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			inventory_insight_views.get_inventory_insight_view(
				"unknown", {"company": "Test Company"}
			)

	@patch("retailedge.inventory_insight_views.get_inventory_ageing")
	def test_ageing_view_preserves_service_columns_and_paginates(self, ageing):
		ageing.return_value = {
			"columns": [{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"}],
			"rows": [{"item_code": "A"}, {"item_code": "B"}],
			"summary": [{"label": "Items with Aged Stock", "value": 1, "datatype": "Int"}],
			"scope": {"company": "Test Company"},
			"scan": {"sle_rows": 20},
			"metadata": {"ageing_truth": "ERPNext v16 Stock Ageing FIFOSlots"},
			"show_costs": 1,
		}
		result = inventory_insight_views.get_inventory_insight_view(
			"ageing", {"company": "Test Company"}, page=1, page_size=25
		)
		self.assertEqual(result["columns"][0]["fieldname"], "item_code")
		self.assertEqual(result["pagination"]["total_rows"], 2)
		self.assertTrue(result["metadata"]["lazy_loaded"])
		self.assertEqual(result["metadata"]["ageing_truth"], "ERPNext v16 Stock Ageing FIFOSlots")
		self.assertEqual(result["show_costs"], 1)
		ageing.assert_called_once()

	@patch("retailedge.inventory_insight_views.get_inventory_transfer_opportunities")
	def test_transfer_view_adds_standard_columns_without_changing_rows(self, transfers):
		transfers.return_value = {
			"rows": [
				{
					"item_code": "ITEM-1",
					"source_warehouse": "A - TC",
					"target_warehouse": "B - TC",
					"suggested_transfer_qty": 5,
				}
			],
			"summary": [{"label": "Transfer Opportunities", "value": 1, "datatype": "Int"}],
			"metadata": {"read_only": True, "creates_stock_entry": False},
		}
		result = inventory_insight_views.get_inventory_insight_view(
			"transfer-opportunities", {"company": "Test Company"}
		)
		self.assertEqual(result["rows"][0]["suggested_transfer_qty"], 5)
		self.assertGreaterEqual(
			{column["fieldname"] for column in result["columns"]},
			{"source_warehouse", "target_warehouse", "suggested_transfer_qty"},
		)
		self.assertFalse(result["metadata"]["creates_stock_entry"])

	@patch("retailedge.inventory_insight_views.get_inventory_transfer_opportunities")
	def test_sort_is_applied_before_pagination_and_validated_against_columns(self, transfers):
		transfers.return_value = {
			"rows": [
				{"item_code": "B", "suggested_transfer_qty": 2},
				{"item_code": "A", "suggested_transfer_qty": 10},
				{"item_code": "C", "suggested_transfer_qty": 5},
			],
			"summary": [],
			"metadata": {},
		}
		result = inventory_insight_views.get_inventory_insight_view(
			"transfer-opportunities",
			{"company": "Test Company"},
			page=1,
			page_size=25,
			sort_field="suggested_transfer_qty",
			sort_direction="desc",
		)
		self.assertEqual([row["item_code"] for row in result["rows"]], ["A", "C", "B"])
		self.assertEqual(result["metadata"]["sort"]["field"], "suggested_transfer_qty")
		self.assertEqual(result["metadata"]["sort"]["direction"], "desc")

		with self.assertRaises(frappe.ValidationError):
			inventory_insight_views.get_inventory_insight_view(
				"transfer-opportunities",
				{"company": "Test Company"},
				sort_field="not_a_column",
				sort_direction="asc",
			)

	@patch("retailedge.inventory_insight_views.get_inventory_profitability_signals")
	def test_profitability_view_keeps_unavailable_reason_and_empty_rows(self, profitability):
		profitability.return_value = {
			"available": False,
			"rows": [],
			"summary": [],
			"scope": {"company": "Test Company"},
			"metadata": {"reason": "Cost visibility denied", "read_only": True},
		}
		result = inventory_insight_views.get_inventory_insight_view(
			"profitability", {"company": "Test Company"}
		)
		self.assertFalse(result["available"])
		self.assertEqual(result["rows"], [])
		self.assertEqual(result["metadata"]["reason"], "Cost visibility denied")
		self.assertTrue(any(column["fieldname"] == "gross_profit" for column in result["columns"]))


if __name__ == "__main__":
	unittest.main()
