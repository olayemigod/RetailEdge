from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, get_first_day, getdate, today

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
	filters = _normalise_filters(filters)
	_validate_filters(filters)
	_assert_report_access(filters)
	_assert_cost_visibility()

	current = _build_period(filters)
	previous_filters = _previous_period_filters(filters)
	previous = _build_period(previous_filters)
	comparison = _build_comparison(current["totals"], previous["totals"], previous_filters)
	currency = _company_currency(filters.company)

	return {
		"summary": _summary_cards(current["totals"]),
		"rows": current["item_rows"],
		"dimensions": current["dimensions"],
		"top_contributors": sorted(
			current["item_rows"], key=lambda row: (-flt(row["gross_profit"]), row["item_code"])
		)[:10],
		"margin_leakage": sorted(
			[row for row in current["item_rows"] if flt(row["gross_margin_percent"]) < DEFAULT_LOW_MARGIN_PERCENT],
			key=lambda row: (flt(row["gross_margin_percent"]), -abs(flt(row["net_sales"]))),
		)[:25],
		"comparison": comparison,
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
			"salesperson_truth": "ERPNext Sales Team allocated_percentage",
			"low_margin_threshold_percent": DEFAULT_LOW_MARGIN_PERCENT,
			"invoice_count": current["invoice_count"],
			"item_row_count": current["item_row_count"],
			"comparison_basis": "immediately preceding equal-length period",
		},
	}


def _normalise_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	filters = _coerce_filters(filters)
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	filters.from_date = str(filters.get("from_date") or get_first_day(today()))
	filters.to_date = str(filters.get("to_date") or today())
	return filters


def _build_period(filters: frappe._dict) -> dict[str, Any]:
	headers = _get_permitted_invoice_headers(filters)
	invoice_names = [row.name for row in headers]
	header_map = _get_invoice_dimension_metadata(invoice_names)
	sales_allocations = _get_sales_allocations(invoice_names)
	items = _get_costed_items(invoice_names)
	item_rows = _aggregate_items(items)
	totals = _totals(item_rows)
	return {
		"totals": totals,
		"item_rows": item_rows,
		"dimensions": _build_dimensions(items, header_map, sales_allocations),
		"invoice_count": len(invoice_names),
		"item_row_count": len(items),
	}


def _get_invoice_dimension_metadata(invoice_names: list[str]) -> dict[str, frappe._dict]:
	if not invoice_names:
		return {}
	rows = frappe.get_list(
		"Sales Invoice",
		filters={"name": ["in", invoice_names], "docstatus": 1},
		fields=["name", "customer", "customer_name", "branch"],
		limit=max(len(invoice_names), 1),
	)
	return {row.name: row for row in rows}


def _get_sales_allocations(invoice_names: list[str]) -> dict[str, list[tuple[str, float]]]:
	if not invoice_names:
		return {}
	rows = frappe.get_all(
		"Sales Team",
		filters={"parent": ["in", invoice_names], "parenttype": "Sales Invoice"},
		fields=["parent", "sales_person", "allocated_percentage"],
		order_by="parent asc, idx asc",
	)
	by_invoice: dict[str, list[frappe._dict]] = defaultdict(list)
	for row in rows:
		if row.get("sales_person"):
			by_invoice[str(row.parent)].append(row)

	allocations: dict[str, list[tuple[str, float]]] = {}
	for invoice, team in by_invoice.items():
		total_percent = sum(max(flt(row.get("allocated_percentage")), 0.0) for row in team)
		if total_percent > 0:
			allocations[invoice] = [
				(str(row.sales_person), max(flt(row.get("allocated_percentage")), 0.0) / total_percent)
				for row in team
				if flt(row.get("allocated_percentage")) > 0
			]
		else:
			weight = 1.0 / len(team)
			allocations[invoice] = [(str(row.sales_person), weight) for row in team]
	return allocations


def _previous_period_filters(filters: frappe._dict) -> frappe._dict:
	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	period_days = max(date_diff(to_date, from_date) + 1, 1)
	previous_to = add_days(from_date, -1)
	previous_from = add_days(previous_to, -(period_days - 1))
	return frappe._dict({**dict(filters), "from_date": str(previous_from), "to_date": str(previous_to)})


def _build_comparison(
	current: dict[str, Any], previous: dict[str, Any], previous_filters: frappe._dict
) -> dict[str, Any]:
	metrics = []
	for key, label, datatype in (
		("net_sales", "Net Sales", "Currency"),
		("gross_profit", "Gross Profit", "Currency"),
		("gross_margin_percent", "Gross Margin", "Percent"),
	):
		current_value = flt(current.get(key))
		previous_value = flt(previous.get(key))
		change = current_value - previous_value
		change_percent = (change / abs(previous_value) * 100.0) if previous_value else None
		metrics.append(
			{
				"key": key,
				"label": _(label),
				"datatype": datatype,
				"current": current_value,
				"previous": previous_value,
				"change": change,
				"change_percent": change_percent,
			}
		)
	return {
		"previous_from_date": previous_filters.from_date,
		"previous_to_date": previous_filters.to_date,
		"metrics": metrics,
	}


def _summary_cards(totals: dict[str, Any]) -> list[dict[str, Any]]:
	return [
		{"label": _("Net Sales"), "value": totals["net_sales"], "datatype": "Currency"},
		{"label": _("Cost of Sales"), "value": totals["cost_of_sales"], "datatype": "Currency"},
		{"label": _("Gross Profit"), "value": totals["gross_profit"], "datatype": "Currency"},
		{"label": _("Gross Margin"), "value": totals["gross_margin_percent"], "datatype": "Percent"},
		{"label": _("Negative Margin Items"), "value": totals["negative_margin_items"], "datatype": "Int"},
		{"label": _("Low Margin Items"), "value": totals["low_margin_items"], "datatype": "Int"},
	]


def _assert_cost_visibility() -> None:
	if should_hide_cost_price():
		raise frappe.PermissionError(
			_("Your current RetailEdge cost-visibility policy does not allow profitability intelligence.")
		)


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
			_(
				"More than {0} sales item rows match this profitability scope. Narrow the date range or Branch before loading profitability intelligence."
			).format(MAX_PROFITABILITY_ROWS)
		)
	return rows


def _aggregate_items(items: list[frappe._dict]) -> list[dict[str, Any]]:
	aggregated: dict[str, dict[str, Any]] = defaultdict(dict)
	for row in items:
		item_code = str(row.get("item_code") or "").strip() or _("Unspecified Item")
		bucket = aggregated.get(item_code)
		if not bucket:
			bucket = _new_bucket(
				item_code,
				item_name=row.get("item_name") or item_code,
				item_group=row.get("item_group") or "",
			)
			aggregated[item_code] = bucket
		_add_to_bucket(bucket, row, row.get("parent"))

	rows = [_finalise_bucket(bucket) for bucket in aggregated.values()]
	rows.sort(key=lambda row: (-flt(row["net_sales"]), row["item_code"]))
	return rows


def _build_dimensions(
	items: list[frappe._dict],
	header_map: dict[str, frappe._dict],
	sales_allocations: dict[str, list[tuple[str, float]]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
	branch_buckets: dict[str, dict[str, Any]] = {}
	group_buckets: dict[str, dict[str, Any]] = {}
	customer_buckets: dict[str, dict[str, Any]] = {}
	salesperson_buckets: dict[str, dict[str, Any]] = {}
	sales_allocations = sales_allocations or {}

	for row in items:
		invoice = str(row.get("parent") or "")
		header = header_map.get(invoice) or frappe._dict()
		branch = str(header.get("branch") or _("Unassigned Branch"))
		customer = str(header.get("customer_name") or header.get("customer") or _("Unspecified Customer"))
		item_group = str(row.get("item_group") or _("Unspecified Item Group"))
		for buckets, key in (
			(branch_buckets, branch),
			(group_buckets, item_group),
			(customer_buckets, customer),
		):
			bucket = buckets.setdefault(key, _new_bucket(key))
			_add_to_bucket(bucket, row, invoice)

		allocations = sales_allocations.get(invoice) or [(_("Unassigned Salesperson"), 1.0)]
		for salesperson, weight in allocations:
			bucket = salesperson_buckets.setdefault(salesperson, _new_bucket(salesperson))
			_add_to_bucket(bucket, row, invoice, weight=weight)

	return {
		"branch": _dimension_rows(branch_buckets),
		"item_group": _dimension_rows(group_buckets),
		"customer": _dimension_rows(customer_buckets),
		"salesperson": _dimension_rows(salesperson_buckets),
	}


def _new_bucket(key: str, **extra: Any) -> dict[str, Any]:
	return {
		"key": key,
		"item_code": key,
		"net_qty": 0.0,
		"net_sales": 0.0,
		"cost_of_sales": 0.0,
		"gross_profit": 0.0,
		"gross_margin_percent": 0.0,
		"invoice_count": 0,
		"_invoices": set(),
		**extra,
	}


def _add_to_bucket(
	bucket: dict[str, Any], row: frappe._dict, invoice: str | None, *, weight: float = 1.0
) -> None:
	weight = flt(weight)
	stock_qty = flt(row.get("stock_qty")) * weight
	net_sales = flt(row.get("base_net_amount")) * weight
	cost_of_sales = flt(row.get("incoming_rate")) * flt(row.get("stock_qty")) * weight
	bucket["net_qty"] += stock_qty
	bucket["net_sales"] += net_sales
	bucket["cost_of_sales"] += cost_of_sales
	bucket["gross_profit"] += net_sales - cost_of_sales
	if invoice:
		bucket["_invoices"].add(invoice)


def _finalise_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
	bucket["invoice_count"] = len(bucket.pop("_invoices", set()))
	bucket["gross_margin_percent"] = _margin_percent(bucket["gross_profit"], bucket["net_sales"])
	return bucket


def _dimension_rows(buckets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	rows = [_finalise_bucket(bucket) for bucket in buckets.values()]
	rows.sort(key=lambda row: (-flt(row["gross_profit"]), str(row.get("key") or "")))
	return rows[:25]


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
		"low_margin_items": sum(
			1 for row in rows if flt(row.get("gross_margin_percent")) < DEFAULT_LOW_MARGIN_PERCENT
		),
	}


def _margin_percent(gross_profit: float, net_sales: float) -> float:
	return (flt(gross_profit) / flt(net_sales) * 100.0) if flt(net_sales) else 0.0
