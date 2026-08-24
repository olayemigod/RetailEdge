from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate

from retailedge.customer_receivables import _build_customer_receivables_dataset
from retailedge.customer_sales_intelligence import (
	_build_customer_sales_dataset,
	_get_first_purchase_dates,
	_normalise_filters,
)
from retailedge.sales_reporting import (
	MAX_ITEM_SCAN_ROWS,
	_assert_report_access,
	_company_currency,
	_get_invoice_items,
	_get_permitted_invoice_headers,
	_validate_filters,
)

MAX_RECENT_INVOICES = 25
MAX_TOP_ITEMS = 15


@frappe.whitelist()
def get_customer_360(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _normalise_filters(filters)
	_validate_customer_360_filters(resolved)
	_assert_report_access(resolved)

	customer = str(resolved.customer)
	master = _get_customer_master(customer)
	headers = _get_permitted_invoice_headers(resolved)
	period_dataset = _build_customer_sales_dataset(resolved)
	period_row = next((row for row in period_dataset.get("rows") or [] if row.get("customer") == customer), None)
	first_purchase = _get_first_purchase_dates(resolved, [customer]).get(customer)
	items = _get_invoice_items([row.name for row in headers], resolved)
	receivables = _customer_receivables(resolved)

	return {
		"title": _("Customer 360"),
		"customer": master,
		"relationship": _relationship_summary(
			first_purchase_date=first_purchase,
			headers=headers,
			to_date=resolved.to_date,
		),
		"period": _period_summary(period_row),
		"top_items": _top_items(headers, items),
		"recent_invoices": _recent_invoices(headers),
		"receivables": receivables,
		"company_currency": _company_currency(resolved.company),
		"show_profitability": cint(period_dataset.get("show_profitability")),
		"scope": {
			"company": resolved.company,
			"branch": str(resolved.get("branch") or ""),
			"customer": customer,
			"from_date": resolved.from_date,
			"to_date": resolved.to_date,
		},
		"scan": {
			"period_invoices": len(headers),
			"item_rows": len(items),
			"item_limit": MAX_ITEM_SCAN_ROWS,
		},
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice",
			"item_truth": "Submitted ERPNext Sales Invoice Item",
			"receivable_truth": "RetailEdge Customer Receivables using current ERPNext Sales Invoice outstanding balances",
			"profitability_truth": "R8 transactional profitability when RetailEdge cost visibility permits",
			"receivables_are_current_not_historical_as_of": True,
			"read_only": True,
		},
	}


def _validate_customer_360_filters(filters: frappe._dict) -> None:
	_validate_filters(filters)
	customer = str(filters.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required for Customer 360."))
	filters.customer = customer


def _get_customer_master(customer: str) -> dict[str, Any]:
	rows = frappe.get_list(
		"Customer",
		filters={"name": customer},
		fields=["name", "customer_name", "customer_group", "territory", "customer_type", "disabled"],
		limit=1,
	)
	if not rows:
		frappe.throw(_("Customer {0} does not exist or is not available to you.").format(customer), frappe.PermissionError)
	row = rows[0]
	return {
		"name": row.name,
		"customer_name": row.customer_name or row.name,
		"customer_group": row.customer_group or "",
		"territory": row.territory or "",
		"customer_type": row.customer_type or "",
		"disabled": cint(row.disabled),
	}


def _relationship_summary(
	*,
	first_purchase_date: str | None,
	headers: list[frappe._dict],
	to_date: str,
) -> dict[str, Any]:
	purchases = sorted(
		[
			str(row.posting_date)
			for row in headers
			if not cint(row.get("is_return")) and row.get("posting_date")
		]
	)
	last_purchase = purchases[-1] if purchases else None
	intervals = [
		date_diff(getdate(current), getdate(previous))
		for previous, current in zip(purchases, purchases[1:])
	]
	return {
		"first_purchase_date": first_purchase_date,
		"last_purchase_date": last_purchase,
		"days_since_last_purchase": date_diff(getdate(to_date), getdate(last_purchase)) if last_purchase else None,
		"period_purchase_count": len(purchases),
		"average_days_between_purchases": (sum(intervals) / len(intervals)) if intervals else None,
	}


def _period_summary(row: dict[str, Any] | None) -> dict[str, Any]:
	if not row:
		return {
			"sales_invoice_count": 0,
			"return_invoice_count": 0,
			"gross_sales": 0.0,
			"returns_value": 0.0,
			"net_sales": 0.0,
			"average_purchase_value": 0.0,
			"current_outstanding": 0.0,
			"overdue_outstanding": 0.0,
			"open_invoice_count": 0,
			"max_overdue_days": 0,
		}
	return {
		key: row.get(key)
		for key in (
			"segment",
			"sales_invoice_count",
			"return_invoice_count",
			"gross_sales",
			"returns_value",
			"net_sales",
			"average_purchase_value",
			"cost_of_sales",
			"gross_profit",
			"gross_margin_percent",
			"current_outstanding",
			"overdue_outstanding",
			"open_invoice_count",
			"max_overdue_days",
		)
		if key in row
	}


def _top_items(headers: list[frappe._dict], items: list[frappe._dict]) -> list[dict[str, Any]]:
	return aggregate_top_items(headers, items)[:MAX_TOP_ITEMS]


def aggregate_top_items(headers: list[frappe._dict], items: list[frappe._dict]) -> list[dict[str, Any]]:
	return_map = {str(row.name): cint(row.get("is_return")) for row in headers}
	buckets: dict[str, dict[str, Any]] = defaultdict(
		lambda: {
			"item_code": "",
			"item_name": "",
			"item_group": "",
			"net_qty": 0.0,
			"net_sales": 0.0,
			"invoice_count": 0,
			"_invoices": set(),
		}
	)
	for row in items:
		item_code = str(row.get("item_code") or "").strip()
		if not item_code:
			continue
		bucket = buckets[item_code]
		bucket["item_code"] = item_code
		bucket["item_name"] = str(row.get("item_name") or item_code)
		bucket["item_group"] = str(row.get("item_group") or "")
		invoice = str(row.get("parent") or "")
		is_return = return_map.get(invoice, 0)
		qty = abs(flt(row.get("qty")))
		value = abs(flt(row.get("base_net_amount")))
		if is_return:
			bucket["net_qty"] -= qty
			bucket["net_sales"] -= value
		else:
			bucket["net_qty"] += qty
			bucket["net_sales"] += value
		if invoice:
			bucket["_invoices"].add(invoice)

	rows = []
	for bucket in buckets.values():
		bucket["invoice_count"] = len(bucket.pop("_invoices", set()))
		rows.append(bucket)
	rows.sort(key=lambda row: (-flt(row.get("net_sales")), str(row.get("item_code") or "")))
	return rows


def _recent_invoices(headers: list[frappe._dict]) -> list[dict[str, Any]]:
	rows = []
	for row in headers:
		is_return = cint(row.get("is_return"))
		rows.append(
			{
				"invoice": row.name,
				"posting_date": row.posting_date,
				"type": _("Return") if is_return else _("Sale"),
				"net_amount": -abs(flt(row.base_net_total)) if is_return else flt(row.base_net_total),
				"grand_total": -abs(flt(row.base_grand_total)) if is_return else flt(row.base_grand_total),
				"outstanding": flt(row.outstanding_amount),
				"status": row.status or "",
				"return_against": row.return_against or "",
			}
		)
	rows.sort(key=lambda row: (str(row.get("posting_date") or ""), str(row.get("invoice") or "")), reverse=True)
	return rows[:MAX_RECENT_INVOICES]


def _customer_receivables(filters: frappe._dict) -> dict[str, Any]:
	dataset = _build_customer_receivables_dataset(
		frappe._dict(
			{
				"company": filters.company,
				"branch": str(filters.get("branch") or ""),
				"customer": filters.customer,
				"customer_group": "",
				"ageing_bucket": "All",
			}
		)
	)
	bucket_totals: dict[str, float] = defaultdict(float)
	rows = list(dataset.get("rows") or [])
	for row in rows:
		bucket_totals[str(row.get("ageing_bucket") or "Current")] += flt(row.get("outstanding"))
	return {
		"total_outstanding": sum(flt(row.get("outstanding")) for row in rows),
		"overdue_outstanding": sum(flt(row.get("outstanding")) for row in rows if cint(row.get("overdue_days")) > 0),
		"open_invoice_count": len(rows),
		"ageing": dict(bucket_totals),
		"rows": rows[:MAX_RECENT_INVOICES],
		"balance_date": dataset.get("current_balance_date"),
		"balance_basis": dataset.get("balance_basis"),
	}
