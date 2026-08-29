from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, get_first_day, getdate, nowdate

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.customer_receivables import _build_customer_receivables_dataset
from retailedge.profitability_intelligence import _get_costed_items, _margin_percent
from retailedge.sales_reporting import (
	DEFAULT_PAGE_SIZE,
	MAX_INVOICE_SCAN_ROWS,
	MAX_PAGE_SIZE,
	_assert_report_access,
	_coerce_filters,
	_company_currency,
	_get_permitted_invoice_headers,
	_invoice_branch_scope,
	_validate_filters,
)

SEGMENT_NEW = "New"
SEGMENT_RETURNING = "Returning"


@frappe.whitelist()
def get_customer_sales_intelligence(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	resolved = _normalise_filters(filters)
	dataset = _build_customer_sales_dataset(resolved)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_customer_sales_intelligence_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	resolved = _normalise_filters(filters)
	dataset = _build_customer_sales_dataset(resolved)
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
	resolved.from_date = str(resolved.get("from_date") or get_first_day(nowdate()))
	resolved.to_date = str(resolved.get("to_date") or nowdate())
	resolved.invoice_kind = "All"
	return resolved


def _build_customer_sales_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters)
	customer_codes = sorted({str(row.customer) for row in headers if row.get("customer")})
	first_purchase_dates = _get_first_purchase_dates(filters, customer_codes)
	receivables = _get_receivable_exposure(filters)
	show_profitability = not should_hide_cost_price()
	profitability = _get_customer_profitability(headers) if show_profitability else {}
	rows = _aggregate_customer_rows(
		headers,
		first_purchase_dates=first_purchase_dates,
		receivables=receivables,
		profitability=profitability,
		from_date=filters.from_date,
		to_date=filters.to_date,
		show_profitability=show_profitability,
	)

	segment = str(filters.get("segment") or "All").strip()
	if segment not in {"All", SEGMENT_NEW, SEGMENT_RETURNING}:
		frappe.throw(_("Customer Segment must be All, New, or Returning."))
	if segment != "All":
		rows = [row for row in rows if row["segment"] == segment]

	rows.sort(key=lambda row: (-flt(row["net_sales"]), str(row["customer_name"]), str(row["customer"])))
	currency = _company_currency(filters.company)
	return {
		"title": _("Customer & Sales Intelligence"),
		"columns": _columns(currency, show_profitability=show_profitability),
		"rows": rows,
		"summary": _summary(rows, show_profitability=show_profitability),
		"company_currency": currency,
		"show_profitability": cint(show_profitability),
		"scope": {
			"company": filters.company,
			"branch": str(filters.get("branch") or ""),
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"customer": str(filters.get("customer") or ""),
			"segment": segment,
		},
		"scan": {"period_invoices": len(headers), "invoice_limit": MAX_INVOICE_SCAN_ROWS},
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice",
			"customer_status_truth": "Earliest submitted non-return Sales Invoice in the same company/branch access scope",
			"receivable_truth": "RetailEdge Customer Receivables using current ERPNext Sales Invoice outstanding balances",
			"profitability_truth": "R8 transactional profitability: Sales Invoice Item incoming_rate × stock_qty",
			"average_purchase_value_basis": "Submitted non-return sales value divided by submitted non-return invoice count",
			"returns_treatment": "Returns reduce net sales but do not establish first purchase status",
			"profitability_hidden_when_cost_restricted": True,
		},
	}


def _get_first_purchase_dates(filters: frappe._dict, customer_codes: list[str]) -> dict[str, str]:
	if not customer_codes:
		return {}
	branch_field, branch_condition = _invoice_branch_scope(filters)
	query_filters: dict[str, Any] = {
		"docstatus": 1,
		"company": filters.company,
		"is_return": 0,
		"posting_date": ["<=", filters.to_date],
		"customer": ["in", customer_codes],
	}
	if branch_field and branch_condition is not None:
		query_filters[branch_field] = branch_condition
	rows = frappe.get_list(
		"Sales Invoice",
		filters=query_filters,
		fields=["customer", "min(posting_date) as first_purchase_date"],
		group_by="customer",
		order_by="customer asc",
		limit=min(len(customer_codes), MAX_INVOICE_SCAN_ROWS) + 1,
	)
	if len(rows) > MAX_INVOICE_SCAN_ROWS:
		frappe.throw(_("Too many customers match this intelligence scope. Narrow the date range or Customer filter."))
	return {
		str(row.customer): str(row.first_purchase_date)
		for row in rows
		if row.get("customer") and row.get("first_purchase_date")
	}


def _get_receivable_exposure(filters: frappe._dict) -> dict[str, dict[str, Any]]:
	receivable_filters = frappe._dict(
		{
			"company": filters.company,
			"branch": str(filters.get("branch") or ""),
			"customer": str(filters.get("customer") or ""),
			"customer_group": "",
			"ageing_bucket": "All",
		}
	)
	dataset = _build_customer_receivables_dataset(receivable_filters)
	result: dict[str, dict[str, Any]] = defaultdict(
		lambda: {"current_outstanding": 0.0, "overdue_outstanding": 0.0, "open_invoice_count": 0, "max_overdue_days": 0}
	)
	for row in dataset.get("rows") or []:
		customer = str(row.get("customer") or "")
		if not customer:
			continue
		bucket = result[customer]
		outstanding = flt(row.get("outstanding"))
		bucket["current_outstanding"] += outstanding
		bucket["open_invoice_count"] += 1
		overdue_days = max(cint(row.get("overdue_days")), 0)
		bucket["max_overdue_days"] = max(bucket["max_overdue_days"], overdue_days)
		if overdue_days > 0:
			bucket["overdue_outstanding"] += outstanding
	return dict(result)


def _get_customer_profitability(headers: list[frappe._dict]) -> dict[str, dict[str, float]]:
	if not headers:
		return {}
	header_map = {str(row.name): str(row.customer or "") for row in headers}
	items = _get_costed_items(list(header_map))
	result: dict[str, dict[str, float]] = defaultdict(lambda: {"cost_of_sales": 0.0, "gross_profit": 0.0})
	for row in items:
		customer = header_map.get(str(row.get("parent") or ""), "")
		if not customer:
			continue
		net_sales = flt(row.get("base_net_amount"))
		cost = flt(row.get("incoming_rate")) * flt(row.get("stock_qty"))
		result[customer]["cost_of_sales"] += cost
		result[customer]["gross_profit"] += net_sales - cost
	return dict(result)


def _aggregate_customer_rows(
	headers: list[frappe._dict],
	*,
	first_purchase_dates: dict[str, str],
	receivables: dict[str, dict[str, Any]],
	profitability: dict[str, dict[str, float]],
	from_date: str,
	to_date: str,
	show_profitability: bool,
) -> list[dict[str, Any]]:
	buckets: dict[str, dict[str, Any]] = {}
	for row in headers:
		customer = str(row.get("customer") or "")
		if not customer:
			continue
		bucket = buckets.setdefault(
			customer,
			{
				"customer": customer,
				"customer_name": str(row.get("customer_name") or customer),
				"sales_invoice_count": 0,
				"return_invoice_count": 0,
				"gross_sales": 0.0,
				"returns_value": 0.0,
				"net_sales": 0.0,
				"last_purchase_date": None,
			},
		)
		amount = flt(row.get("base_net_total"))
		is_return = cint(row.get("is_return"))
		if is_return:
			return_value = abs(amount)
			bucket["return_invoice_count"] += 1
			bucket["returns_value"] += return_value
			bucket["net_sales"] -= return_value
		else:
			bucket["sales_invoice_count"] += 1
			bucket["gross_sales"] += amount
			bucket["net_sales"] += amount
			posting_date = str(row.get("posting_date") or "")
			if posting_date and (not bucket["last_purchase_date"] or posting_date > bucket["last_purchase_date"]):
				bucket["last_purchase_date"] = posting_date

	rows: list[dict[str, Any]] = []
	for customer, bucket in buckets.items():
		first_purchase_date = first_purchase_dates.get(customer)
		segment = classify_customer_segment(first_purchase_date, from_date)
		last_purchase = bucket.get("last_purchase_date")
		receivable = receivables.get(customer) or {}
		row = {
			**bucket,
			"first_purchase_date": first_purchase_date,
			"segment": segment,
			"average_purchase_value": (
				flt(bucket["gross_sales"]) / cint(bucket["sales_invoice_count"])
				if cint(bucket["sales_invoice_count"]) > 0
				else 0.0
			),
			"days_since_last_purchase": date_diff(getdate(to_date), getdate(last_purchase)) if last_purchase else None,
			"current_outstanding": flt(receivable.get("current_outstanding")),
			"overdue_outstanding": flt(receivable.get("overdue_outstanding")),
			"open_invoice_count": cint(receivable.get("open_invoice_count")),
			"max_overdue_days": cint(receivable.get("max_overdue_days")),
		}
		if show_profitability:
			profit = profitability.get(customer) or {}
			row["cost_of_sales"] = flt(profit.get("cost_of_sales"))
			row["gross_profit"] = flt(profit.get("gross_profit"))
			row["gross_margin_percent"] = _margin_percent(row["gross_profit"], row["net_sales"])
		rows.append(row)
	return rows


def classify_customer_segment(first_purchase_date: str | None, from_date: str) -> str:
	if first_purchase_date and getdate(first_purchase_date) >= getdate(from_date):
		return SEGMENT_NEW
	return SEGMENT_RETURNING


def _summary(rows: list[dict[str, Any]], *, show_profitability: bool) -> list[dict[str, Any]]:
	sales_invoices = sum(cint(row.get("sales_invoice_count")) for row in rows)
	gross_sales = sum(flt(row.get("gross_sales")) for row in rows)
	summary = [
		{"label": _("Customers"), "value": len(rows), "datatype": "Int"},
		{"label": _("New Customers"), "value": sum(1 for row in rows if row.get("segment") == SEGMENT_NEW), "datatype": "Int"},
		{"label": _("Returning Customers"), "value": sum(1 for row in rows if row.get("segment") == SEGMENT_RETURNING), "datatype": "Int"},
		{"label": _("Net Sales"), "value": sum(flt(row.get("net_sales")) for row in rows), "datatype": "Currency"},
		{"label": _("Average Purchase Value"), "value": gross_sales / sales_invoices if sales_invoices else 0.0, "datatype": "Currency"},
		{"label": _("Current Outstanding"), "value": sum(flt(row.get("current_outstanding")) for row in rows), "datatype": "Currency"},
		{"label": _("Overdue Outstanding"), "value": sum(flt(row.get("overdue_outstanding")) for row in rows), "datatype": "Currency"},
	]
	if show_profitability:
		summary.extend(
		[
			{"label": _("Transactional Gross Profit"), "value": sum(flt(row.get("gross_profit")) for row in rows), "datatype": "Currency"},
			{
				"label": _("Transactional Gross Margin"),
				"value": _margin_percent(
					sum(flt(row.get("gross_profit")) for row in rows),
					sum(flt(row.get("net_sales")) for row in rows),
				),
				"datatype": "Percent",
			},
		]
		)
	return summary


def _columns(currency: str, *, show_profitability: bool) -> list[dict[str, Any]]:
	columns = [
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer"},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data"},
		{"fieldname": "segment", "label": _("Customer Segment"), "fieldtype": "Data"},
		{"fieldname": "first_purchase_date", "label": _("First Purchase"), "fieldtype": "Date"},
		{"fieldname": "last_purchase_date", "label": _("Last Purchase"), "fieldtype": "Date"},
		{"fieldname": "days_since_last_purchase", "label": _("Days Since Purchase"), "fieldtype": "Int"},
		{"fieldname": "sales_invoice_count", "label": _("Sales"), "fieldtype": "Int"},
		{"fieldname": "return_invoice_count", "label": _("Returns"), "fieldtype": "Int"},
		{"fieldname": "gross_sales", "label": _("Sales Value"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "returns_value", "label": _("Returns Value"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "net_sales", "label": _("Net Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "average_purchase_value", "label": _("Average Purchase Value"), "fieldtype": "Currency", "options": currency},
	]
	if show_profitability:
		columns.extend(
			[
				{"fieldname": "cost_of_sales", "label": _("Recorded Item Cost"), "fieldtype": "Currency", "options": currency},
				{"fieldname": "gross_profit", "label": _("Transactional Gross Profit"), "fieldtype": "Currency", "options": currency},
				{"fieldname": "gross_margin_percent", "label": _("Gross Margin"), "fieldtype": "Percent"},
			]
		)
	columns.extend(
		[
			{"fieldname": "current_outstanding", "label": _("Current Outstanding"), "fieldtype": "Currency", "options": currency},
			{"fieldname": "overdue_outstanding", "label": _("Overdue"), "fieldtype": "Currency", "options": currency},
			{"fieldname": "open_invoice_count", "label": _("Open Invoices"), "fieldtype": "Int"},
			{"fieldname": "max_overdue_days", "label": _("Oldest Overdue Days"), "fieldtype": "Int"},
		]
	)
	return columns


def _page_response(dataset: dict[str, Any], *, page: int | str, page_size: int | str) -> dict[str, Any]:
	rows = list(dataset.get("rows") or [])
	resolved_page_size = max(25, min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	resolved_page = max(cint(page), 1)
	total_rows = len(rows)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	resolved_page = min(resolved_page, total_pages)
	start = (resolved_page - 1) * resolved_page_size
	return {
		**dataset,
		"rows": rows[start : start + resolved_page_size],
		"pagination": {
			"page": resolved_page,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": resolved_page > 1,
			"has_next": resolved_page < total_pages,
		},
	}
