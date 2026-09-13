from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, getdate, nowdate

from retailedge.customer_receivables import get_customer_receivables_export
from retailedge.dashboard_capabilities import require_dashboard_action

DASHBOARD_KEY = "owner-dashboard"
MAX_PRIORITY_ROWS = 20
MAX_EXPOSURE_ROWS = 10
MAX_OLDEST_ROWS = 10
MAX_NEWLY_OVERDUE_ROWS = 20


@frappe.whitelist()
def get_receivables_control_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)

	from_date = getdate(filters.get("from_date") or get_first_day(nowdate()))
	to_date = getdate(filters.get("to_date") or nowdate())
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date."))

	dataset = get_customer_receivables_export({"company": company, "branch": branch})
	return _build_receivables_control(
		dataset,
		company=company,
		branch=branch,
		from_date=from_date,
		to_date=to_date,
	)


def _build_receivables_control(
	dataset: dict[str, Any],
	*,
	company: str,
	branch: str,
	from_date,
	to_date,
) -> dict[str, Any]:
	rows = [dict(row) for row in (dataset.get("rows") or []) if flt(row.get("outstanding")) > 0]
	total_receivables = sum(flt(row.get("outstanding")) for row in rows)
	overdue_rows = [row for row in rows if int(row.get("overdue_days") or 0) > 0]
	overdue_amount = sum(flt(row.get("outstanding")) for row in overdue_rows)
	over_90_amount = sum(
		flt(row.get("outstanding"))
		for row in rows
		if int(row.get("overdue_days") or 0) > 90
	)

	top_exposures = _top_customer_exposures(rows, total_receivables=total_receivables)
	oldest = _oldest_receivables(overdue_rows)
	newly_overdue = _newly_overdue(
		overdue_rows,
		from_date=from_date,
		to_date=min(to_date, getdate(nowdate())),
	)
	priorities = _collection_priorities(overdue_rows)
	top_customer_share = flt(top_exposures[0].get("share_percent")) if top_exposures else 0.0

	return {
		"title": _("Receivables & Collections Control"),
		"filters": {
			"company": company,
			"branch": branch,
			"from_date": str(from_date),
			"to_date": str(to_date),
		},
		"summary": [
			_card("Total Receivables", total_receivables, "Currency", "current"),
			_card("Overdue Receivables", overdue_amount, "Currency", "current"),
			_card("Over 90 Days", over_90_amount, "Currency", "current"),
			_card("Customers Owing", len({row.get("customer") for row in rows if row.get("customer")}), "Int", "current"),
			_card("Overdue Invoices", len(overdue_rows), "Int", "current"),
			_card("Top Customer Exposure", top_customer_share, "Percent", "current"),
		],
		"pressure": {
			"overdue_percent": _percent(overdue_amount, total_receivables),
			"over_90_percent": _percent(over_90_amount, total_receivables),
			"top_customer_share_percent": top_customer_share,
		},
		"top_customer_exposures": top_exposures,
		"oldest_receivables": oldest,
		"newly_overdue": newly_overdue,
		"collection_priorities": priorities,
		"metadata": {
			"balance_basis": dataset.get("balance_basis") or "current_outstanding",
			"balance_date": dataset.get("current_balance_date") or nowdate(),
			"source": "RetailEdge Customer Receivables using submitted ERPNext Sales Invoice current outstanding balances",
			"newly_overdue_definition": "currently outstanding invoices whose due date fell within the selected period; this is not a historical receivables reconstruction",
			"priority_definition": "overdue invoices ordered by ageing severity, then days overdue, then outstanding amount",
			"native_invoice_route": "/app/sales-invoice/{name}",
			"native_links_open_new_tab": True,
			"scan": dataset.get("scan") or {},
		},
	}


def _top_customer_exposures(rows: list[dict[str, Any]], *, total_receivables: float) -> list[dict[str, Any]]:
	totals: dict[str, dict[str, Any]] = defaultdict(lambda: {"outstanding": 0.0, "invoice_count": 0, "max_overdue_days": 0})
	for row in rows:
		customer = str(row.get("customer") or "").strip()
		if not customer:
			continue
		bucket = totals[customer]
		bucket["customer"] = customer
		bucket["customer_name"] = row.get("customer_name") or customer
		bucket["outstanding"] = flt(bucket.get("outstanding")) + flt(row.get("outstanding"))
		bucket["invoice_count"] = int(bucket.get("invoice_count") or 0) + 1
		bucket["max_overdue_days"] = max(
			int(bucket.get("max_overdue_days") or 0),
			int(row.get("overdue_days") or 0),
		)
	result = []
	for bucket in totals.values():
		result.append(
			{
				**bucket,
				"share_percent": _percent(flt(bucket.get("outstanding")), total_receivables) or 0.0,
			}
		)
	result.sort(key=lambda row: (-flt(row.get("outstanding")), -int(row.get("max_overdue_days") or 0), str(row.get("customer"))))
	return result[:MAX_EXPOSURE_ROWS]


def _oldest_receivables(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	ordered = sorted(
		rows,
		key=lambda row: (
			-int(row.get("overdue_days") or 0),
			-flt(row.get("outstanding")),
			str(row.get("invoice") or ""),
		),
	)
	return [_invoice_control_row(row) for row in ordered[:MAX_OLDEST_ROWS]]


def _newly_overdue(rows: list[dict[str, Any]], *, from_date, to_date) -> list[dict[str, Any]]:
	if from_date > to_date:
		return []
	matches = []
	for row in rows:
		due_date = row.get("due_date") or row.get("posting_date")
		if not due_date:
			continue
		resolved_due = getdate(due_date)
		if from_date <= resolved_due <= to_date:
			matches.append(row)
	matches.sort(
		key=lambda row: (
			str(row.get("due_date") or row.get("posting_date") or ""),
			-flt(row.get("outstanding")),
			str(row.get("invoice") or ""),
		),
		reverse=True,
	)
	return [_invoice_control_row(row) for row in matches[:MAX_NEWLY_OVERDUE_ROWS]]


def _collection_priorities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	ordered = sorted(
		rows,
		key=lambda row: (
			-_severity_rank(int(row.get("overdue_days") or 0)),
			-int(row.get("overdue_days") or 0),
			-flt(row.get("outstanding")),
			str(row.get("invoice") or ""),
		),
	)
	return [
		{
			**_invoice_control_row(row),
			"priority": _priority_label(int(row.get("overdue_days") or 0)),
		}
		for row in ordered[:MAX_PRIORITY_ROWS]
	]


def _invoice_control_row(row: dict[str, Any]) -> dict[str, Any]:
	return {
		"customer": row.get("customer") or "",
		"customer_name": row.get("customer_name") or row.get("customer") or "",
		"invoice": row.get("invoice") or "",
		"branch": row.get("branch") or "",
		"posting_date": row.get("posting_date"),
		"due_date": row.get("due_date"),
		"outstanding": flt(row.get("outstanding")),
		"overdue_days": int(row.get("overdue_days") or 0),
		"ageing_bucket": row.get("ageing_bucket") or "",
		"status": row.get("status") or "",
	}


def _severity_rank(overdue_days: int) -> int:
	if overdue_days > 90:
		return 4
	if overdue_days > 60:
		return 3
	if overdue_days > 30:
		return 2
	return 1


def _priority_label(overdue_days: int) -> str:
	if overdue_days > 90:
		return "Critical"
	if overdue_days > 60:
		return "High"
	if overdue_days > 30:
		return "Medium"
	return "Watch"


def _percent(numerator: float, denominator: float) -> float | None:
	return numerator / denominator * 100.0 if denominator else None


def _card(label: str, value: float | int, datatype: str, time_basis: str) -> dict[str, Any]:
	return {"label": _(label), "value": value, "datatype": datatype, "time_basis": time_basis}


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
