from __future__ import annotations

import os
import unittest

import frappe

from retailedge.retailedge.report.retailedge_stock_movement_history import retailedge_stock_movement_history as report


class TestStockMovementHistory(unittest.TestCase):
	def test_quantity_conversion_uses_item_conversion_factor(self):
		self.assertEqual(report.convert_quantity(24, 12), 2)
		self.assertIsNone(report.convert_quantity(24, None))
		self.assertIsNone(report.convert_quantity(24, 0))

	def test_directional_quantities_keep_numeric_in_and_out_columns(self):
		in_quantity, out_quantity = report.split_movement_quantity(
			24,
			source_warehouse="Main Store",
			destination_warehouse="Branch Store",
		)
		self.assertEqual(in_quantity, 24)
		self.assertEqual(out_quantity, 24)

		in_quantity, out_quantity = report.split_movement_quantity(
			24,
			destination_warehouse="Branch Store",
		)
		self.assertEqual(in_quantity, 24)
		self.assertIsNone(out_quantity)

		in_quantity, out_quantity = report.split_movement_quantity(
			24,
			source_warehouse="Main Store",
		)
		self.assertIsNone(in_quantity)
		self.assertEqual(out_quantity, 24)

	def test_transfer_classification(self):
		self.assertEqual(report.classify_stock_entry_movement("Material Transfer", "Stores", "Shop"), "Internal Transfer")
		self.assertEqual(report.classify_stock_entry_movement("Material Issue", "Stores", None), "Material Issue")

	def test_sales_and_purchase_return_classification(self):
		self.assertEqual(report.classify_ledger_movement("Sales Invoice", False, {}), "Sale")
		self.assertEqual(report.classify_ledger_movement("Sales Invoice", True, {"is_return": 1}), "Sales Return")
		self.assertEqual(report.classify_ledger_movement("Purchase Receipt", True, {}), "Purchase Receipt")
		self.assertEqual(report.classify_ledger_movement("Purchase Receipt", False, {"is_return": 1}), "Purchase Return")

	def test_output_has_numeric_quantities_and_destination_balances(self):
		row = report.make_output_row(
			posting_datetime="2026-07-23 10:00:00",
			movement_type="Internal Transfer",
			item_code="ITEM-001",
			item_name="Sample Item",
			stock_uom="Nos",
			in_quantity=24,
			out_quantity=24,
			compare_uom="Carton",
			conversion_factor=12,
			source_warehouse="Main Store",
			destination_warehouse="Branch Store",
			destination_balance=120,
			voucher_type="Stock Entry",
			voucher_no="MAT-STE-0001",
			purpose="Material Transfer",
			batch_no=None,
			remarks="",
		)
		self.assertEqual(row["stock_uom"], "Nos")
		self.assertEqual(row["in_quantity"], 24)
		self.assertEqual(row["out_quantity"], 24)
		self.assertEqual(row["compare_uom"], "Carton")
		self.assertEqual(row["compare_in_quantity"], 2)
		self.assertEqual(row["compare_out_quantity"], 2)
		self.assertEqual(row["destination_balance"], 120)
		self.assertEqual(row["destination_balance_compare"], 10)
		for fieldname in (
			"in_quantity",
			"out_quantity",
			"compare_in_quantity",
			"compare_out_quantity",
			"destination_balance",
			"destination_balance_compare",
		):
			self.assertIsInstance(row[fieldname], (int, float))

	def test_columns_use_separate_uom_and_numeric_quantity_fields(self):
		columns = report.get_columns(frappe._dict({"compare_uom": "Carton"}))
		column_map = {column["fieldname"]: column for column in columns}

		self.assertNotIn("source_branch", column_map)
		self.assertNotIn("destination_branch", column_map)
		self.assertNotIn("party", column_map)
		self.assertNotIn("base_quantity_display", column_map)
		self.assertNotIn("compare_quantity_display", column_map)
		self.assertNotIn("destination_balance_display", column_map)
		self.assertNotIn("destination_balance_compare_display", column_map)

		self.assertEqual(column_map["stock_uom"]["fieldtype"], "Link")
		self.assertEqual(column_map["compare_uom"]["fieldtype"], "Link")
		for fieldname in (
			"in_quantity",
			"out_quantity",
			"compare_in_quantity",
			"compare_out_quantity",
			"destination_balance",
			"destination_balance_compare",
		):
			self.assertEqual(column_map[fieldname]["fieldtype"], "Float")

	def test_report_has_no_edgesuite_ui_dependency(self):
		app_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			app_path,
			"retailedge",
			"report",
			"retailedge_stock_movement_history",
			"retailedge_stock_movement_history.js",
		)
		with open(js_path, encoding="utf-8") as handle:
			content = handle.read()
		self.assertNotIn("edgeui.bundle.js", content)
		self.assertNotIn("window.EdgeUI", content)
		self.assertNotIn("Vue", content)
		self.assertIn('frappe.query_reports["RetailEdge Stock Movement History"]', content)

	def test_workspace_patch_is_registered(self):
		patches_path = os.path.join(frappe.get_app_path("retailedge"), "patches.txt")
		with open(patches_path, encoding="utf-8") as handle:
			content = handle.read()
		self.assertIn("retailedge.patches.add_stock_movement_history_report_link", content)
