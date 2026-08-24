from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.customer_sales_intelligence import _normalise_filters
from retailedge.profitability_intelligence import _margin_percent
from retailedge.sales_reporting import (
	DEFAULT_PAGE_SIZE,
	MAX_ITEM_SCAN_ROWS,
	MAX_PAGE_SIZE,
	_assert_report_access,
	_filter_headers_by_salesperson,
	_get_permitted_invoice_headers,
	_salespeople_by_invoice,
	_validate_filters,
)

DEFAULT_HIGH_REDUCTION_PERCENT = 10.0
DEFAULT_LOW_MARGIN_PERCENT = 10.0


@frappe.whitelist()
def get_sales_quality_intelligence(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	dataset = _build_sales_quality_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_sales_quality_intelligence_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	dataset = _build_sales_quality_dataset(filters)
	return {
		"title": dataset["title"],
		"columns": dataset["columns"],
		"rows": dataset["rows"],
		"summary": dataset["summary"],
		"metadata": dataset["metadata"],
		"scan": dataset["scan"],
	}


def _build_sales_quality_dataset(filters: dict[str, Any] | str | None) -> dict[str, Any]:
	filters = _normalise_filters(filters)
	filters.invoice_kind = "All"
	_validate_filters(filters)
	_assert_report_access(filters)

	headers = _get_permitted_invoice_headers(filters)
	headers = _filter_headers_by_salesperson(headers, filters.get("salesperson"))
	if any(filters.get(field) for field in ("item_code", "item_group", "warehouse")):
		matching_parents = _matching_invoice_parents([row.name for row in headers], filters)
		headers = [row for row in headers if row.name in matching_parents]

	sales_headers = [row for row in headers if not cint(row.get("is_return"))]
	return_headers = [row for row in headers if cint(row.get("is_return"))]
	sales_names = [str(row.name) for row in sales_headers]
	show_costs = not should_hide_cost_price()
	invoice_details = _get_invoice_discount_details(sales_names)
	item_rows = _get_sales_quality_items(sales_names, show_costs=show_costs)
	team_map = _salespeople_by_invoice(sales_names)

	rows = build_sales_quality_rows(
		sales_headers,
		invoice_details=invoice_details,
		items=item_rows,
		team_map=team_map,
		show_costs=show_costs,
		high_reduction_percent=max(flt(filters.get("high_reduction_percent") or DEFAULT_HIGH_REDUCTION_PERCENT), 0.0),
		low_margin_percent=flt(filters.get("low_margin_percent") or DEFAULT_LOW_MARGIN_PERCENT),
	)
	return_value = sum(abs(flt(row.get("base_net_total"))) for row in return_headers)
	return_count = len(return_headers)

	columns = _columns(show_costs)
	net_sales = sum(flt(row.get("net_sales")) for row in rows)
	reference_value = sum(flt(row.get("reference_value")) for row in rows)
	reduction = sum(flt(row.get("price_reduction")) for row in rows)
	summary = [
		{"label": _("Net Sales"), "value": net_sales, "datatype": "Currency"},
		{"label": _("Recorded Price Reduction"), "value": reduction, "datatype": "Currency"},
		{"label": _("Effective Reduction"), "value": (reduction / reference_value * 100.0) if reference_value > 0 else 0.0, "datatype": "Percent"},
		{"label": _("High Reduction Invoices"), "value": sum(1 for row in rows if row.get("high_reduction")), "datatype": "Int"},
		{"label": _("Returns"), "value": return_count, "datatype": "Int"},
		{"label": _("Return Value"), "value": return_value, "datatype": "Currency"},
	]
	if show_costs:
		gross_profit = sum(flt(row.get("gross_profit")) for row in rows)
		summary.extend(
			[
				{"label": _("Transactional Gross Profit"), "value": gross_profit, "datatype": "Currency"},
				{"label": _("Transactional Gross Margin"), "value": _margin_percent(gross_profit, net_sales), "datatype": "Percent"},
				{"label": _("Low / Negative Margin Invoices"), "value": sum(1 for row in rows if row.get("low_margin")), "datatype": "Int"},
			]
		)

	return {
		"title": _("Discount & Sales Quality"),
		"columns": columns,
		"rows": rows,
		"summary": summary,
		"show_costs": 1 if show_costs else 0,
		"scan": {"invoices": len(headers), "sale_invoices": len(sales_headers), "return_invoices": return_count, "item_rows": len(item_rows)},
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice / Sales Invoice Item",
			"additional_discount_truth": "Sales Invoice base_discount_amount and additional_discount_percentage",
			"reference_truth": "Sales Invoice Item base_rate_with_margin, falling back to base_price_list_rate",
			"reduction_definition": "Positive difference between recorded company-currency price-list-with-margin reference and submitted base_net_amount",
			"cost_truth": "Sales Invoice Item incoming_rate × stock_qty when RetailEdge cost visibility permits",
			"financial_truth": "ERPNext Profit and Loss remains financial profit truth",
			"returns": "Returns are reported separately and are not treated as discount leakage",
		},
	}


def _matching_invoice_parents(invoice_names: list[str], filters: frappe._dict) -> set[str]:
	if not invoice_names:
		return set()
	query_filters: dict[str, Any] = {"parenttype": "Sales Invoice", "parent": ["in", invoice_names]}
	if filters.get("item_code"):
		query_filters["item_code"] = filters.item_code
	if filters.get("item_group"):
		query_filters["item_group"] = filters.item_group
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters.warehouse
	rows = frappe.get_all("Sales Invoice Item", filters=query_filters, fields=["parent"], limit=MAX_ITEM_SCAN_ROWS + 1)
	if len(rows) > MAX_ITEM_SCAN_ROWS:
		frappe.throw(_("Too many Sales Invoice Item rows match this sales-quality scope. Narrow the filters."))
	return {str(row.parent) for row in rows}


def _get_invoice_discount_details(invoice_names: list[str]) -> dict[str, frappe._dict]:
	if not invoice_names:
		return {}
	rows = frappe.get_list(
		"Sales Invoice",
		filters={"name": ["in", invoice_names], "docstatus": 1},
		fields=["name", "base_discount_amount", "additional_discount_percentage"],
		limit=max(len(invoice_names), 1),
	)
	return {str(row.name): row for row in rows}


def _get_sales_quality_items(invoice_names: list[str], *, show_costs: bool) -> list[frappe._dict]:
	if not invoice_names:
		return []
	fields = [
		"parent",
		"item_code",
		"qty",
		"base_price_list_rate",
		"base_rate_with_margin",
		"discount_percentage",
		"distributed_discount_amount",
		"base_net_amount",
	]
	if show_costs:
		fields.extend(["stock_qty", "incoming_rate"])
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parenttype": "Sales Invoice", "parent": ["in", invoice_names]},
		fields=fields,
		order_by="parent asc, idx asc",
		limit=MAX_ITEM_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_ITEM_SCAN_ROWS:
		frappe.throw(_("More than {0} Sales Invoice Item rows match this sales-quality scope. Narrow the filters.").format(MAX_ITEM_SCAN_ROWS))
	return rows


def build_sales_quality_rows(
	headers: list[frappe._dict] | list[dict[str, Any]],
	*,
	invoice_details: dict[str, frappe._dict] | dict[str, dict[str, Any]],
	items: list[frappe._dict] | list[dict[str, Any]],
	team_map: dict[str, list[str]] | None = None,
	show_costs: bool,
	high_reduction_percent: float = DEFAULT_HIGH_REDUCTION_PERCENT,
	low_margin_percent: float = DEFAULT_LOW_MARGIN_PERCENT,
) -> list[dict[str, Any]]:
	item_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"reference_value": 0.0, "net_sales": 0.0, "cost_of_sales": 0.0, "discounted_lines": 0, "max_line_discount_percent": 0.0, "missing_reference_lines": 0})
	for item in items:
		invoice = str(item.get("parent") or "")
		if not invoice:
			continue
		bucket = item_buckets[invoice]
		qty = flt(item.get("qty"))
		reference_rate = flt(item.get("base_rate_with_margin")) or flt(item.get("base_price_list_rate"))
		reference_value = reference_rate * qty if qty > 0 and reference_rate > 0 else 0.0
		if reference_value <= 0 and flt(item.get("base_net_amount")) > 0:
			bucket["missing_reference_lines"] += 1
		bucket["reference_value"] += reference_value
		bucket["net_sales"] += flt(item.get("base_net_amount"))
		line_discount_percent = max(flt(item.get("discount_percentage")), 0.0)
		if line_discount_percent > 0 or flt(item.get("distributed_discount_amount")) > 0:
			bucket["discounted_lines"] += 1
		bucket["max_line_discount_percent"] = max(bucket["max_line_discount_percent"], line_discount_percent)
		if show_costs:
			bucket["cost_of_sales"] += flt(item.get("incoming_rate")) * flt(item.get("stock_qty"))

	team_map = team_map or {}
	rows: list[dict[str, Any]] = []
	for header in headers:
		invoice = str(header.get("name") or "")
		bucket = item_buckets.get(invoice) or {}
		detail = invoice_details.get(invoice) or {}
		reference_value = flt(bucket.get("reference_value"))
		net_sales = flt(bucket.get("net_sales"))
		price_reduction = max(reference_value - net_sales, 0.0) if reference_value > 0 else 0.0
		reduction_percent = (price_reduction / reference_value * 100.0) if reference_value > 0 else 0.0
		row = {
			"invoice": invoice,
			"posting_date": header.get("posting_date"),
			"customer": header.get("customer"),
			"customer_name": header.get("customer_name") or header.get("customer"),
			"branch": header.get("branch") or "",
			"salespeople": ", ".join(team_map.get(invoice, [])),
			"reference_value": reference_value,
			"net_sales": net_sales,
			"price_reduction": price_reduction,
			"effective_reduction_percent": reduction_percent,
			"additional_discount_amount": flt(detail.get("base_discount_amount")),
			"additional_discount_percent": flt(detail.get("additional_discount_percentage")),
			"discounted_lines": cint(bucket.get("discounted_lines")),
			"max_line_discount_percent": flt(bucket.get("max_line_discount_percent")),
			"missing_reference_lines": cint(bucket.get("missing_reference_lines")),
			"high_reduction": reduction_percent >= flt(high_reduction_percent) if reference_value > 0 else False,
		}
		if show_costs:
			cost = flt(bucket.get("cost_of_sales"))
			profit = net_sales - cost
			margin = _margin_percent(profit, net_sales)
			row.update({"cost_of_sales": cost, "gross_profit": profit, "gross_margin_percent": margin, "low_margin": net_sales > 0 and margin <= flt(low_margin_percent)})
		rows.append(row)
	rows.sort(key=lambda row: (-flt(row.get("effective_reduction_percent")), -flt(row.get("price_reduction")), str(row.get("invoice") or "")))
	return rows


def _columns(show_costs: bool) -> list[dict[str, Any]]:
	columns = [
		{"label": _("Sales Invoice"), "fieldname": "invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Data", "width": 120},
		{"label": _("Salespeople"), "fieldname": "salespeople", "fieldtype": "Data", "width": 160},
		{"label": _("Reference Value"), "fieldname": "reference_value", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 125},
		{"label": _("Price Reduction"), "fieldname": "price_reduction", "fieldtype": "Currency", "width": 130},
		{"label": _("Reduction %"), "fieldname": "effective_reduction_percent", "fieldtype": "Percent", "width": 105},
		{"label": _("Additional Discount"), "fieldname": "additional_discount_amount", "fieldtype": "Currency", "width": 135},
		{"label": _("Additional %"), "fieldname": "additional_discount_percent", "fieldtype": "Percent", "width": 105},
		{"label": _("Discounted Lines"), "fieldname": "discounted_lines", "fieldtype": "Int", "width": 105},
		{"label": _("Max Line %"), "fieldname": "max_line_discount_percent", "fieldtype": "Percent", "width": 100},
	]
	if show_costs:
		columns.extend(
			[
				{"label": _("Recorded Cost"), "fieldname": "cost_of_sales", "fieldtype": "Currency", "width": 120},
				{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
				{"label": _("Margin %"), "fieldname": "gross_margin_percent", "fieldtype": "Percent", "width": 100},
			]
		)
	return columns


def _page_response(dataset: dict[str, Any], *, page: int | str, page_size: int | str) -> dict[str, Any]:
	page = max(cint(page), 1)
	page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
	start = (page - 1) * page_size
	end = start + page_size
	total = len(dataset["rows"])
	return {**dataset, "rows": dataset["rows"][start:end], "pagination": {"page": page, "page_size": page_size, "total_rows": total, "has_previous": page > 1, "has_next": end < total}}
