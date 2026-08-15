from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import add_days, get_first_day, getdate, nowdate


def get_preset_dates(preset: str) -> tuple[getdate | None, getdate | None]:
	today = getdate(nowdate())

	if preset == "Today":
		from_date = today
		to_date = today
	elif preset == "Yesterday":
		yesterday = add_days(today, -1)
		from_date = yesterday
		to_date = yesterday
	elif preset == "This Week":
		# Monday as first day of week
		from_date = today - timedelta(days=today.weekday())
		to_date = today
	elif preset == "This Month":
		from_date = get_first_day(today)
		to_date = today
	elif preset == "This Quarter":
		quarter_month = ((today.month - 1) // 3) * 3 + 1
		from_date = getdate(f"{today.year}-{quarter_month:02d}-01")
		to_date = today
	elif preset == "This Year":
		from_date = getdate(f"{today.year}-01-01")
		to_date = today
	elif preset == "Last Week":
		this_week_start = today - timedelta(days=today.weekday())
		from_date = this_week_start - timedelta(days=7)
		to_date = this_week_start - timedelta(days=1)
	elif preset == "Last Month":
		first_of_this_month = get_first_day(today)
		last_of_last_month = add_days(first_of_this_month, -1)
		from_date = get_first_day(last_of_last_month)
		to_date = last_of_last_month
	elif preset == "Last Quarter":
		current_quarter_start_month = ((today.month - 1) // 3) * 3 + 1
		first_of_this_quarter = getdate(f"{today.year}-{current_quarter_start_month:02d}-01")
		last_of_last_quarter = add_days(first_of_this_quarter, -1)
		last_quarter_start_month = ((last_of_last_quarter.month - 1) // 3) * 3 + 1
		from_date = getdate(f"{last_of_last_quarter.year}-{last_quarter_start_month:02d}-01")
		to_date = last_of_last_quarter
	elif preset == "Last Year":
		from_date = getdate(f"{today.year - 1}-01-01")
		to_date = getdate(f"{today.year - 1}-12-31")
	elif preset in ("Full History", "Full Branch History"):
		earliest = None
		from retailedge.branch_context import has_doctype

		if has_doctype("Sales Invoice"):
			earliest = frappe.db.get_value(
				"Sales Invoice", filters={}, fieldname="posting_date", order_by="posting_date asc"
			)
		if not earliest:
			earliest = "2020-01-01"
		from_date = getdate(earliest)
		to_date = today
	else:
		from_date = None
		to_date = None

	return from_date, to_date
