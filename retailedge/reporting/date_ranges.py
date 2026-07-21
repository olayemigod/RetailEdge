from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe.utils import add_days, get_first_day, getdate, nowdate


def get_preset_dates(preset: str) -> tuple[date | None, date | None]:
	"""Resolve supported RetailEdge date presets without mutating caller filters."""
	today = getdate(nowdate())

	if preset == "Today":
		return today, today
	if preset == "Yesterday":
		yesterday = add_days(today, -1)
		return yesterday, yesterday
	if preset == "This Week":
		return today - timedelta(days=today.weekday()), today
	if preset == "This Month":
		return get_first_day(today), today
	if preset == "This Quarter":
		quarter_month = ((today.month - 1) // 3) * 3 + 1
		return getdate(f"{today.year}-{quarter_month:02d}-01"), today
	if preset == "This Year":
		return getdate(f"{today.year}-01-01"), today
	if preset == "Last Week":
		this_week_start = today - timedelta(days=today.weekday())
		return this_week_start - timedelta(days=7), this_week_start - timedelta(days=1)
	if preset == "Last Month":
		first_of_this_month = get_first_day(today)
		last_of_last_month = add_days(first_of_this_month, -1)
		return get_first_day(last_of_last_month), last_of_last_month
	if preset == "Last Quarter":
		current_quarter_start_month = ((today.month - 1) // 3) * 3 + 1
		first_of_this_quarter = getdate(f"{today.year}-{current_quarter_start_month:02d}-01")
		last_of_last_quarter = add_days(first_of_this_quarter, -1)
		last_quarter_start_month = ((last_of_last_quarter.month - 1) // 3) * 3 + 1
		return (
			getdate(f"{last_of_last_quarter.year}-{last_quarter_start_month:02d}-01"),
			last_of_last_quarter,
		)
	if preset == "Last Year":
		return getdate(f"{today.year - 1}-01-01"), getdate(f"{today.year - 1}-12-31")
	if preset in {"Full History", "Full Branch History"}:
		from retailedge.branch_context import has_doctype

		earliest = None
		if has_doctype("Sales Invoice"):
			earliest = frappe.db.get_value(
				"Sales Invoice",
				filters={},
				fieldname="posting_date",
				order_by="posting_date asc",
			)
		return getdate(earliest or "2020-01-01"), today

	return None, None
