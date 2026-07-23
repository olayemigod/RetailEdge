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

	def test_running_balance_uses_opening_minus_out_plus_in(self):
		rows = [
			report.make_output_row(
				item_code="ITEM-001",
				movement_type="Purchase Receipt",
				in_quantity=20,
				out_quantity=None,
				balance=None,
				compare_uom="Carton",
				conversion_factor=10,
			),
			report.make_output_row(
				item_code="ITEM-001",
				movement_type="Internal Transfer",
				in_quantity=10,
				out_quantity=10,
				balance=None,
				compare_uom="Carton",
				conversion_factor=10,
			),
			report.make_output_row(
				item_code="ITEM-001",
				movement_type="Sale",
				in_quantity=None,
				out_quantity=5,
				balance=None,
				compare_uom="Carton",
				conversion_factor=10,
			),
		]

		result = report.apply_running_balances(rows, opening_balance=100)

		self.assertEqual(result[0]["balance"], 120)
		self.assertEqual(result[1]["balance"], 120)
		self.assertEqual(result[2]["balance"], 115)
		self.assertEqual(result[1]["compare_balance"], 12)
		self.assertEqual(result[2]["compare_balance"], 11.5)

	def test_internal_transfer_is_one_row_with_in_and_out(self):
		group_rows = [
			frappe._dict(
				{
					"name": "SLE-OUT",
					"creation": "2026-07-23 09:59:59",
					"posting_datetime": "2026-07-23 10:00:00",
					"item_code": "ITEM-001",
					"warehouse": "Main Store",
					"actual_qty": -24,
					"voucher_type": "Stock Entry",
					"voucher_no": "MAT-STE-0001",
					"voucher_detail_no": "DETAIL-1",
					"stock_uom": "Nos",
				}
			),
			frappe._dict(
				{
					"name": "SLE-IN",
					"creation": "2026-07-23 10:00:01",
					"posting_datetime": "2026-07-23 10:00:00",
					"item_code": "ITEM-001",
					"warehouse": "Branch Store",
					"actual_qty": 24,
					"voucher_type": "Stock Entry",
					"voucher_no": "MAT-STE-0001",
					"voucher_detail_no": "DETAIL-1",
					"stock_uom": "Nos",
				}
			),
		]
		row = report.build_stock_entry_movement_row(
			group_rows,
			detail_map={
				"DETAIL-1": frappe._dict(
					{
						"item_name": "Sample Item",
						"s_warehouse": "Main Store",
						"t_warehouse": "Branch Store",
						"stock_uom": "Nos",
					}
				)
			},
			header_map={"MAT-STE-0001": frappe._dict({"purpose": "Material Transfer"})},
			item=frappe._dict({"item_name": "Sample Item", "stock_uom": "Nos"}),
			conversion_map={("ITEM-001", "Carton"): 12},
			compare_uom="Carton",
		)

		self.assertEqual(row["movement_type"], "Internal Transfer")
		self.assertEqual(row["in_quantity"], 24)
		self.assertEqual(row["out_quantity"], 24)
		self.assertEqual(row["compare_in_quantity"], 2)
		self.assertEqual(row["compare_out_quantity"], 2)

	def test_display_filters_do_not_recalculate_running_balance(self):
		rows = report.apply_running_balances(
			[
				report.make_output_row(
					movement_type="Purchase Receipt",
					voucher_type="Purchase Receipt",
					voucher_no="PREC-1",
					in_quantity=20,
					out_quantity=None,
					balance=None,
					compare_uom=None,
					conversion_factor=None,
				),
				report.make_output_row(
					movement_type="Sale",
					voucher_type="Sales Invoice",
					voucher_no="SINV-1",
					in_quantity=None,
					out_quantity=5,
					balance=None,
					compare_uom=None,
					conversion_factor=None,
				),
			],
			opening_balance=100,
		)
		filtered = report.apply_display_filters(
			rows,
			frappe._dict({"movement_type": "Sale"}),
		)
		self.assertEqual(len(filtered), 1)
		self.assertEqual(filtered[0]["balance"], 115)

	def test_zero_and_negative_running_balances_are_preserved(self):
		zero = report.apply_running_balances(
			[
				report.make_output_row(
					in_quantity=None,
					out_quantity=5,
					balance=None,
					compare_uom=None,
					conversion_factor=None,
				)
			],
			opening_balance=5,
		)
		negative = report.apply_running_balances(
			[
				report.make_output_row(
					in_quantity=None,
					out_quantity=10,
					balance=None,
					compare_uom=None,
					conversion_factor=None,
				)
			],
			opening_balance=5,
		)
		self.assertEqual(zero[0]["balance"], 0)
		self.assertEqual(negative[0]["balance"], -5)

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

	def test_sales_card_comes_after_distinct_warehouses(self):
		summary = report.get_report_summary(
			[
				{
					"movement_type": "Sale",
					"voucher_type": "Sales Invoice",
					"voucher_no": "SINV-1",
					"item_code": "ITEM-001",
					"source_warehouse": "Main Store",
				},
				{
					"movement_type": "Sale",
					"voucher_type": "Sales Invoice",
					"voucher_no": "SINV-1",
					"item_code": "ITEM-001",
					"source_warehouse": "Main Store",
				},
			]
		)
		labels = [card["label"] for card in summary]
		self.assertEqual(labels[:4], ["Movement Rows", "Distinct Items", "Distinct Warehouses", "Sales"])
		self.assertEqual(summary[3]["value"], 1)

	def test_item_filter_is_required_and_item_group_is_removed(self):
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
		item_block = content.split('fieldname: "item_code"', 1)[1].split("},", 1)[0]
		self.assertIn("reqd: 1", item_block)
		self.assertNotIn('fieldname: "item_group"', content)

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
		for fieldname in ("in_quantity", "compare_in_quantity", "balance", "compare_balance"):
			self.assertNotIsInstance(row[fieldname], str)

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
