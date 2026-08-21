from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, today

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.sales_reporting import (
	MAX_ITEM_SCAN_ROWS,
	_assert_report_access,
	_company_currency,
	_coerce_filters,
	_get_permitted_invoice_headers,
	_validate_filters,
)

MAX_PROFITABILITY_ROWS = MAX_ITEM_SCAN_ROWS
DEFAULT_LOW_MARGIN_PERCENT = 10.0


@frappe.whitelist()
def get_profitability_intelligence(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return permission-aware owner profitability metrics from submitted Sales Invoices.

	Sales Invoice remains the revenue truth. Cost is the ERPNext incoming rate recorded on
	the submitted Sales Invoice Item, so this layer does not invent or maintain a parallel
	cost model.
	"""
	filters = _coerce_filters(filters)
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	filters.from_date = str(filters.get("from_date") or get_first_day(today()))
	filters.to_date = str(filters.get("to_date") or today())

	_validate_filters(filters)
	_assert_report_access(filters)
	_assert_cost_visibility()

	headers = _get_permitted_invoice_headers(filters)
	header_map = {row.name: row for row in headers}
	items = _get_costed_items(list(header_map))
	rows = _aggregate_items(items)
	currency = _company_currency(filters.company)

	totals = _totals(rows)
	return {
		"summary": [
			{"label": _("Net Sales"), "value": totals["net_sales"], "datatype": "Currency"},
			{"label": _("Cost of Sales"), "value": totals["cost_of_sales"], "datatype": "Currency"},
			{"label": _("Gross Profit"), "value": totals["gross_profit"], "datatype": "Currency"},
			{"label": _("Gross Margin"), "value": totals["gross_margin_percent"], "datatype": "Percent"},
			{"label": _("Negative Margin Items"), "value": totals["negative_margin_items"], "datatype": "Int"},
			{"label": _("Low Margin Items"), "value": totals["low_margin_items"], "datatype": "Int"},
		],
		"rows": rows,
		"top_contributors": sorted(rows, key=lambda row: (-flt(row["gross_profit"]), row["item_code"]))[:10],
		"margin_leakage": sorted(
			[row for row in rows if flt(row["gross_margin_percent"]) < DEFAULT_LOW_MARGIN_PERCENT],
			key=lambda row: (flt(row["gross_margin_percent"]), -abs(flt(row["net_sales"]))),
		)[:25],
		"company_currency": currency,
		"show_costs": 1,
		"scope": {
			"company": filters.company,
			"branch": str(filters.get("branch") or ""),
			"from_date": filters.from_date,
			"to_date": filters.to_date,
		},
		"metadata": {
			"revenue_truth": "Submitted Sales Invoice / Sales Invoice Item",
			"cost_truth": "Sales Invoice Item incoming_rate × stock_qty",
			"low_margin_threshold_percent": DEFAULT_LOW_MARGIN_PERCENT,
			"invoice_count": len(header_map),
			"item_row_count": len(items),
		},
	}


def _assert_cost_visibility() -> None:
	if should_hide_cost_price():
		raise frappe.PermissionError(_("Your current RetailEdge cost-visibility policy does not allow profitability intelligence."))


def _get_costed_items(invoice_names: list[str]) -> list[frappe._dict]:
	if not invoice_names:
		return []
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", invoice_names], "parenttype": "Sales Invoice"},
		fields=[
			"parent",
			"item_code",
			"item_name",
			"item_group",
			"stock_qty",
			"base_net_amount",
			"incoming_rate",
		],
		order_by="parent asc, idx asc",
		limit=MAX_PROFITABILITY_ROWS + 1,
	)
	if len(rows) > MAX_PROFITABILITY_ROWS:
		frappe.throw(
			_("More than {0} sales item rows match this profitability scope. Narrow the date range or Branch before loading profitability intelligence.").format(
				MAX_PROFITABILITY_ROWS
			)
		)
	return rows


def _aggregate_items(items: list[frappe._dict]) -> list[dict[str, Any]]:
	aggregated: dict[str, dict[str, Any]] = defaultdict(dict)
	for row in items:
		item_code = str(row.get("item_code") or "").strip() or _("Unspecified Item")
		bucket = aggregated.get(item_code)
		if not bucket:
			bucket = {
				"item_code": item_code,
				"item_name": row.get("item_name") or item_code,
				"item_group": row.get("item_group") or "",
				"net_qty": 0.0,
				"net_sales": 0.0,
				"cost_of_sales": 0.0,
				"gross_profit": 0.0,
				"gross_margin_percent": 0.0,
				"invoice_count": 0,
				"_invoices": set(),
			}
			aggregated[item_code] = bucket

		stock_qty = flt(row.get("stock_qty"))
		net_sales = flt(row.get("base_net_amount"))
		cost_of_sales = flt(row.get("incoming_rate")) * stock_qty
		bucket["net_qty"] += stock_qty
		bucket["net_sales"] += net_sales
		bucket["cost_of_sales"] += cost_of_sales
		bucket["gross_profit"] += net_sales - cost_of_sales
		bucket["_invoices"].add(row.get("parent"))

	rows: list[dict[str, Any]] = []
	for bucket in aggregated.values():
		bucket["invoice_count"] = len(bucket.pop("_invoices"))
		bucket["gross_margin_percent"] = _margin_percent(bucket["gross_profit"], bucket["net_sales"])
		rows.append(bucket)
	rows.sort(key=lambda row: (-flt(row["net_sales"]), row["item_code"]))
	return rows


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
	net_sales = sum(flt(row.get("net_sales")) for row in rows)
	cost_of_sales = sum(flt(row.get("cost_of_sales")) for row in rows)
	gross_profit = net_sales - cost_of_sales
	return {
		"net_sales": net_sales,
		"cost_of_sales": cost_of_sales,
		"gross_profit": gross_profit,
		"gross_margin_percent": _margin_percent(gross_profit, net_sales),
		"negative_margin_items": sum(1 for row in rows if flt(row.get("gross_profit")) < 0),
		"low_margin_items": sum(1 for row in rows if flt(row.get("gross_margin_percent")) < DEFAULT_LOW_MARGIN_PERCENT),
	}


def _margin_percent(gross_profit: float, net_sales: float) -> float:
	return (flt(gross_profit) / flt(net_sales) * 100.0) if flt(net_sales) else 0.0
