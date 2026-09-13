from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.sales_reporting import (
	get_sales_by_item,
	get_sales_invoice_register,
	get_sales_reporting_context,
)

DASHBOARD_KEY = "sales-overview"
PREVIEW_ROWS = 8


@frappe.whitelist()
def get_sales_dashboard_context() -> dict[str, Any]:
	context = get_sales_reporting_context()
	filters = context.get("default_filters") or {}
	context["dashboard_key"] = DASHBOARD_KEY
	context["capabilities"] = require_dashboard_action(
		DASHBOARD_KEY,
		"view",
		company=filters.get("company") or "",
		branch=filters.get("branch") or "",
	)
	return context


@frappe.whitelist()
def get_sales_dashboard_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)

	invoice_register = get_sales_invoice_register(filters=filters, page=1, page_size=PREVIEW_ROWS)
	by_item = get_sales_by_item(filters=filters, page=1, page_size=PREVIEW_ROWS)

	return {
		"title": _("Sales Overview"),
		"filters": dict(filters),
		"headline_summary": _headline_summary(invoice_register, by_item),
		"attention": _attention_items(invoice_register),
		"recent_invoices": invoice_register.get("rows") or [],
		"invoice_columns": invoice_register.get("columns") or [],
		"top_items": by_item.get("rows") or [],
		"item_columns": by_item.get("columns") or [],
		"routes": {
			"invoice_register": "/app/sales-invoice-register",
			"sales_by_item": "/app/sales-by-item",
			"salesperson_performance": "/app/salesperson-performance-dashboard",
			"branch_performance": "/app/branch-performance-dashboard",
		},
		"metadata": {
			"composition": "existing_sales_reporting_engines",
			"invoice_source": "Sales Invoice Register",
			"item_source": "Sales by Item",
			"accounting_truth": "Submitted ERPNext Sales Invoices and Sales Invoice Items",
		},
	}


def _headline_summary(invoice_register: dict[str, Any], by_item: dict[str, Any]) -> list[dict[str, Any]]:
	cards: list[dict[str, Any]] = []
	for source, label, display_label in (
		(invoice_register, "Net Invoiced", "Net Invoiced"),
		(invoice_register, "Invoices", "Invoices"),
		(invoice_register, "Returns", "Returns"),
		(invoice_register, "Net Outstanding", "Outstanding"),
		(by_item, "Net Quantity", "Net Quantity"),
	):
		card = _summary_card(source, label)
		if card:
			cards.append({**card, "label": _(display_label), "source_label": card.get("label")})
	return cards


def _attention_items(invoice_register: dict[str, Any]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for label, tone, message in (
		("Returns", "warning", "Sales returns were recorded in the selected period"),
		("Net Outstanding", "warning", "Submitted sales invoices still have outstanding balances"),
	):
		card = _summary_card(invoice_register, label)
		if not card or flt(card.get("value")) <= 0:
			continue
		items.append(
			{
				"label": _(message),
				"metric": card.get("label") or label,
				"value": card.get("value"),
				"datatype": card.get("datatype") or "Data",
				"tone": tone,
				"route": "/app/sales-invoice-register",
			}
		)
	return items


def build_sales_dashboard_export_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	result = get_sales_dashboard_data(filters)
	rows: list[dict[str, Any]] = []
	for card in result.get("headline_summary") or []:
		rows.append(
			{
				"section": _("Headline"),
				"metric": card.get("label") or "",
				"value": card.get("value"),
				"datatype": card.get("datatype") or "Data",
			}
		)
	for row in result.get("top_items") or []:
		rows.append(
			{
				"section": _("Top Items"),
				"metric": row.get("item_name") or row.get("item_code") or "",
				"value": row.get("net_sales"),
				"datatype": "Currency",
			}
		)
	return {
		"title": _("Sales Overview"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 160},
			{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 220},
			{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 160},
		],
		"rows": rows,
		"summary": result.get("headline_summary") or [],
		"filters": result.get("filters") or {},
	}


def _summary_card(payload: dict[str, Any], label: str) -> dict[str, Any] | None:
	for card in payload.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return dict(card)
	return None


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
