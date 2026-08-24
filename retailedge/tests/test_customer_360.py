from __future__ import annotations

import unittest

import frappe

from retailedge.customer_360 import (
	_period_summary,
	_relationship_summary,
	aggregate_top_items,
)


class TestCustomer360(unittest.TestCase):
	def test_relationship_summary_uses_historical_latest_purchase_but_period_cadence(self):
		headers = [
			frappe._dict({"name": "SI-001", "posting_date": "2026-08-01", "is_return": 0}),
			frappe._dict({"name": "SIR-001", "posting_date": "2026-08-05", "is_return": 1}),
			frappe._dict({"name": "SI-002", "posting_date": "2026-08-11", "is_return": 0}),
		]
		result = _relationship_summary(
			first_purchase_date="2026-07-15",
			latest_purchase_date="2026-08-18",
			headers=headers,
			to_date="2026-08-21",
		)
		self.assertEqual(result["first_purchase_date"], "2026-07-15")
		self.assertEqual(result["last_purchase_date"], "2026-08-18")
		self.assertEqual(result["period_purchase_count"], 2)
		self.assertEqual(result["average_days_between_purchases"], 10)
		self.assertEqual(result["days_since_last_purchase"], 3)

	def test_relationship_summary_keeps_historical_latest_purchase_when_period_is_empty(self):
		result = _relationship_summary(
			first_purchase_date="2026-01-03",
			latest_purchase_date="2026-07-29",
			headers=[],
			to_date="2026-08-10",
		)
		self.assertEqual(result["last_purchase_date"], "2026-07-29")
		self.assertEqual(result["days_since_last_purchase"], 12)
		self.assertEqual(result["period_purchase_count"], 0)
		self.assertIsNone(result["average_days_between_purchases"])

	def test_relationship_summary_has_no_fake_cadence_for_one_purchase(self):
		result = _relationship_summary(
			first_purchase_date="2026-08-03",
			latest_purchase_date="2026-08-03",
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

	def test_period_summary_does_not_invent_receivables_or_profitability_when_missing(self):
		result = _period_summary(None)
		self.assertEqual(result["net_sales"], 0)
		self.assertNotIn("current_outstanding", result)
		self.assertNotIn("overdue_outstanding", result)
		self.assertNotIn("gross_profit", result)
		self.assertNotIn("cost_of_sales", result)


if __name__ == "__main__":
	unittest.main()
