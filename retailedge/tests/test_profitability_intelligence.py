from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.profitability_intelligence import (
	DEFAULT_LOW_MARGIN_PERCENT,
	_aggregate_items,
	_assert_cost_visibility,
	_build_comparison,
	_build_dimensions,
	_previous_period_filters,
	_totals,
)


class TestProfitabilityIntelligence(FrappeTestCase):
	def test_aggregate_uses_recorded_incoming_rate_and_net_sales(self):
		rows = _aggregate_items(
			[
				frappe._dict(parent="SINV-0001", item_code="ITEM-A", item_name="Item A", item_group="Products", stock_qty=2, base_net_amount=200, incoming_rate=60),
				frappe._dict(parent="SINV-0002", item_code="ITEM-A", item_name="Item A", item_group="Products", stock_qty=1, base_net_amount=120, incoming_rate=70),
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

	def test_dimensions_use_authorized_invoice_metadata(self):
		items = [
			frappe._dict(parent="SINV-1", item_code="A", item_group="Batteries", stock_qty=1, base_net_amount=150, incoming_rate=100),
			frappe._dict(parent="SINV-2", item_code="B", item_group="Inverters", stock_qty=1, base_net_amount=300, incoming_rate=200),
		]
		headers = {
			"SINV-1": frappe._dict(name="SINV-1", branch="Lagos", customer="CUST-1", customer_name="Alpha Stores"),
			"SINV-2": frappe._dict(name="SINV-2", branch="Abuja", customer="CUST-2", customer_name="Beta Stores"),
		}
		dimensions = _build_dimensions(items, headers)
		self.assertEqual(dimensions["branch"][0]["gross_profit"], 100)
		self.assertEqual({row["key"] for row in dimensions["branch"]}, {"Lagos", "Abuja"})
		self.assertEqual({row["key"] for row in dimensions["item_group"]}, {"Batteries", "Inverters"})
		self.assertEqual({row["key"] for row in dimensions["customer"]}, {"Alpha Stores", "Beta Stores"})

	def test_salesperson_dimension_allocates_without_double_counting(self):
		items = [frappe._dict(parent="SINV-1", item_code="A", item_group="Products", stock_qty=1, base_net_amount=200, incoming_rate=100)]
		headers = {"SINV-1": frappe._dict(name="SINV-1", branch="Lagos", customer_name="Alpha")}
		dimensions = _build_dimensions(items, headers, {"SINV-1": [("Ada", 0.75), ("Bola", 0.25)]})
		rows = {row["key"]: row for row in dimensions["salesperson"]}
		self.assertEqual(rows["Ada"]["net_sales"], 150)
		self.assertEqual(rows["Ada"]["gross_profit"], 75)
		self.assertEqual(rows["Bola"]["net_sales"], 50)
		self.assertEqual(rows["Bola"]["gross_profit"], 25)
		self.assertEqual(sum(row["net_sales"] for row in rows.values()), 200)
		self.assertEqual(sum(row["gross_profit"] for row in rows.values()), 100)

	def test_previous_period_is_equal_length_and_immediately_precedes_current(self):
		previous = _previous_period_filters(frappe._dict(company="Test", branch="", from_date="2026-08-11", to_date="2026-08-20"))
		self.assertEqual(previous.from_date, "2026-08-01")
		self.assertEqual(previous.to_date, "2026-08-10")

	def test_comparison_reports_absolute_and_percentage_change(self):
		comparison = _build_comparison(
			{"net_sales": 120, "gross_profit": 30, "gross_margin_percent": 25},
			{"net_sales": 100, "gross_profit": 20, "gross_margin_percent": 20},
			frappe._dict(from_date="2026-08-01", to_date="2026-08-10"),
		)
		net_sales = next(row for row in comparison["metrics"] if row["key"] == "net_sales")
		self.assertEqual(net_sales["change"], 20)
		self.assertEqual(net_sales["change_percent"], 20)
		self.assertEqual(comparison["previous_from_date"], "2026-08-01")

	@patch("retailedge.profitability_intelligence.should_hide_cost_price", return_value=True)
	def test_cost_visibility_policy_fails_closed(self, _mock_hide):
		with self.assertRaises(frappe.PermissionError):
			_assert_cost_visibility()
