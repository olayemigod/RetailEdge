from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from retailedge.forecasting import MAX_FORECAST_HORIZON, build_baseline_forecast
from retailedge.sales_reporting import (
	MAX_INVOICE_SCAN_ROWS,
	MAX_ITEM_SCAN_ROWS,
	_assert_report_access,
	_coerce_filters,
	_company_currency,
	_filter_headers_by_salesperson,
	_get_invoice_items,
	_get_permitted_invoice_headers,
	_validate_filters,
)

DEFAULT_HISTORY_MONTHS = 6
DEFAULT_FORECAST_MONTHS = 3
MAX_SALES_FORECAST_HISTORY_MONTHS = 24


@frappe.whitelist()
def get_sales_forecast(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _normalise_filters(filters)
	return _build_sales_forecast_dataset(resolved)


@frappe.whitelist()
def get_sales_forecast_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _normalise_filters(filters)
	dataset = _build_sales_forecast_dataset(resolved)
	return {
		"title": dataset["title"],
		"columns": dataset["columns"],
		"rows": dataset["rows"],
		"summary": dataset["summary"],
		"company_currency": dataset["company_currency"],
		"metadata": dataset["metadata"],
	}


def _normalise_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	resolved = _coerce_filters(filters)
	if not resolved.get("company"):
		resolved.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	resolved.as_of_date = str(resolved.get("as_of_date") or nowdate())
	resolved.history_months = _bounded_int(
		resolved.get("history_months"),
		default=DEFAULT_HISTORY_MONTHS,
		minimum=1,
		maximum=MAX_SALES_FORECAST_HISTORY_MONTHS,
		label=_("History Months"),
	)
	resolved.forecast_months = _bounded_int(
		resolved.get("forecast_months"),
		default=DEFAULT_FORECAST_MONTHS,
		minimum=1,
		maximum=MAX_FORECAST_HORIZON,
		label=_("Forecast Months"),
	)
	resolved.invoice_kind = "All"
	resolved.from_date, resolved.to_date, resolved.forecast_start = _completed_month_window(
		resolved.as_of_date,
		resolved.history_months,
	)
	return resolved


def _build_sales_forecast_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters)
	headers = _filter_headers_by_salesperson(headers, filters.get("salesperson"))

	item_scoped = any(filters.get(fieldname) for fieldname in ("item_code", "item_group", "warehouse"))
	items = _get_invoice_items([row.name for row in headers], filters) if item_scoped else []
	actual_rows = _aggregate_monthly_sales(
		headers,
		from_date=filters.from_date,
		to_date=filters.to_date,
		items=items,
		item_scoped=item_scoped,
	)
	forecast = build_baseline_forecast(
		[
			{"period_start": row["period_start"], "actual": row["net_sales"]}
			for row in actual_rows
		],
		horizon=filters.forecast_months,
		period="Monthly",
		as_of_date=filters.to_date,
	)

	rows = [
		{
			**row,
			"row_type": _("Actual"),
			"forecast": None,
		}
		for row in actual_rows
	]
	rows.extend(
		{
			"period_start": row["period_start"],
			"gross_sales": None,
			"returns_value": None,
			"net_sales": None,
			"invoice_count": None,
			"return_count": None,
			"row_type": _("Forecast"),
			"forecast": flt(row["forecast"]),
		}
		for row in forecast["rows"]
	)

	currency = _company_currency(filters.company)
	historical_net_sales = sum(flt(row["net_sales"]) for row in actual_rows)
	forecast_total = sum(flt(row["forecast"]) for row in forecast["rows"])
	return {
		"title": _("Sales Forecast"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": [
			{"label": _("Historical Net Sales"), "value": historical_net_sales, "datatype": "Currency"},
			{
				"label": _("Average Monthly Net Sales"),
				"value": historical_net_sales / len(actual_rows) if actual_rows else 0.0,
				"datatype": "Currency",
			},
			{
				"label": _("Next Month Forecast"),
				"value": flt(forecast["rows"][0]["forecast"]) if forecast["rows"] else 0.0,
				"datatype": "Currency",
			},
			{"label": _("Forecast Horizon Total"), "value": forecast_total, "datatype": "Currency"},
		],
		"company_currency": currency,
		"scope": {
			"company": filters.company,
			"branch": str(filters.get("branch") or ""),
			"customer": str(filters.get("customer") or ""),
			"item_code": str(filters.get("item_code") or ""),
			"item_group": str(filters.get("item_group") or ""),
			"warehouse": str(filters.get("warehouse") or ""),
			"salesperson": str(filters.get("salesperson") or ""),
			"as_of_date": filters.as_of_date,
			"history_from_date": filters.from_date,
			"history_to_date": filters.to_date,
			"forecast_start": filters.forecast_start,
			"history_months": filters.history_months,
			"forecast_months": filters.forecast_months,
		},
		"scan": {
			"invoices": len(headers),
			"item_rows": len(items),
			"invoice_limit": MAX_INVOICE_SCAN_ROWS,
			"item_limit": MAX_ITEM_SCAN_ROWS,
		},
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice",
			"item_truth": "Submitted ERPNext Sales Invoice Item when Item, Item Group, or Warehouse scope is selected",
			"returns_treatment": "Submitted return invoices reduce monthly net sales and remain separately visible as return value",
			"history_policy": "Completed calendar months only; partial current month is excluded unless the as-of date is the calendar month end",
			"zero_period_policy": "A completed month with no matching submitted invoices is supplied explicitly as zero actual sales",
			"forecast_engine": forecast["metadata"],
			"profit_truth": "This report forecasts sales only; ERPNext Profit and Loss remains financial profit truth",
			"mutates_accounting_documents": False,
		},
	}


def _aggregate_monthly_sales(
	headers: list[frappe._dict],
	*,
	from_date: str,
	to_date: str,
	items: list[frappe._dict] | None = None,
	item_scoped: bool = False,
) -> list[dict[str, Any]]:
	periods = _month_starts(from_date, to_date)
	buckets: dict[str, dict[str, Any]] = {
		period: {
			"period_start": period,
			"gross_sales": 0.0,
			"returns_value": 0.0,
			"net_sales": 0.0,
			"invoice_count": 0,
			"return_count": 0,
		}
		for period in periods
	}
	if not buckets:
		return []

	if item_scoped:
		item_totals: dict[str, float] = defaultdict(float)
		for row in items or []:
			item_totals[str(row.get("parent") or "")] += flt(row.get("base_net_amount"))
	else:
		item_totals = {}

	for row in headers:
		invoice_name = str(row.get("name") or "")
		if item_scoped and invoice_name not in item_totals:
			continue
		posting_date = str(row.get("posting_date") or "")
		if not posting_date:
			continue
		period_start = f"{posting_date[:7]}-01"
		bucket = buckets.get(period_start)
		if not bucket:
			continue
		amount = item_totals[invoice_name] if item_scoped else flt(row.get("base_net_total"))
		if cint(row.get("is_return")):
			return_value = abs(amount)
			bucket["returns_value"] += return_value
			bucket["net_sales"] -= return_value
			bucket["return_count"] += 1
		else:
			bucket["gross_sales"] += amount
			bucket["net_sales"] += amount
			bucket["invoice_count"] += 1
	return [buckets[period] for period in periods]


def _completed_month_window(as_of_date: str, history_months: int) -> tuple[str, str, str]:
	as_of = getdate(as_of_date)
	month_end = getdate(get_last_day(as_of))
	if as_of == month_end:
		history_end = as_of
		forecast_start = getdate(add_months(get_first_day(as_of), 1))
	else:
		forecast_start = getdate(get_first_day(as_of))
		history_end = forecast_start - timedelta(days=1)
	history_start = getdate(add_months(get_first_day(history_end), -(history_months - 1)))
	return history_start.isoformat(), history_end.isoformat(), forecast_start.isoformat()


def _month_starts(from_date: str, to_date: str) -> list[str]:
	current = getdate(get_first_day(from_date))
	end = getdate(get_first_day(to_date))
	result: list[str] = []
	while current <= end:
		result.append(current.isoformat())
		current = getdate(add_months(current, 1))
	return result


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, label: str) -> int:
	if value in (None, ""):
		return default
	try:
		resolved = int(value)
	except (TypeError, ValueError):
		frappe.throw(_("{0} must be a whole number.").format(label))
	if resolved < minimum or resolved > maximum:
		frappe.throw(_("{0} must be between {1} and {2}.").format(label, minimum, maximum))
	return resolved


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "period_start", "label": _("Month"), "fieldtype": "Date"},
		{"fieldname": "row_type", "label": _("Type"), "fieldtype": "Data"},
		{"fieldname": "gross_sales", "label": _("Gross Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "returns_value", "label": _("Returns"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "net_sales", "label": _("Actual Net Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "forecast", "label": _("Forecast Net Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "invoice_count", "label": _("Sales Invoices"), "fieldtype": "Int"},
		{"fieldname": "return_count", "label": _("Returns"), "fieldtype": "Int"},
	]
