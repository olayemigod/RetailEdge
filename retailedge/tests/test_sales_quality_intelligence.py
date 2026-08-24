from __future__ import annotations

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.sales_quality_intelligence import build_sales_quality_rows


class TestSalesQualityIntelligence(FrappeTestCase):
	def test_price_reduction_uses_recorded_reference_and_net_amount(self):
		rows = build_sales_quality_rows(
			[frappe._dict(name="SINV-1", posting_date="2026-08-24", customer="CUST-1", customer_name="Alpha", branch="Lagos")],
			invoice_details={"SINV-1": frappe._dict(base_discount_amount=10, additional_discount_percentage=5)},
			items=[frappe._dict(parent="SINV-1", item_code="A", qty=2, stock_qty=2, base_price_list_rate=100, base_rate_with_margin=0, discount_percentage=10, distributed_discount_amount=10, base_net_amount=180, incoming_rate=50)],
			team_map={"SINV-1": ["Ada"]},
			show_costs=True,
		)
		row = rows[0]
		self.assertEqual(row["reference_value"], 200)
		self.assertEqual(row["net_sales"], 180)
		self.assertEqual(row["price_reduction"], 20)
		self.assertEqual(row["effective_reduction_percent"], 10)
		self.assertEqual(row["additional_discount_amount"], 10)
		self.assertEqual(row["gross_profit"], 80)

	def test_rate_with_margin_is_preferred_as_discount_reference(self):
		rows = build_sales_quality_rows(
			[frappe._dict(name="SINV-1", customer="CUST-1")],
			invoice_details={},
			items=[frappe._dict(parent="SINV-1", qty=1, stock_qty=1, base_price_list_rate=100, base_rate_with_margin=120, discount_percentage=25, base_net_amount=90, incoming_rate=0)],
			show_costs=False,
		)
		self.assertEqual(rows[0]["reference_value"], 120)
		self.assertEqual(rows[0]["price_reduction"], 30)
		self.assertEqual(rows[0]["effective_reduction_percent"], 25)

	def test_missing_reference_is_visible_not_fabricated(self):
		rows = build_sales_quality_rows(
			[frappe._dict(name="SINV-1", customer="CUST-1")],
			invoice_details={},
			items=[frappe._dict(parent="SINV-1", qty=1, stock_qty=1, base_price_list_rate=0, base_rate_with_margin=0, discount_percentage=0, base_net_amount=100, incoming_rate=20)],
			show_costs=False,
		)
		row = rows[0]
		self.assertEqual(row["reference_value"], 0)
		self.assertEqual(row["price_reduction"], 0)
		self.assertEqual(row["missing_reference_lines"], 1)
		self.assertFalse(row["high_reduction"])

	def test_cost_restricted_rows_omit_profit_fields(self):
		rows = build_sales_quality_rows(
			[frappe._dict(name="SINV-1", customer="CUST-1")],
			invoice_details={},
			items=[frappe._dict(parent="SINV-1", qty=1, stock_qty=1, base_price_list_rate=100, base_rate_with_margin=0, base_net_amount=90, incoming_rate=80)],
			show_costs=False,
		)
		self.assertNotIn("cost_of_sales", rows[0])
		self.assertNotIn("gross_profit", rows[0])
		self.assertNotIn("gross_margin_percent", rows[0])
		self.assertNotIn("low_margin", rows[0])

	def test_low_margin_flag_uses_r8_transactional_margin_contract(self):
		rows = build_sales_quality_rows(
			[frappe._dict(name="SINV-1", customer="CUST-1")],
			invoice_details={},
			items=[frappe._dict(parent="SINV-1", qty=1, stock_qty=1, base_price_list_rate=100, base_rate_with_margin=0, base_net_amount=90, incoming_rate=85)],
			show_costs=True,
			low_margin_percent=10,
		)
		self.assertEqual(rows[0]["gross_profit"], 5)
		self.assertTrue(rows[0]["low_margin"])

	def test_high_reduction_threshold_is_explicit(self):
		rows = build_sales_quality_rows(
			[frappe._dict(name="SINV-1", customer="CUST-1")],
			invoice_details={},
			items=[frappe._dict(parent="SINV-1", qty=1, stock_qty=1, base_price_list_rate=100, base_rate_with_margin=0, base_net_amount=80, incoming_rate=0)],
			show_costs=False,
			high_reduction_percent=15,
		)
		self.assertTrue(rows[0]["high_reduction"])


if __name__ == "__main__":
	unittest.main()
