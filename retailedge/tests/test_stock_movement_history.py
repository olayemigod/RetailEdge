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

	def test_quantity_display_includes_uom_name(self):
		self.assertEqual(report.format_quantity(24, "Nos"), "24 Nos")
		self.assertEqual(report.format_quantity(2.5, "Carton"), "2.5 Carton")
		self.assertEqual(report.format_quantity(None, "Nos"), "")

	def test_transfer_classification(self):
		self.assertEqual(report.classify_stock_entry_movement("Material Transfer", "Stores", "Shop"), "Internal Transfer")
		self.assertEqual(report.classify_stock_entry_movement("Material Issue", "Stores", None), "Material Issue")

	def test_sales_and_purchase_return_classification(self):
		self.assertEqual(report.classify_ledger_movement("Sales Invoice", False, {}), "Sale")
		self.assertEqual(report.classify_ledger_movement("Sales Invoice", True, {"is_return": 1}), "Sales Return")
		self.assertEqual(report.classify_ledger_movement("Purchase Receipt", True, {}), "Purchase Receipt")
		self.assertEqual(report.classify_ledger_movement("Purchase Receipt", False, {"is_return": 1}), "Purchase Return")

	def test_output_has_destination_balances_in_both_uoms(self):
		row = report.make_output_row(
			posting_datetime="2026-07-23 10:00:00",
			movement_type="Internal Transfer",
			item_code="ITEM-001",
			item_name="Sample Item",
			base_quantity=24,
			base_uom="Nos",
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
		self.assertEqual(row["base_quantity_display"], "24 Nos")
		self.assertEqual(row["compare_quantity_display"], "2 Carton")
		self.assertEqual(row["destination_balance_display"], "120 Nos")
		self.assertEqual(row["destination_balance_compare_display"], "10 Carton")

	def test_columns_exclude_removed_fields(self):
		columns = report.get_columns(frappe._dict({"compare_uom": "Carton"}))
		fieldnames = {column["fieldname"] for column in columns}
		self.assertNotIn("source_branch", fieldnames)
		self.assertNotIn("destination_branch", fieldnames)
		self.assertNotIn("party", fieldnames)
		self.assertNotIn("base_uom", fieldnames)
		self.assertNotIn("compare_uom", fieldnames)
		self.assertIn("destination_balance_display", fieldnames)
		self.assertIn("destination_balance_compare_display", fieldnames)

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
