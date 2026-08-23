import unittest
from pathlib import Path

import frappe
from frappe.utils import add_days, getdate

from retailedge import inventory_ageing


class TestInventoryAgeing(unittest.TestCase):
	def test_age_ranges_are_explicit_ordered_and_bounded(self):
		self.assertEqual(inventory_ageing._normalise_age_ranges(None), (30, 60, 90, 180))
		self.assertEqual(inventory_ageing._normalise_age_ranges("15,45,120"), (15, 45, 120))

		for invalid in ([30, 30], [90, 30], [0, 30], [30, 4000]):
			with self.subTest(invalid=invalid):
				with self.assertRaises(frappe.ValidationError):
					inventory_ageing._normalise_age_ranges(invalid)

	def test_cost_hidden_sle_query_does_not_request_valuation_fields(self):
		hidden = inventory_ageing._sle_fields(show_costs=False)
		visible = inventory_ageing._sle_fields(show_costs=True)

		self.assertNotIn("stock_value_difference", hidden)
		self.assertNotIn("valuation_rate", hidden)
		self.assertIn("stock_value_difference", visible)
		self.assertIn("valuation_rate", visible)

	def test_fifo_row_preserves_erpnext_age_buckets_and_aged_threshold(self):
		as_of = getdate("2026-08-23")
		fifo_queue = [
			[5.0, add_days(as_of, -120), 500.0],
			[3.0, add_days(as_of, -10), 300.0],
		]

		row = inventory_ageing._format_fifo_row(
			item_code="ITEM-1",
			item_name="Item One",
			item_group="Products",
			stock_uom="Nos",
			warehouse="",
			total_qty=8,
			fifo_queue=fifo_queue,
			as_of_date=as_of,
			age_ranges=(30, 90, 180),
			aged_threshold_days=90,
			show_costs=True,
		)

		self.assertEqual(row["stock_qty"], 8)
		self.assertEqual(row["average_age_days"], 78.75)
		self.assertEqual(row["oldest_stock_age_days"], 120)
		self.assertEqual(row["youngest_stock_age_days"], 10)
		self.assertEqual(row["age_0_30_qty"], 3)
		self.assertEqual(row["age_91_180_qty"], 5)
		self.assertEqual(row["aged_qty"], 5)
		self.assertEqual(row["aged_stock_value"], 500)
		self.assertEqual(row["ageing_status"], "Mixed")

	def test_cost_hidden_fifo_output_contains_no_value_fields(self):
		as_of = getdate("2026-08-23")
		row = inventory_ageing._format_fifo_row(
			item_code="ITEM-1",
			item_name="Item One",
			item_group="Products",
			stock_uom="Nos",
			warehouse="Main - TC",
			total_qty=4,
			fifo_queue=[[4.0, add_days(as_of, -100), 999999.0]],
			as_of_date=as_of,
			age_ranges=(30, 90),
			aged_threshold_days=90,
			show_costs=False,
		)

		self.assertEqual(row["aged_qty"], 4)
		self.assertEqual(row["ageing_status"], "Aged")
		self.assertNotIn("stock_value", row)
		self.assertNotIn("aged_stock_value", row)
		self.assertFalse(any(key.endswith("_value") for key in row))

	def test_ageing_summary_uses_quantity_weighting_and_gates_value_card(self):
		rows = [
			{"stock_qty": 10, "average_age_days": 20, "aged_qty": 0, "aged_stock_value": 0},
			{"stock_qty": 30, "average_age_days": 60, "aged_qty": 5, "aged_stock_value": 2500},
		]

		hidden = {
			card["label"]: card["value"]
			for card in inventory_ageing._summary(rows, show_costs=False)
		}
		visible = {
			card["label"]: card["value"]
			for card in inventory_ageing._summary(rows, show_costs=True)
		}

		self.assertEqual(hidden["Weighted Average Stock Age"], 50)
		self.assertEqual(hidden["Items with Aged Stock"], 1)
		self.assertEqual(hidden["Aged Stock Quantity"], 5)
		self.assertNotIn("Aged Stock Value", hidden)
		self.assertEqual(visible["Aged Stock Value"], 2500)

	def test_ageing_source_is_read_only_bounded_and_reuses_erpnext_fifo(self):
		text = Path(inventory_ageing.__file__).read_text(encoding="utf-8")

		self.assertIn("FIFOSlots", text)
		self.assertIn("MAX_AGEING_SLE_ROWS", text)
		self.assertIn("MAX_BUNDLE_ENTRY_ROWS", text)
		self.assertIn("_resolve_warehouse_scope", text)
		self.assertIn("_resolve_item_scope", text)
		self.assertIn("should_hide_cost_price", text)
		self.assertIn('"Serial and Batch Entry"', text)
		self.assertNotIn("frappe.get_all", text)
		self.assertNotIn("ignore_permissions=True", text)
		self.assertNotIn("frappe.db.commit", text)
		self.assertNotIn("frappe.new_doc", text)
		self.assertNotIn(".submit(", text)


if __name__ == "__main__":
	unittest.main()
