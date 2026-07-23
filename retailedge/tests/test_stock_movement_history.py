from __future__ import annotations

import inspect
import os
import unittest
from unittest.mock import patch

import frappe

from retailedge.retailedge.report.retailedge_stock_movement_history import retailedge_stock_movement_history as report


class TestStockMovementHistory(unittest.TestCase):
	def test_quantity_conversion_uses_item_conversion_factor(self):
		self.assertEqual(report.convert_quantity(24, 12), 2)
		self.assertIsNone(report.convert_quantity(24, None))
		self.assertIsNone(report.convert_quantity(24, 0))

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
		self.assertEqual(result[1]["balance"], 115)
		self.assertEqual(result[1]["compare_balance"], 11.5)

	def test_stock_entry_transfer_uses_only_selected_warehouse_side(self):
		common = {
			"detail_map": {
				"DETAIL-1": frappe._dict(
					{
						"item_name": "Sample Item",
						"s_warehouse": "Main Store",
						"t_warehouse": "Branch Store",
						"stock_uom": "Nos",
					}
				)
			},
			"header_map": {"MAT-STE-0001": frappe._dict({"purpose": "Material Transfer"})},
			"item": frappe._dict({"item_name": "Sample Item", "stock_uom": "Nos"}),
			"conversion_map": {("ITEM-001", "Carton"): 12},
			"compare_uom": "Carton",
		}
		source_row = report.build_stock_entry_movement_row(
			[
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
				)
			],
			**common,
		)
		destination_row = report.build_stock_entry_movement_row(
			[
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
				)
			],
			**common,
		)

		self.assertEqual(source_row["movement_type"], "Internal Transfer")
		self.assertIsNone(source_row["in_quantity"])
		self.assertEqual(source_row["out_quantity"], 24)
		self.assertEqual(source_row["compare_out_quantity"], 2)
		self.assertEqual(destination_row["in_quantity"], 24)
		self.assertIsNone(destination_row["out_quantity"])
		self.assertEqual(destination_row["compare_in_quantity"], 2)

	@patch.object(report.frappe, "get_list")
	def test_opening_balance_uses_supported_sum_dict_and_exact_warehouse(self, get_list):
		get_list.return_value = [frappe._dict({"opening_balance": 42})]
		filters = frappe._dict(
			{
				"company": "Test Company",
				"item_code": "ITEM-001",
				"warehouse": "Main Store - TC",
				"from_date": "2026-07-01",
			}
		)

		self.assertEqual(report.get_opening_balance(filters), 42)
		kwargs = get_list.call_args.kwargs
		self.assertEqual(kwargs["fields"], [{"SUM": "actual_qty", "as": "opening_balance"}])
		self.assertEqual(kwargs["filters"]["warehouse"], "Main Store - TC")
		self.assertNotIn("sum(actual_qty)", str(kwargs["fields"]).lower())

	def test_zero_and_negative_running_balances_are_preserved(self):
		zero = report.apply_running_balances(
			[report.make_output_row(in_quantity=None, out_quantity=5, balance=None, compare_uom=None, conversion_factor=None)],
			opening_balance=5,
		)
		negative = report.apply_running_balances(
			[report.make_output_row(in_quantity=None, out_quantity=10, balance=None, compare_uom=None, conversion_factor=None)],
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
		self.assertEqual(columns[fieldnames.index("balance")]["label"], "Balance")

	def test_sales_card_comes_after_distinct_warehouses(self):
		summary = report.get_report_summary(
			[
				{
					"movement_type": "Sale",
					"voucher_type": "Sales Invoice",
					"voucher_no": "SINV-1",
					"item_code": "ITEM-001",
					"source_warehouse": "Main Store",
				}
			]
		)
		labels = [card["label"] for card in summary]
		self.assertEqual(labels[:4], ["Movement Rows", "Distinct Items", "Distinct Warehouses", "Sales"])
		self.assertEqual(summary[3]["value"], 1)

	def test_item_and_warehouse_filters_are_required(self):
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
		for fieldname in ("item_code", "warehouse"):
			block = content.split(f'fieldname: "{fieldname}"', 1)[1].split("},", 1)[0]
			self.assertIn("reqd: 1", block)
		self.assertNotIn('fieldname: "item_group"', content)

	def test_backend_requires_warehouse(self):
		source = inspect.getsource(report.validate_filters)
		self.assertIn('("warehouse", _("Warehouse"))', source)

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

	def test_menu_refresh_patch_is_registered(self):
		patches_path = os.path.join(frappe.get_app_path("retailedge"), "patches.txt")
		with open(patches_path, encoding="utf-8") as handle:
			content = handle.read()
		self.assertIn("retailedge.patches.ensure_stock_movement_history_menu_v2", content)

	def test_frappe_cloud_version_compatibility_is_declared(self):
		pyproject_path = os.path.join(os.path.dirname(frappe.get_app_path("retailedge")), "pyproject.toml")
		with open(pyproject_path, encoding="utf-8") as handle:
			content = handle.read()
		self.assertIn("[tool.bench.frappe-dependencies]", content)
		self.assertIn('frappe = ">=16.0.0,<17.0.0"', content)
