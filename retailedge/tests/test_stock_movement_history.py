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

	def test_transfer_classification(self):
		self.assertEqual(
			report.classify_stock_entry_movement("Material Transfer", "Stores", "Shop"),
			"Internal Transfer",
		)
		self.assertEqual(
			report.classify_stock_entry_movement("Material Issue", "Stores", None),
			"Material Issue",
		)

	def test_sales_and_purchase_return_classification(self):
		self.assertEqual(report.classify_ledger_movement("Sales Invoice", False, {}), "Sale")
		self.assertEqual(
			report.classify_ledger_movement("Sales Invoice", True, {"is_return": 1}),
			"Sales Return",
		)
		self.assertEqual(
			report.classify_ledger_movement("Purchase Receipt", True, {}),
			"Purchase Receipt",
		)
		self.assertEqual(
			report.classify_ledger_movement("Purchase Receipt", False, {"is_return": 1}),
			"Purchase Return",
		)

	def test_every_row_uses_stock_ledger_balance(self):
		common = {
			"header": frappe._dict({"purpose": "Material Transfer"}),
			"stock_entry_detail": frappe._dict(
				{
					"item_name": "Sample Item",
					"s_warehouse": "Main Store",
					"t_warehouse": "Branch Store",
				}
			),
			"item_map": {"ITEM-001": frappe._dict({"item_name": "Sample Item", "stock_uom": "Nos"})},
			"conversion_map": {("ITEM-001", "Carton"): 12},
			"compare_uom": "Carton",
		}
		out_sle = frappe._dict(
			{
				"name": "SLE-OUT",
				"creation": "2026-07-23 09:59:59",
				"posting_datetime": "2026-07-23 10:00:00",
				"item_code": "ITEM-001",
				"warehouse": "Main Store",
				"actual_qty": -24,
				"qty_after_transaction": 96,
				"voucher_type": "Stock Entry",
				"voucher_no": "MAT-STE-0001",
				"voucher_detail_no": "DETAIL-1",
				"stock_uom": "Nos",
			}
		)
		in_sle = frappe._dict(
			{
				"name": "SLE-IN",
				"creation": "2026-07-23 10:00:01",
				"posting_datetime": "2026-07-23 10:00:00",
				"item_code": "ITEM-001",
				"warehouse": "Branch Store",
				"actual_qty": 24,
				"qty_after_transaction": 48,
				"voucher_type": "Stock Entry",
				"voucher_no": "MAT-STE-0001",
				"voucher_detail_no": "DETAIL-1",
				"stock_uom": "Nos",
			}
		)

		out_row = report.build_ledger_row(out_sle, **common)
		in_row = report.build_ledger_row(in_sle, **common)

		self.assertIsNone(out_row["in_quantity"])
		self.assertEqual(out_row["out_quantity"], 24)
		self.assertEqual(out_row["balance"], 96)
		self.assertEqual(out_row["compare_balance"], 8)

		self.assertEqual(in_row["in_quantity"], 24)
		self.assertIsNone(in_row["out_quantity"])
		self.assertEqual(in_row["balance"], 48)
		self.assertEqual(in_row["compare_balance"], 4)

	def test_zero_and_negative_stock_ledger_balances_are_preserved(self):
		zero = report.make_output_row(
			stock_uom="Nos",
			in_quantity=5,
			out_quantity=None,
			balance=0,
			compare_uom="Carton",
			conversion_factor=5,
		)
		negative = report.make_output_row(
			stock_uom="Nos",
			in_quantity=None,
			out_quantity=5,
			balance=-5,
			compare_uom="Carton",
			conversion_factor=5,
		)
		self.assertEqual(zero["balance"], 0)
		self.assertEqual(zero["compare_balance"], 0)
		self.assertEqual(negative["balance"], -5)
		self.assertEqual(negative["compare_balance"], -1)

	def test_balance_column_immediately_follows_in_and_out_quantity(self):
		columns = report.get_columns(frappe._dict({"compare_uom": "Carton"}))
		fieldnames = [column["fieldname"] for column in columns]
		out_index = fieldnames.index("out_quantity")
		self.assertEqual(fieldnames[out_index - 1], "in_quantity")
		self.assertEqual(fieldnames[out_index + 1], "balance")
		balance_column = columns[fieldnames.index("balance")]
		self.assertEqual(balance_column["label"], "Balance")
		self.assertEqual(balance_column["fieldtype"], "Float")

	def test_columns_use_separate_uom_and_numeric_quantity_fields(self):
		columns = report.get_columns(frappe._dict({"compare_uom": "Carton"}))
		column_map = {column["fieldname"]: column for column in columns}

		for removed in (
			"source_branch",
			"destination_branch",
			"party",
			"base_quantity_display",
			"compare_quantity_display",
			"destination_balance",
			"destination_balance_compare",
		):
			self.assertNotIn(removed, column_map)

		self.assertEqual(column_map["stock_uom"]["fieldtype"], "Link")
		self.assertEqual(column_map["compare_uom"]["fieldtype"], "Link")
		for fieldname in (
			"in_quantity",
			"out_quantity",
			"balance",
			"compare_in_quantity",
			"compare_out_quantity",
			"compare_balance",
		):
			self.assertEqual(column_map[fieldname]["fieldtype"], "Float")

	def test_export_quantity_fields_do_not_embed_uom_text(self):
		row = report.make_output_row(
			stock_uom="Nos",
			in_quantity=36,
			out_quantity=None,
			balance=120,
			compare_uom="Carton",
			conversion_factor=12,
		)
		self.assertEqual(row["in_quantity"], 36)
		self.assertEqual(row["compare_in_quantity"], 3)
		self.assertEqual(row["balance"], 120)
		self.assertEqual(row["compare_balance"], 10)
		for fieldname in ("in_quantity", "compare_in_quantity", "balance", "compare_balance"):
			self.assertNotIsInstance(row[fieldname], str)

	def test_sales_summary_card_counts_distinct_sales_documents(self):
		summary = report.get_report_summary(
			[
				{"movement_type": "Sale", "voucher_type": "Sales Invoice", "voucher_no": "SINV-1"},
				{"movement_type": "Sale", "voucher_type": "Sales Invoice", "voucher_no": "SINV-1"},
				{"movement_type": "Sale", "voucher_type": "Delivery Note", "voucher_no": "DN-1"},
				{"movement_type": "Sales Return", "voucher_type": "Sales Invoice", "voucher_no": "SINV-R1"},
			]
		)
		self.assertEqual(summary[0]["label"], "Sales")
		self.assertEqual(summary[0]["value"], 2)

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

	def test_frappe_cloud_version_compatibility_is_declared(self):
		pyproject_path = os.path.join(os.path.dirname(frappe.get_app_path("retailedge")), "pyproject.toml")
		with open(pyproject_path, encoding="utf-8") as handle:
			content = handle.read()
		self.assertIn("[tool.bench.frappe-dependencies]", content)
		self.assertIn('frappe = ">=16.0.0,<17.0.0"', content)
