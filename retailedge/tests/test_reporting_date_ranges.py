from __future__ import annotations

import os
import unittest
from datetime import timedelta
from pathlib import Path

import frappe
from frappe.utils import add_days, get_first_day, getdate, nowdate

from retailedge.reporting.date_ranges import get_preset_dates


class TestReportingDateRanges(unittest.TestCase):
	def test_preset_dates_calculation(self):
		today = getdate(nowdate())

		# Today
		f, t = get_preset_dates("Today")
		self.assertEqual(f, today)
		self.assertEqual(t, today)

		# Yesterday
		f, t = get_preset_dates("Yesterday")
		self.assertEqual(f, add_days(today, -1))
		self.assertEqual(t, add_days(today, -1))

		# This Week
		f, t = get_preset_dates("This Week")
		self.assertEqual(f, today - timedelta(days=today.weekday()))
		self.assertEqual(t, today)

		# This Month
		f, t = get_preset_dates("This Month")
		self.assertEqual(f, get_first_day(today))
		self.assertEqual(t, today)

		# This Quarter
		f, t = get_preset_dates("This Quarter")
		quarter_month = ((today.month - 1) // 3) * 3 + 1
		self.assertEqual(f, getdate(f"{today.year}-{quarter_month:02d}-01"))
		self.assertEqual(t, today)

		# This Year
		f, t = get_preset_dates("This Year")
		self.assertEqual(f, getdate(f"{today.year}-01-01"))
		self.assertEqual(t, today)

		# Last Week
		f, t = get_preset_dates("Last Week")
		this_week_start = today - timedelta(days=today.weekday())
		self.assertEqual(f, this_week_start - timedelta(days=7))
		self.assertEqual(t, this_week_start - timedelta(days=1))

		# Last Month
		f, t = get_preset_dates("Last Month")
		first_of_this_month = get_first_day(today)
		last_of_last_month = add_days(first_of_this_month, -1)
		self.assertEqual(f, get_first_day(last_of_last_month))
		self.assertEqual(t, last_of_last_month)

		# Last Quarter
		f, t = get_preset_dates("Last Quarter")
		current_quarter_start_month = ((today.month - 1) // 3) * 3 + 1
		first_of_this_quarter = getdate(f"{today.year}-{current_quarter_start_month:02d}-01")
		last_of_last_quarter = add_days(first_of_this_quarter, -1)
		last_quarter_start_month = ((last_of_last_quarter.month - 1) // 3) * 3 + 1
		self.assertEqual(f, getdate(f"{last_of_last_quarter.year}-{last_quarter_start_month:02d}-01"))
		self.assertEqual(t, last_of_last_quarter)

		# Last Year
		f, t = get_preset_dates("Last Year")
		self.assertEqual(f, getdate(f"{today.year - 1}-01-01"))
		self.assertEqual(t, getdate(f"{today.year - 1}-12-31"))

		# Full History
		f, t = get_preset_dates("Full History")
		self.assertEqual(t, today)
		self.assertIsNotNone(f)

		# Full Branch History
		f, t = get_preset_dates("Full Branch History")
		self.assertEqual(t, today)
		self.assertIsNotNone(f)

		# Custom Period
		f, t = get_preset_dates("Custom Period")
		self.assertIsNone(f)
		self.assertIsNone(t)

	def test_frontend_query_report_period_helper_delegates_to_edgesuite(self):
		retailedge_path = frappe.get_app_path("retailedge")
		js_path = os.path.join(
			retailedge_path,
			"public",
			"js",
			"retailedge_query_report_smart_date.js",
		)
		with open(js_path) as f:
			content = f.read()

		self.assertIn("window.retailedge.setupDateRangePresets", content)
		self.assertIn('runtime?.getComponent?.("EdgeSmartDateRange")', content)
		self.assertIn("runtime?.components?.EdgeSmartDateRange", content)
		self.assertIn("runtime?.Vue", content)
		self.assertIn("__retailedgeSmartDateApp", content)
		self.assertIn("__retailedgeSmartDateHost", content)
		self.assertIn("hideFilterControl(presetFilter)", content)
		self.assertIn("hideFilterControl(fromFilter)", content)
		self.assertIn("hideFilterControl(toFilter)", content)
		self.assertIn("await setExactPeriod(value?.from_date || \"\", value?.to_date || \"\")", content)
		self.assertIn("queryReport._no_refresh = true", content)
		self.assertIn("queryReport.refresh()", content)
		self.assertIn("window.retailedge.getPresetDates = undefined", content)
		self.assertNotIn('case "This Month"', content)
		self.assertNotIn('case "Last Quarter"', content)

	def test_all_native_query_report_period_callers_use_central_helper(self):
		retailedge_path = Path(frappe.get_app_path("retailedge"))
		report_root = retailedge_path / "retailedge" / "report"
		expected = {
			"pos_closing_variance_vs_expenses",
			"retailedge_invoice_payment_audit",
			"retailedge_cashier_expense_review",
			"retailedge_daily_sales_audit_register",
			"retailedge_branch_performance_summary",
			"retailedge_bank_transaction_matching",
			"retailedge_stock_movement_history",
		}
		actual = set()
		for script in report_root.glob("*/*.js"):
			if "setupDateRangePresets(report)" in script.read_text():
				actual.add(script.parent.name)

		self.assertEqual(actual, expected)
