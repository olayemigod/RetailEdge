# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
import frappe
from frappe.utils import getdate, nowdate, get_first_day, add_days
from datetime import timedelta
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
