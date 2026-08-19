from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, getdate, today

from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.expense_register import get_expense_register_export

DASHBOARD_KEY = "expense-overview"


@frappe.whitelist()
def get_expense_period_context(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)

	anchor = getdate(filters.get("to_date") or today())
	mtd_start = getdate(get_first_day(anchor))
	ytd_start = date(anchor.year, 1, 1)
	common = {
		"company": company,
		"branch": branch,
		"expense_category": filters.get("expense_category") or "",
		"expense_status": filters.get("expense_status") or "",
	}
	mtd = _load_period({**common, "from_date": str(mtd_start), "to_date": str(anchor)})
	ytd = _load_period({**common, "from_date": str(ytd_start), "to_date": str(anchor)})
	return {
		"anchor_date": str(anchor),
		"mtd": {**mtd, "from_date": str(mtd_start), "to_date": str(anchor), "label": _("Month to Date")},
		"ytd": {
			**ytd,
			"from_date": str(ytd_start),
			"to_date": str(anchor),
			"label": _("Calendar Year to Date"),
		},
		"metadata": {
			"source": "RetailEdge Expense Register",
			"time_basis": "as_of_selected_to_date",
			"ytd_basis": "calendar_year",
		},
	}


def _load_period(period_filters: dict[str, Any]) -> dict[str, Any]:
	payload = get_expense_register_export(period_filters)
	rows = list(payload.get("rows") or [])
	total = sum(flt(row.get("amount")) for row in rows)
	return {
		"total_expenses": total,
		"expense_count": len(rows),
		"average_expense": total / len(rows) if rows else 0,
		"top_categories": _top_categories(rows),
	}


def _top_categories(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
	buckets: dict[str, dict[str, Any]] = {}
	for row in rows:
		category = str(row.get("expense_category") or _("Unspecified")).strip() or _("Unspecified")
		bucket = buckets.setdefault(category, {"amount": 0.0, "count": 0})
		bucket["amount"] += flt(row.get("amount"))
		bucket["count"] += 1
	result = [
		{"label": category, "amount": values["amount"], "count": values["count"]}
		for category, values in buckets.items()
	]
	result.sort(key=lambda row: (-flt(row["amount"]), row["label"]))
	return result[:limit]


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
