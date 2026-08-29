from __future__ import annotations

import unittest

import frappe

from retailedge.customer_sales_intelligence import (
	SEGMENT_NEW,
	SEGMENT_RETURNING,
	_aggregate_customer_rows,
	classify_customer_segment,
)


class TestCustomerSalesIntelligence(unittest.TestCase):
	def test_customer_segment_uses_first_submitted_purchase_not_customer_creation(self):
		self.assertEqual(classify_customer_segment("2026-08-01", "2026-08-01"), SEGMENT_NEW)
		self.assertEqual(classify_customer_segment("2026-08-15", "2026-08-01"), SEGMENT_NEW)
		self.assertEqual(classify_customer_segment("2026-07-31", "2026-08-01"), SEGMENT_RETURNING)
		self.assertEqual(classify_customer_segment(None, "2026-08-01"), SEGMENT_RETURNING)

	def test_returns_reduce_net_sales_but_do_not_inflate_purchase_count(self):
		headers = [
			frappe._dict(
				name="SINV-1",
				customer="CUST-1",
				customer_name="Customer One",
				posting_date="2026-08-02",
				base_net_total=1000,
				is_return=0,
			),
			frappe._dict(
				name="SINV-RET-1",
				customer="CUST-1",
				customer_name="Customer One",
				posting_date="2026-08-05",
				base_net_total=-200,
				is_return=1,
			),
		]
		rows = _aggregate_customer_rows(
			headers,
			first_purchase_dates={"CUST-1": "2026-08-02"},
			receivables={},
			profitability={},
			from_date="2026-08-01",
			to_date="2026-08-31",
			show_profitability=False,
		)
		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row["sales_invoice_count"], 1)
		self.assertEqual(row["return_invoice_count"], 1)
		self.assertEqual(row["gross_sales"], 1000)
		self.assertEqual(row["returns_value"], 200)
		self.assertEqual(row["net_sales"], 800)
		self.assertEqual(row["average_purchase_value"], 1000)
		self.assertEqual(row["segment"], SEGMENT_NEW)

	def test_receivable_exposure_is_separate_from_selected_period_sales(self):
		headers = [
			frappe._dict(
				name="SINV-2",
				customer="CUST-2",
				customer_name="Customer Two",
				posting_date="2026-08-20",
				base_net_total=500,
				is_return=0,
			)
		]
		rows = _aggregate_customer_rows(
			headers,
			first_purchase_dates={"CUST-2": "2026-01-10"},
			receivables={
				"CUST-2": {
					"current_outstanding": 750,
					"overdue_outstanding": 250,
					"open_invoice_count": 2,
					"max_overdue_days": 45,
				}
			},
			profitability={},
			from_date="2026-08-01",
			to_date="2026-08-31",
			show_profitability=False,
		)
		row = rows[0]
		self.assertEqual(row["segment"], SEGMENT_RETURNING)
		self.assertEqual(row["current_outstanding"], 750)
		self.assertEqual(row["overdue_outstanding"], 250)
		self.assertEqual(row["open_invoice_count"], 2)
		self.assertEqual(row["max_overdue_days"], 45)

	def test_profitability_fields_are_optional_and_use_supplied_r8_metrics(self):
		headers = [
			frappe._dict(
				name="SINV-3",
				customer="CUST-3",
				customer_name="Customer Three",
				posting_date="2026-08-10",
				base_net_total=1000,
				is_return=0,
			)
		]
		with_profit = _aggregate_customer_rows(
			headers,
			first_purchase_dates={"CUST-3": "2026-08-10"},
			receivables={},
			profitability={"CUST-3": {"cost_of_sales": 700, "gross_profit": 300}},
			from_date="2026-08-01",
			to_date="2026-08-31",
			show_profitability=True,
		)[0]
		self.assertEqual(with_profit["cost_of_sales"], 700)
		self.assertEqual(with_profit["gross_profit"], 300)
		self.assertEqual(with_profit["gross_margin_percent"], 30)

		without_profit = _aggregate_customer_rows(
			headers,
			first_purchase_dates={"CUST-3": "2026-08-10"},
			receivables={},
			profitability={},
			from_date="2026-08-01",
			to_date="2026-08-31",
			show_profitability=False,
		)[0]
		self.assertNotIn("cost_of_sales", without_profit)
		self.assertNotIn("gross_profit", without_profit)
		self.assertNotIn("gross_margin_percent", without_profit)

	def test_last_purchase_and_recency_ignore_return_date(self):
		headers = [
			frappe._dict(
				name="SINV-4",
				customer="CUST-4",
				customer_name="Customer Four",
				posting_date="2026-08-05",
				base_net_total=100,
				is_return=0,
			),
			frappe._dict(
				name="SINV-RET-4",
				customer="CUST-4",
				customer_name="Customer Four",
				posting_date="2026-08-20",
				base_net_total=-20,
				is_return=1,
			),
		]
		row = _aggregate_customer_rows(
			headers,
			first_purchase_dates={"CUST-4": "2026-06-01"},
			receivables={},
			profitability={},
			from_date="2026-08-01",
			to_date="2026-08-31",
			show_profitability=False,
		)[0]
		self.assertEqual(row["last_purchase_date"], "2026-08-05")
		self.assertEqual(row["days_since_last_purchase"], 26)


if __name__ == "__main__":
	unittest.main()
