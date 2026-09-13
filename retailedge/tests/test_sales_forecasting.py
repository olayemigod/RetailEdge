from __future__ import annotations

import unittest

import frappe

from retailedge.sales_forecasting import _aggregate_monthly_sales, _completed_month_window


class TestSalesForecasting(unittest.TestCase):
	def test_partial_current_month_is_excluded_from_history(self):
		from_date, to_date, forecast_start = _completed_month_window("2026-08-24", 3)
		self.assertEqual(from_date, "2026-05-01")
		self.assertEqual(to_date, "2026-07-31")
		self.assertEqual(forecast_start, "2026-08-01")

	def test_month_end_as_of_date_includes_that_completed_month(self):
		from_date, to_date, forecast_start = _completed_month_window("2026-08-31", 3)
		self.assertEqual(from_date, "2026-06-01")
		self.assertEqual(to_date, "2026-08-31")
		self.assertEqual(forecast_start, "2026-09-01")

	def test_empty_completed_month_is_explicit_zero_actual(self):
		rows = _aggregate_monthly_sales(
			[
				frappe._dict(
					name="SINV-1",
					posting_date="2026-05-15",
					base_net_total=1000,
					is_return=0,
				),
				frappe._dict(
					name="SINV-2",
					posting_date="2026-07-10",
					base_net_total=500,
					is_return=0,
				),
			],
			from_date="2026-05-01",
			to_date="2026-07-31",
		)
		self.assertEqual(len(rows), 3)
		self.assertEqual(rows[1]["period_start"], "2026-06-01")
		self.assertEqual(rows[1]["net_sales"], 0)
		self.assertEqual(rows[1]["invoice_count"], 0)

	def test_returns_reduce_net_sales_without_inflating_sales_invoice_count(self):
		rows = _aggregate_monthly_sales(
			[
				frappe._dict(
					name="SINV-3",
					posting_date="2026-07-01",
					base_net_total=1000,
					is_return=0,
				),
				frappe._dict(
					name="SINV-RET-3",
					posting_date="2026-07-20",
					base_net_total=-250,
					is_return=1,
				),
			],
			from_date="2026-07-01",
			to_date="2026-07-31",
		)[0]
		self.assertEqual(rows["gross_sales"], 1000)
		self.assertEqual(rows["returns_value"], 250)
		self.assertEqual(rows["net_sales"], 750)
		self.assertEqual(rows["invoice_count"], 1)
		self.assertEqual(rows["return_count"], 1)

	def test_item_scoped_forecast_uses_matching_line_values_not_whole_invoice(self):
		headers = [
			frappe._dict(
				name="SINV-4",
				posting_date="2026-07-05",
				base_net_total=5000,
				is_return=0,
			),
			frappe._dict(
				name="SINV-5",
				posting_date="2026-07-10",
				base_net_total=3000,
				is_return=0,
			),
		]
		items = [frappe._dict(parent="SINV-4", base_net_amount=1200)]
		row = _aggregate_monthly_sales(
			headers,
			from_date="2026-07-01",
			to_date="2026-07-31",
			items=items,
			item_scoped=True,
		)[0]
		self.assertEqual(row["gross_sales"], 1200)
		self.assertEqual(row["net_sales"], 1200)
		self.assertEqual(row["invoice_count"], 1)

	def test_item_scoped_return_uses_matching_return_line_value(self):
		headers = [
			frappe._dict(
				name="SINV-RET-6",
				posting_date="2026-07-15",
				base_net_total=-1000,
				is_return=1,
			)
		]
		items = [frappe._dict(parent="SINV-RET-6", base_net_amount=-200)]
		row = _aggregate_monthly_sales(
			headers,
			from_date="2026-07-01",
			to_date="2026-07-31",
			items=items,
			item_scoped=True,
		)[0]
		self.assertEqual(row["returns_value"], 200)
		self.assertEqual(row["net_sales"], -200)
		self.assertEqual(row["return_count"], 1)


if __name__ == "__main__":
	unittest.main()
