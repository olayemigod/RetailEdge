from __future__ import annotations

import unittest

import frappe

from retailedge.sales_team_allocation import (
	UNALLOCATED_SALESPERSON,
	UNASSIGNED_SALESPERSON,
	resolve_sales_team_allocations,
)
from retailedge.salesperson_performance import allocate_salesperson_invoice_rows, _salesperson_summary


class TestSalesTeamAllocation(unittest.TestCase):
	def test_positive_allocations_preserve_residual_as_unallocated(self):
		rows = [
			frappe._dict(sales_person="Ada", allocated_percentage=60),
			frappe._dict(sales_person="Bola", allocated_percentage=20),
		]
		allocations = resolve_sales_team_allocations(rows, invoice="SINV-1")
		self.assertEqual(allocations[0], ("Ada", 0.6))
		self.assertEqual(allocations[1], ("Bola", 0.2))
		self.assertEqual(allocations[2][0], UNALLOCATED_SALESPERSON)
		self.assertAlmostEqual(allocations[2][1], 0.2)
		self.assertAlmostEqual(sum(weight for _name, weight in allocations), 1.0)

	def test_all_zero_or_missing_allocations_split_evenly(self):
		rows = [
			frappe._dict(sales_person="Ada", allocated_percentage=0),
			frappe._dict(sales_person="Bola", allocated_percentage=None),
		]
		allocations = resolve_sales_team_allocations(rows, invoice="SINV-2")
		self.assertEqual(allocations, [("Ada", 0.5), ("Bola", 0.5)])

	def test_no_sales_team_is_explicitly_unassigned(self):
		self.assertEqual(resolve_sales_team_allocations([], invoice="SINV-3"), [(UNASSIGNED_SALESPERSON, 1.0)])

	def test_allocations_above_one_hundred_are_rejected(self):
		rows = [
			frappe._dict(sales_person="Ada", allocated_percentage=70),
			frappe._dict(sales_person="Bola", allocated_percentage=40),
		]
		with self.assertRaises(frappe.ValidationError):
			resolve_sales_team_allocations(rows, invoice="SINV-4")

	def test_salesperson_rows_allocate_invoice_amounts_without_double_counting(self):
		invoices = [
			frappe._dict(
				name="SINV-5",
				posting_date="2026-08-20",
				customer="CUST-1",
				grand_total=1000,
				discount_amount=100,
				net_total=900,
				outstanding_amount=300,
				status="Partly Paid",
			)
		]
		rows = allocate_salesperson_invoice_rows(
			invoices,
			allocations={"SINV-5": [("Ada", 0.5), ("Bola", 0.5)]},
			item_context={"SINV-5": {"items": "ITEM-1", "total_qty": 4}},
		)
		self.assertEqual(len(rows), 2)
		self.assertEqual(sum(row["gross_amount"] for row in rows), 1000)
		self.assertEqual(sum(row["net_amount"] for row in rows), 900)
		self.assertEqual(sum(row["discount"] for row in rows), 100)
		self.assertEqual(sum(row["outstanding_amount"] for row in rows), 300)
		self.assertEqual(sum(row["total_qty"] for row in rows), 4)

	def test_salesperson_filter_uses_resolved_allocation_rows(self):
		invoice = frappe._dict(
			name="SINV-6",
			posting_date="2026-08-21",
			customer="CUST-2",
			grand_total=1200,
			discount_amount=0,
			net_total=1200,
			outstanding_amount=0,
			status="Paid",
		)
		rows = allocate_salesperson_invoice_rows(
			[invoice],
			allocations={"SINV-6": [("Ada", 0.25), ("Bola", 0.75)]},
			salesperson_filter="Ada",
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["salesperson"], "Ada")
		self.assertEqual(rows[0]["gross_amount"], 300)
		self.assertEqual(_salesperson_summary(rows)["total_invoices"], 1)


if __name__ == "__main__":
	unittest.main()
