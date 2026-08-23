from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import inventory_demand


class TestInventoryDemand(unittest.TestCase):
	def test_window_is_explicit_inclusive_and_bounded(self):
		filters = frappe._dict({"as_of_date": "2026-08-23", "lookback_days": 30})
		from_date, to_date, days = inventory_demand._resolve_window(filters)
		self.assertEqual(str(from_date), "2026-07-25")
		self.assertEqual(str(to_date), "2026-08-23")
		self.assertEqual(days, 30)

		for invalid in (0, -1, inventory_demand.MAX_LOOKBACK_DAYS + 1):
			with self.subTest(invalid=invalid):
				with self.assertRaises(frappe.ValidationError):
					inventory_demand._resolve_window(
						frappe._dict({"as_of_date": "2026-08-23", "lookback_days": invalid})
					)

	def test_demand_semantics_exclude_transfers_manufacture_and_adjustments(self):
		purposes = {
			"STE-ISSUE": "Material Issue",
			"STE-TRANSFER": "Material Transfer",
			"STE-MFG": "Material Transfer for Manufacture",
			"STE-REPACK": "Repack",
		}
		cases = (
			({"actual_qty": -5, "voucher_type": "Sales Invoice", "voucher_no": "SINV-1"}, True),
			({"actual_qty": -5, "voucher_type": "Delivery Note", "voucher_no": "DN-1"}, True),
			({"actual_qty": -5, "voucher_type": "Stock Entry", "voucher_no": "STE-ISSUE"}, True),
			({"actual_qty": -5, "voucher_type": "Stock Entry", "voucher_no": "STE-TRANSFER"}, False),
			({"actual_qty": -5, "voucher_type": "Stock Entry", "voucher_no": "STE-MFG"}, False),
			({"actual_qty": -5, "voucher_type": "Stock Entry", "voucher_no": "STE-REPACK"}, False),
			({"actual_qty": -5, "voucher_type": "Stock Reconciliation", "voucher_no": "REC-1"}, False),
			({"actual_qty": -5, "voucher_type": "Purchase Receipt", "voucher_no": "PREC-RET"}, False),
			({"actual_qty": 5, "voucher_type": "Sales Invoice", "voucher_no": "SINV-RET"}, False),
		)
		for raw, expected in cases:
			with self.subTest(raw=raw):
				self.assertEqual(
					inventory_demand._is_demand_row(
						frappe._dict(raw), stock_entry_purposes=purposes
					),
					expected,
				)

	def test_aggregation_returns_item_and_location_demand_without_double_counting(self):
		rows = [
			frappe._dict(
				item_code="ITEM-1",
				warehouse="Lagos - TC",
				actual_qty=-6,
				posting_date="2026-08-20",
			),
			frappe._dict(
				item_code="ITEM-1",
				warehouse="Abuja - TC",
				actual_qty=-4,
				posting_date="2026-08-22",
			),
			frappe._dict(
				item_code="ITEM-2",
				warehouse="Lagos - TC",
				actual_qty=-3,
				posting_date="2026-08-01",
			),
		]
		item_map = {
			"ITEM-1": frappe._dict(item_name="Item One", item_group="Products", stock_uom="Nos"),
			"ITEM-2": frappe._dict(item_name="Item Two", item_group="Products", stock_uom="Nos"),
		}
		locations, items = inventory_demand._aggregate_demand(
			rows,
			item_map=item_map,
			to_date=frappe.utils.getdate("2026-08-23"),
			lookback_days=10,
		)

		self.assertEqual(len(locations), 3)
		by_item = {row["item_code"]: row for row in items}
		self.assertEqual(by_item["ITEM-1"]["demand_qty"], 10)
		self.assertEqual(by_item["ITEM-1"]["movement_count"], 2)
		self.assertEqual(by_item["ITEM-1"]["last_demand_on"], "2026-08-22")
		self.assertEqual(by_item["ITEM-1"]["days_since_demand"], 1)
		self.assertEqual(by_item["ITEM-1"]["average_daily_demand"], 1)

	def test_stock_entry_purpose_lookup_is_permission_aware(self):
		rows = [frappe._dict(voucher_type="Stock Entry", voucher_no="STE-1")]
		with patch("retailedge.inventory_demand.frappe.has_permission", return_value=False):
			with patch("retailedge.inventory_demand.frappe.get_list") as get_list:
				self.assertEqual(inventory_demand._get_stock_entry_purposes(rows), {})
				get_list.assert_not_called()

	@patch("retailedge.inventory_demand._get_item_metadata")
	@patch("retailedge.inventory_demand._resolve_item_scope", return_value=None)
	@patch("retailedge.inventory_demand._resolve_warehouse_scope", return_value=["Lagos - TC"])
	@patch("retailedge.inventory_demand._assert_sle_read_permission")
	@patch("retailedge.inventory_demand._assert_report_access")
	@patch("retailedge.inventory_demand.frappe.get_list")
	def test_service_uses_bounded_permission_aware_sle_query(
		self,
		get_list,
		_assert_report_access,
		_assert_sle,
		_resolve_warehouses,
		_resolve_items,
		get_items,
	):
		get_list.return_value = [
			frappe._dict(
				name="SLE-1",
				posting_date="2026-08-20",
				item_code="ITEM-1",
				warehouse="Lagos - TC",
				actual_qty=-5,
				voucher_type="Sales Invoice",
				voucher_no="SINV-1",
			)
		]
		get_items.return_value = {
			"ITEM-1": frappe._dict(item_name="Item One", item_group="Products", stock_uom="Nos")
		}
		result = inventory_demand.get_historical_inventory_demand(
			{
				"company": "Test Company",
				"branch": "Lagos",
				"as_of_date": "2026-08-23",
				"lookback_days": 30,
			}
		)

		self.assertEqual(result["rows"][0]["demand_qty"], 5)
		self.assertFalse(result["metadata"]["forecast"])
		self.assertEqual(result["scan"]["sle_limit"], inventory_demand.MAX_SLE_SCAN_ROWS)
		query = get_list.call_args
		self.assertEqual(query.args[0], "Stock Ledger Entry")
		self.assertEqual(query.kwargs["filters"]["warehouse"], ["in", ["Lagos - TC"]])
		self.assertEqual(query.kwargs["filters"]["actual_qty"], ["<", 0])
		self.assertEqual(query.kwargs["limit"], inventory_demand.MAX_SLE_SCAN_ROWS + 1)
		_assert_report_access.assert_called_once()
		_assert_sle.assert_called_once()
		_resolve_warehouses.assert_called_once()
		_resolve_items.assert_called_once()

	def test_scan_overflow_fails_instead_of_silently_truncating(self):
		rows = [frappe._dict(name=f"SLE-{index}") for index in range(inventory_demand.MAX_SLE_SCAN_ROWS + 1)]
		with (
			patch("retailedge.inventory_demand._assert_report_access"),
			patch("retailedge.inventory_demand._assert_sle_read_permission"),
			patch("retailedge.inventory_demand._resolve_warehouse_scope", return_value=["Stores - TC"]),
			patch("retailedge.inventory_demand._resolve_item_scope", return_value=None),
			patch("retailedge.inventory_demand.frappe.get_list", return_value=rows),
		):
			with self.assertRaises(frappe.ValidationError):
				inventory_demand.get_historical_inventory_demand(
					{"company": "Test Company", "as_of_date": "2026-08-23", "lookback_days": 30}
				)

	def test_source_has_no_unbounded_or_permission_bypassing_query_path(self):
		source = Path(inventory_demand.__file__).read_text(encoding="utf-8")
		for forbidden in (
			"frappe.get_all(",
			"frappe.db.sql(",
			"ignore_permissions=True",
			"limit_page_length=0",
			"frappe.db.commit(",
			".submit(",
		):
			self.assertNotIn(forbidden, source)
		self.assertIn("MAX_SLE_SCAN_ROWS = 20000", source)
		self.assertIn('frappe.get_list(\n\t\t"Stock Ledger Entry"', source)
		self.assertIn("_resolve_warehouse_scope", source)
		self.assertIn("_resolve_item_scope", source)
		self.assertIn('DEMAND_STOCK_ENTRY_PURPOSES = {"Material Issue"}', source)

	def test_public_service_does_not_expose_cost_or_valuation_fields(self):
		source = inspect.getsource(inventory_demand.get_historical_inventory_demand)
		for forbidden in ("valuation_rate", "stock_value", "incoming_rate"):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
