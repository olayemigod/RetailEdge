from __future__ import annotations

import unittest

import frappe

from retailedge.customer_360 import (
	_period_summary,
	_relationship_summary,
	aggregate_top_items,
)


class TestCustomer360(unittest.TestCase):
	def test_relationship_summary_ignores_returns_for_purchase_cadence(self):
		headers = [
			frappe._dict({"name": "SI-001", "posting_date": "2026-08-01", "is_return": 0}),
			frappe._dict({"name": "SIR-001", "posting_date": "2026-08-05", "is_return": 1}),
			frappe._dict({"name": "SI-002", "posting_date": "2026-08-11", "is_return": 0}),
		]
		result = _relationship_summary(
			first_purchase_date="2026-07-15",
			headers=headers,
			to_date="2026-08-21",
		)
		self.assertEqual(result["first_purchase_date"], "2026-07-15")
		self.assertEqual(result["last_purchase_date"], "2026-08-11")
		self.assertEqual(result["period_purchase_count"], 2)
		self.assertEqual(result["average_days_between_purchases"], 10)
		self.assertEqual(result["days_since_last_purchase"], 10)

	def test_relationship_summary_has_no_fake_cadence_for_one_purchase(self):
		result = _relationship_summary(
			first_purchase_date="2026-08-03",
			headers=[frappe._dict({"name": "SI-001", "posting_date": "2026-08-03", "is_return": 0})],
			to_date="2026-08-10",
		)
		self.assertIsNone(result["average_days_between_purchases"])
		self.assertEqual(result["period_purchase_count"], 1)

	def test_top_items_net_returns_against_sales(self):
		headers = [
			frappe._dict({"name": "SI-001", "is_return": 0}),
			frappe._dict({"name": "SIR-001", "is_return": 1}),
		]
		items = [
			frappe._dict({"parent": "SI-001", "item_code": "ITEM-A", "item_name": "Item A", "item_group": "Products", "qty": 5, "base_net_amount": 500}),
			frappe._dict({"parent": "SIR-001", "item_code": "ITEM-A", "item_name": "Item A", "item_group": "Products", "qty": -2, "base_net_amount": -200}),
			frappe._dict({"parent": "SI-001", "item_code": "ITEM-B", "item_name": "Item B", "item_group": "Products", "qty": 1, "base_net_amount": 150}),
		]
		rows = aggregate_top_items(headers, items)
		by_item = {row["item_code"]: row for row in rows}
		self.assertEqual(by_item["ITEM-A"]["net_qty"], 3)
		self.assertEqual(by_item["ITEM-A"]["net_sales"], 300)
		self.assertEqual(by_item["ITEM-A"]["invoice_count"], 2)
		self.assertEqual(rows[0]["item_code"], "ITEM-A")

	def test_period_summary_does_not_invent_profitability_when_hidden(self):
		row = {
			"segment": "Returning",
			"sales_invoice_count": 2,
			"return_invoice_count": 0,
			"gross_sales": 1000,
			"returns_value": 0,
			"net_sales": 1000,
			"average_purchase_value": 500,
			"current_outstanding": 100,
			"overdue_outstanding": 40,
			"open_invoice_count": 1,
			"max_overdue_days": 15,
		}
		result = _period_summary(row)
		self.assertNotIn("gross_profit", result)
		self.assertNotIn("cost_of_sales", result)
		self.assertEqual(result["net_sales"], 1000)


if __name__ == "__main__":
	unittest.main()
