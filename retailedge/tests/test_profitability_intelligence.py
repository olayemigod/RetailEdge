from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.profitability_intelligence import (
	DEFAULT_LOW_MARGIN_PERCENT,
	_aggregate_items,
	_assert_cost_visibility,
	_totals,
)


class TestProfitabilityIntelligence(FrappeTestCase):
	def test_aggregate_uses_recorded_incoming_rate_and_net_sales(self):
		rows = _aggregate_items(
			[
				frappe._dict(
					parent="SINV-0001",
					item_code="ITEM-A",
					item_name="Item A",
					item_group="Products",
					stock_qty=2,
					base_net_amount=200,
					incoming_rate=60,
				),
				frappe._dict(
					parent="SINV-0002",
					item_code="ITEM-A",
					item_name="Item A",
					item_group="Products",
					stock_qty=1,
					base_net_amount=120,
					incoming_rate=70,
				),
			]
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["net_sales"], 320)
		self.assertEqual(rows[0]["cost_of_sales"], 190)
		self.assertEqual(rows[0]["gross_profit"], 130)
		self.assertAlmostEqual(rows[0]["gross_margin_percent"], 40.625)
		self.assertEqual(rows[0]["invoice_count"], 2)

	def test_returns_reverse_revenue_and_cost_without_double_counting(self):
		rows = _aggregate_items(
			[
				frappe._dict(parent="SINV-1", item_code="ITEM-A", stock_qty=2, base_net_amount=200, incoming_rate=60),
				frappe._dict(parent="SINV-RET-1", item_code="ITEM-A", stock_qty=-1, base_net_amount=-100, incoming_rate=60),
			]
		)
		self.assertEqual(rows[0]["net_qty"], 1)
		self.assertEqual(rows[0]["net_sales"], 100)
		self.assertEqual(rows[0]["cost_of_sales"], 60)
		self.assertEqual(rows[0]["gross_profit"], 40)

	def test_totals_identify_negative_and_low_margin_items(self):
		rows = [
			{"item_code": "A", "net_sales": 100, "cost_of_sales": 95, "gross_profit": 5, "gross_margin_percent": 5},
			{"item_code": "B", "net_sales": 100, "cost_of_sales": 120, "gross_profit": -20, "gross_margin_percent": -20},
			{"item_code": "C", "net_sales": 200, "cost_of_sales": 100, "gross_profit": 100, "gross_margin_percent": 50},
		]
		totals = _totals(rows)
		self.assertEqual(totals["net_sales"], 400)
		self.assertEqual(totals["cost_of_sales"], 315)
		self.assertEqual(totals["gross_profit"], 85)
		self.assertEqual(totals["negative_margin_items"], 1)
		self.assertEqual(totals["low_margin_items"], 2)
		self.assertEqual(DEFAULT_LOW_MARGIN_PERCENT, 10.0)

	@patch("retailedge.profitability_intelligence.should_hide_cost_price", return_value=True)
	def test_cost_visibility_policy_fails_closed(self, _mock_hide):
		with self.assertRaises(frappe.PermissionError):
			_assert_cost_visibility()
