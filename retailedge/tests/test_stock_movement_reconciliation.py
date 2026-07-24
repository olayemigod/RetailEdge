from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.retailedge.report.retailedge_stock_movement_history import (
	retailedge_stock_movement_history as report,
)


class TestStockMovementReconciliation(unittest.TestCase):
	def make_reconciliation_row(self, target, *, compare_uom=None, factor=None):
		return report.make_output_row(
			voucher_type="Stock Reconciliation",
			voucher_no="MAT-RECO-0001",
			ledger_warehouse="Main Store - TC",
			reconciliation_balance=target,
			in_quantity=999,
			out_quantity=999,
			balance=None,
			compare_uom=compare_uom,
			conversion_factor=factor,
		)

	def test_reconciliation_increase_is_derived_from_target_balance(self):
		row = self.make_reconciliation_row(95, compare_uom="Carton", factor=5)

		result = report.apply_running_balances([row], opening_balance=80)[0]

		self.assertEqual(result["movement_type"], "Adjustment In")
		self.assertEqual(result["in_quantity"], 15)
		self.assertIsNone(result["out_quantity"])
		self.assertEqual(result["balance"], 95)
		self.assertEqual(result["compare_in_quantity"], 3)
		self.assertEqual(result["destination_warehouse"], "Main Store - TC")
		self.assertIsNone(result["source_warehouse"])

	def test_reconciliation_decrease_is_derived_from_target_balance(self):
		row = self.make_reconciliation_row(105)

		result = report.apply_running_balances([row], opening_balance=120)[0]

		self.assertEqual(result["movement_type"], "Adjustment Out")
		self.assertIsNone(result["in_quantity"])
		self.assertEqual(result["out_quantity"], 15)
		self.assertEqual(result["balance"], 105)
		self.assertEqual(result["source_warehouse"], "Main Store - TC")
		self.assertIsNone(result["destination_warehouse"])

	def test_zero_delta_reconciliation_remains_visible_without_fake_quantity(self):
		row = self.make_reconciliation_row(50)

		result = report.apply_running_balances([row], opening_balance=50)[0]

		self.assertEqual(result["movement_type"], "Stock Reconciliation")
		self.assertIsNone(result["in_quantity"])
		self.assertIsNone(result["out_quantity"])
		self.assertEqual(result["balance"], 50)

	def test_opening_stock_reconciliation_seeds_opening_and_is_removed(self):
		filters = frappe._dict({"from_date": "2026-07-01"})
		opening_row = frappe._dict(
			{
				"name": "SLE-OPEN",
				"posting_date": "2026-07-01",
				"posting_datetime": "2026-07-01 00:00:00",
				"creation": "2026-07-01 08:00:00",
				"voucher_type": "Stock Reconciliation",
				"voucher_no": "MAT-RECO-OPEN",
				"qty_after_transaction": 42,
			}
		)
		movement_row = frappe._dict(
			{
				"name": "SLE-SALE",
				"posting_date": "2026-07-01",
				"posting_datetime": "2026-07-01 09:00:00",
				"creation": "2026-07-01 09:00:01",
				"voucher_type": "Sales Invoice",
				"voucher_no": "SINV-1",
				"qty_after_transaction": 40,
			}
		)

		opening, remaining, context = report.split_opening_stock_reconciliations(
			filters,
			[opening_row, movement_row],
			opening_balance=10,
			reconciliation_purposes={"MAT-RECO-OPEN": "Opening Stock"},
		)

		self.assertEqual(opening, 42)
		self.assertEqual([row.name for row in remaining], ["SLE-SALE"])
		self.assertEqual(context.voucher_no, "MAT-RECO-OPEN")

	def test_normal_reconciliation_on_from_date_is_not_promoted(self):
		filters = frappe._dict({"from_date": "2026-07-01"})
		row = frappe._dict(
			{
				"name": "SLE-RECO",
				"posting_date": "2026-07-01",
				"posting_datetime": "2026-07-01 10:00:00",
				"creation": "2026-07-01 10:00:01",
				"voucher_type": "Stock Reconciliation",
				"voucher_no": "MAT-RECO-1",
				"qty_after_transaction": 30,
			}
		)

		opening, remaining, context = report.split_opening_stock_reconciliations(
			filters,
			[row],
			opening_balance=25,
			reconciliation_purposes={"MAT-RECO-1": "Stock Reconciliation"},
		)

		self.assertEqual(opening, 25)
		self.assertEqual(remaining, [row])
		self.assertIsNone(context)

	@patch.object(report.frappe, "get_list")
	def test_zero_quantity_reconciliation_is_retained(self, get_list):
		get_list.return_value = [
			frappe._dict({"name": "ZERO-NORMAL", "actual_qty": 0, "voucher_type": "Sales Invoice"}),
			frappe._dict({"name": "ZERO-RECO", "actual_qty": 0, "voucher_type": "Stock Reconciliation"}),
			frappe._dict({"name": "MOVE", "actual_qty": 5, "voucher_type": "Purchase Receipt"}),
		]
		filters = frappe._dict(
			{
				"company": "Test Company",
				"item_code": "ITEM-001",
				"warehouse": "Main Store - TC",
				"from_date": "2026-07-01",
				"to_date": "2026-07-31",
			}
		)

		rows = report.get_stock_ledger_rows(filters)

		self.assertEqual([row.name for row in rows], ["ZERO-RECO", "MOVE"])
		self.assertNotIn("actual_qty", get_list.call_args.kwargs["filters"])

	def test_display_filter_does_not_recalculate_reconciliation_balance(self):
		rows = report.apply_running_balances(
			[
				report.make_output_row(
					voucher_type="Purchase Receipt",
					movement_type="Purchase Receipt",
					in_quantity=20,
					out_quantity=None,
					balance=None,
					compare_uom=None,
					conversion_factor=None,
				),
				self.make_reconciliation_row(90),
			],
			opening_balance=100,
		)

		filtered = report.apply_display_filters(
			rows,
			frappe._dict({"voucher_type": "Stock Reconciliation"}),
		)

		self.assertEqual(len(filtered), 1)
		self.assertEqual(filtered[0]["out_quantity"], 30)
		self.assertEqual(filtered[0]["balance"], 90)
