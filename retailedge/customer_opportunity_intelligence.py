from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate

from retailedge.customer_sales_intelligence import _get_receivable_exposure, _normalise_filters
from retailedge.sales_reporting import (
	_assert_report_access,
	_company_currency,
	_get_permitted_invoice_headers,
	_validate_filters,
)

DEFAULT_CHANGE_THRESHOLD_PERCENT = 25.0
MIN_CHANGE_THRESHOLD_PERCENT = 5.0
MAX_CHANGE_THRESHOLD_PERCENT = 90.0


@frappe.whitelist()
def get_customer_opportunity_intelligence(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	current_filters = _normalise_filters(filters)
	_validate_filters(current_filters)
	_assert_report_access(current_filters)
	threshold = _change_threshold(current_filters)

	prior_filters = _prior_period_filters(current_filters)
	current_headers = _get_permitted_invoice_headers(current_filters)
	prior_headers = _get_permitted_invoice_headers(prior_filters)
	customer_codes = sorted(
		{str(row.customer) for row in current_headers + prior_headers if row.get("customer")}
	)
	receivables = _get_receivable_exposure(current_filters)
	rows = build_comparison_rows(
		current_headers,
		prior_headers,
		receivables=receivables,
		change_threshold_percent=threshold,
	)
	rows.sort(key=_sort_key)
	currency = _company_currency(current_filters.company)

	return {
		"title": _("Customer Retention & Opportunity Intelligence"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": _summary(rows),
		"company_currency": currency,
		"scope": {
			"company": current_filters.company,
			"branch": str(current_filters.get("branch") or ""),
			"customer": str(current_filters.get("customer") or ""),
			"current_from_date": current_filters.from_date,
			"current_to_date": current_filters.to_date,
			"prior_from_date": prior_filters.from_date,
			"prior_to_date": prior_filters.to_date,
			"change_threshold_percent": threshold,
		},
		"scan": {
			"customers": len(customer_codes),
			"current_invoices": len(current_headers),
			"prior_invoices": len(prior_headers),
		},
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice",
			"comparison_basis": "Selected period versus the immediately preceding period of equal day length",
			"receivable_truth": "Current ERPNext outstanding exposure reused from RetailEdge Customer Receivables",
			"churn_claimed": False,
			"dormancy_claimed": False,
			"signal_rule": "Signals describe observed period behaviour only; they do not assert customer churn",
		},
	}


@frappe.whitelist()
def get_customer_opportunity_intelligence_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	result = get_customer_opportunity_intelligence(filters)
	return {
		"title": result["title"],
		"columns": result["columns"],
		"rows": result["rows"],
		"summary": result["summary"],
		"company_currency": result["company_currency"],
		"scope": result["scope"],
		"metadata": result["metadata"],
	}


def _change_threshold(filters: frappe._dict) -> float:
	value = flt(filters.get("change_threshold_percent") or DEFAULT_CHANGE_THRESHOLD_PERCENT)
	if value < MIN_CHANGE_THRESHOLD_PERCENT or value > MAX_CHANGE_THRESHOLD_PERCENT:
		frappe.throw(
			_("Change Threshold must be between {0}% and {1}%.").format(
				int(MIN_CHANGE_THRESHOLD_PERCENT), int(MAX_CHANGE_THRESHOLD_PERCENT)
			)
		)
	return value


def _prior_period_filters(current_filters: frappe._dict) -> frappe._dict:
	current_from = getdate(current_filters.from_date)
	current_to = getdate(current_filters.to_date)
	period_days = date_diff(current_to, current_from) + 1
	prior_to = add_days(current_from, -1)
	prior_from = add_days(prior_to, -(period_days - 1))
	prior = frappe._dict(dict(current_filters))
	prior.from_date = str(prior_from)
	prior.to_date = str(prior_to)
	prior.segment = "All"
	return prior


def build_comparison_rows(
	current_headers: list[frappe._dict],
	prior_headers: list[frappe._dict],
	*,
	receivables: dict[str, dict[str, Any]],
	change_threshold_percent: float = DEFAULT_CHANGE_THRESHOLD_PERCENT,
) -> list[dict[str, Any]]:
	current = _aggregate_period(current_headers)
	prior = _aggregate_period(prior_headers)
	customers = sorted(set(current) | set(prior))
	rows: list[dict[str, Any]] = []
	for customer in customers:
		current_row = current.get(customer) or _empty_period(customer)
		prior_row = prior.get(customer) or _empty_period(customer)
		receivable = receivables.get(customer) or {}
		value_change = _percent_change(current_row["net_sales"], prior_row["net_sales"])
		frequency_change = _percent_change(current_row["purchase_count"], prior_row["purchase_count"])
		signals = _signals(
			current_row=current_row,
			prior_row=prior_row,
			value_change_percent=value_change,
			frequency_change_percent=frequency_change,
			overdue_outstanding=flt(receivable.get("overdue_outstanding")),
			threshold=change_threshold_percent,
		)
		rows.append(
			{
				"customer": customer,
				"customer_name": current_row.get("customer_name") or prior_row.get("customer_name") or customer,
				"attention_status": _attention_status(signals),
				"signal_labels": "; ".join(str(signal.get("label") or "") for signal in signals if signal.get("label")),
				"signals": signals,
				"current_net_sales": flt(current_row["net_sales"]),
				"prior_net_sales": flt(prior_row["net_sales"]),
				"value_change_percent": value_change,
				"current_purchase_count": cint(current_row["purchase_count"]),
				"prior_purchase_count": cint(prior_row["purchase_count"]),
				"frequency_change_percent": frequency_change,
				"current_return_value": flt(current_row["returns_value"]),
				"prior_return_value": flt(prior_row["returns_value"]),
				"current_outstanding": flt(receivable.get("current_outstanding")),
				"overdue_outstanding": flt(receivable.get("overdue_outstanding")),
				"max_overdue_days": cint(receivable.get("max_overdue_days")),
			}
		)
	return rows


def _aggregate_period(headers: list[frappe._dict]) -> dict[str, dict[str, Any]]:
	result: dict[str, dict[str, Any]] = defaultdict(dict)
	for row in headers:
		customer = str(row.get("customer") or "")
		if not customer:
			continue
		bucket = result.get(customer)
		if not bucket:
			bucket = _empty_period(customer)
			bucket["customer_name"] = str(row.get("customer_name") or customer)
			result[customer] = bucket
		amount = flt(row.get("base_net_total"))
		if cint(row.get("is_return")):
			return_value = abs(amount)
			bucket["returns_value"] += return_value
			bucket["net_sales"] -= return_value
		else:
			bucket["gross_sales"] += amount
			bucket["net_sales"] += amount
			bucket["purchase_count"] += 1
	return dict(result)


def _empty_period(customer: str) -> dict[str, Any]:
	return {
		"customer": customer,
		"customer_name": customer,
		"purchase_count": 0,
		"gross_sales": 0.0,
		"returns_value": 0.0,
		"net_sales": 0.0,
	}


def _percent_change(current: float | int, prior: float | int) -> float | None:
	prior_value = flt(prior)
	if prior_value <= 0:
		return None
	return ((flt(current) - prior_value) / prior_value) * 100.0


def _signals(
	*,
	current_row: dict[str, Any],
	prior_row: dict[str, Any],
	value_change_percent: float | None,
	frequency_change_percent: float | None,
	overdue_outstanding: float,
	threshold: float,
) -> list[dict[str, Any]]:
	signals: list[dict[str, Any]] = []
	current_purchases = cint(current_row.get("purchase_count"))
	prior_purchases = cint(prior_row.get("purchase_count"))
	if prior_purchases > 0 and current_purchases == 0:
		signals.append(
			{
				"key": "no_current_purchase",
				"label": _("No purchase in current period"),
				"kind": "retention",
				"explanation": _("This customer purchased in the immediately preceding comparable period but has no submitted non-return sale in the selected period."),
			}
		)
	if value_change_percent is not None and value_change_percent <= -threshold:
		signals.append(
			{
				"key": "declining_value",
				"label": _("Sales value declined"),
				"kind": "retention",
				"explanation": _("Net sales are {0}% lower than the preceding comparable period.").format(abs(round(value_change_percent, 1))),
			}
		)
	if frequency_change_percent is not None and frequency_change_percent <= -threshold:
		signals.append(
			{
				"key": "declining_frequency",
				"label": _("Purchase frequency declined"),
				"kind": "retention",
				"explanation": _("Submitted purchase count is {0}% lower than the preceding comparable period.").format(abs(round(frequency_change_percent, 1))),
			}
		)
	if overdue_outstanding > 0:
		signals.append(
			{
				"key": "overdue_receivable",
				"label": _("Overdue balance needs follow-up"),
				"kind": "receivable",
				"explanation": _("The customer currently has overdue ERPNext receivable exposure."),
			}
		)
	if value_change_percent is not None and value_change_percent >= threshold:
		signals.append(
			{
				"key": "growing_value",
				"label": _("Sales value growing"),
				"kind": "opportunity",
				"explanation": _("Net sales are {0}% higher than the preceding comparable period.").format(round(value_change_percent, 1)),
			}
		)
	if frequency_change_percent is not None and frequency_change_percent >= threshold:
		signals.append(
			{
				"key": "growing_frequency",
				"label": _("Purchase frequency growing"),
				"kind": "opportunity",
				"explanation": _("Submitted purchase count is {0}% higher than the preceding comparable period.").format(round(frequency_change_percent, 1)),
			}
		)
	return signals


def _attention_status(signals: list[dict[str, Any]]) -> str:
	kinds = {str(signal.get("kind") or "") for signal in signals}
	if "retention" in kinds:
		return "Follow-up"
	if "receivable" in kinds:
		return "Receivable Follow-up"
	if "opportunity" in kinds:
		return "Opportunity"
	return "Stable"


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Customers Compared"), "value": len(rows), "datatype": "Int"},
		{"label": _("Retention Follow-up"), "value": sum(1 for row in rows if row.get("attention_status") == "Follow-up"), "datatype": "Int"},
		{"label": _("Receivable Follow-up"), "value": sum(1 for row in rows if row.get("attention_status") == "Receivable Follow-up"), "datatype": "Int"},
		{"label": _("Growth Opportunities"), "value": sum(1 for row in rows if row.get("attention_status") == "Opportunity"), "datatype": "Int"},
	]


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer"},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data"},
		{"fieldname": "attention_status", "label": _("Attention Status"), "fieldtype": "Data"},
		{"fieldname": "signal_labels", "label": _("Signals"), "fieldtype": "Data"},
		{"fieldname": "current_net_sales", "label": _("Current Net Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "prior_net_sales", "label": _("Prior Net Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "value_change_percent", "label": _("Value Change"), "fieldtype": "Percent"},
		{"fieldname": "current_purchase_count", "label": _("Current Purchases"), "fieldtype": "Int"},
		{"fieldname": "prior_purchase_count", "label": _("Prior Purchases"), "fieldtype": "Int"},
		{"fieldname": "frequency_change_percent", "label": _("Frequency Change"), "fieldtype": "Percent"},
		{"fieldname": "current_return_value", "label": _("Current Returns"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "current_outstanding", "label": _("Current Outstanding"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "overdue_outstanding", "label": _("Overdue"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "max_overdue_days", "label": _("Oldest Overdue Days"), "fieldtype": "Int"},
	]


def _sort_key(row: dict[str, Any]):
	priority = {"Follow-up": 0, "Receivable Follow-up": 1, "Opportunity": 2, "Stable": 3}
	return (
		priority.get(str(row.get("attention_status") or "Stable"), 4),
		-flt(row.get("overdue_outstanding")),
		-flt(row.get("prior_net_sales")),
		str(row.get("customer_name") or row.get("customer") or ""),
	)
