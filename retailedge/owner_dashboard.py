from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, today

from retailedge.branch_performance_dashboard import get_branch_performance_dashboard_data
from retailedge.cash_movement import get_cash_movement
from retailedge.customer_receivables import get_customer_receivables
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.expense_register import get_expense_register
from retailedge.profitability_intelligence import get_profitability_intelligence
from retailedge.sales_reporting import get_sales_invoice_register
from retailedge.stock_position import get_stock_position
from retailedge.supplier_payables import get_supplier_payables

DASHBOARD_KEY = "owner-dashboard"
DEFAULT_PAGE_SIZE = 1


@frappe.whitelist()
def get_owner_dashboard_context() -> dict[str, Any]:
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	capabilities = require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	return {
		"dashboard_key": DASHBOARD_KEY,
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"capabilities": capabilities,
		"sections": [
			"sales",
			"profitability",
			"expenses",
			"cash",
			"receivables",
			"payables",
			"stock",
			"branches",
		],
	}


@frappe.whitelist()
def get_owner_dashboard_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	from_date = str(filters.get("from_date") or get_first_day(today()))
	to_date = str(filters.get("to_date") or today())
	common = {"company": company, "branch": branch, "from_date": from_date, "to_date": to_date}

	sections = {
		"sales": _safe_section(
			"Sales",
			lambda: get_sales_invoice_register(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/sales-invoice-register",
		),
		"profitability": _safe_section(
			"Profitability",
			lambda: get_profitability_intelligence(filters=common),
			"/app/profitability-intelligence",
		),
		"expenses": _safe_section(
			"Expenses",
			lambda: get_expense_register(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/expense-register",
		),
		"cash": _safe_section(
			"Cash Movement",
			lambda: get_cash_movement(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/cash-movement",
		),
		"receivables": _safe_section(
			"Receivables",
			lambda: get_customer_receivables(
				filters={"company": company, "branch": branch}, page=1, page_size=DEFAULT_PAGE_SIZE
			),
			"/app/customer-receivables",
			time_basis="current",
		),
		"payables": _safe_section(
			"Payables",
			lambda: get_supplier_payables(
				filters={"company": company, "branch": branch}, page=1, page_size=DEFAULT_PAGE_SIZE
			),
			"/app/supplier-payables",
			time_basis="current",
		),
		"stock": _safe_section(
			"Stock Position",
			lambda: get_stock_position(
				filters={"company": company, "branch": branch}, page=1, page_size=DEFAULT_PAGE_SIZE
			),
			"/app/stock-position",
			time_basis="current",
		),
		"branches": _safe_section(
			"Branch Performance",
			lambda: get_branch_performance_dashboard_data(filters=common),
			"/app/branch-performance-dashboard",
		),
	}
	return {
		"title": _("Owner Dashboard"),
		"filters": common,
		"headline_summary": _headline_summary(sections),
		"attention": _attention_items(sections),
		"sections": sections,
		"metadata": {
			"composition": "existing_retailedge_reporting_engines_plus_profitability_intelligence",
			"accounting_truth": "ERPNext submitted/posted documents and existing RetailEdge control records",
			"period_sections": ["sales", "profitability", "expenses", "cash", "branches"],
			"current_sections": ["receivables", "payables", "stock"],
			"generated_for": frappe.session.user,
		},
	}


def build_owner_dashboard_export_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Flatten source summaries for the shared EdgeSuite dashboard export/print service."""
	result = get_owner_dashboard_data(filters)
	rows: list[dict[str, Any]] = []
	for key, section in (result.get("sections") or {}).items():
		if not section.get("available"):
			continue
		for card in section.get("summary") or []:
			rows.append(
				{
					"section": section.get("label") or key,
					"metric": card.get("label") or "",
					"basis": _("Current") if section.get("time_basis") == "current" else _("Selected Period"),
					"value": card.get("value"),
					"datatype": card.get("datatype") or card.get("type") or "Data",
				}
			)
	return {
		"title": _("Owner Dashboard"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 180},
			{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 220},
			{"fieldname": "basis", "label": _("Time Basis"), "fieldtype": "Data", "width": 150},
			{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 160},
		],
		"rows": rows,
		"summary": result.get("headline_summary") or [],
		"filters": result.get("filters") or {},
	}


def _headline_summary(sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	preferred = (
		("sales", "Net Invoiced", "Sales"),
		("profitability", "Gross Profit", "Gross Profit"),
		("profitability", "Gross Margin", "Gross Margin"),
		("expenses", "Total Expenses", "Expenses"),
		("receivables", "Total Receivables", "Receivables"),
		("payables", "Total Payables", "Payables"),
		("stock", "Stock Value", "Stock Value"),
	)
	cards: list[dict[str, Any]] = []
	for section_key, metric_label, display_label in preferred:
		card = _summary_card(sections.get(section_key), metric_label)
		if not card:
			continue
		section = sections.get(section_key) or {}
		cards.append(
			{
				**card,
				"label": _(display_label),
				"source_label": card.get("label"),
				"time_basis": section.get("time_basis") or "period",
			}
		)
	return cards


def _attention_items(sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	_rules = (
		("profitability", "Negative Margin Items", "danger", "Items are selling at negative margin", "/app/profitability-intelligence"),
		("profitability", "Low Margin Items", "warning", "Items are below the margin threshold", "/app/profitability-intelligence"),
		("expenses", "Posting Blocked", "danger", "Expense posting is blocked", "/app/expense-register"),
		("expenses", "Submitted for Review", "warning", "Expenses are awaiting review", "/app/expense-register"),
		("receivables", "Over 90 Days", "danger", "Receivables are over 90 days overdue", "/app/customer-receivables"),
		("receivables", "Overdue", "warning", "Customer balances are overdue", "/app/customer-receivables"),
		("payables", "Over 90 Days", "danger", "Supplier balances are over 90 days overdue", "/app/supplier-payables"),
		("payables", "Overdue", "warning", "Supplier balances are overdue", "/app/supplier-payables"),
		("stock", "Negative Stock", "danger", "Items have negative stock", "/app/stock-position"),
		("stock", "Out of Stock", "warning", "Items are out of stock", "/app/stock-position"),
		("stock", "Fully Reserved", "warning", "Stock is fully reserved", "/app/stock-position"),
	)
	seen: set[tuple[str, str]] = set()
	for section_key, metric_label, tone, message, route in _rules:
		card = _summary_card(sections.get(section_key), metric_label)
		if not card or flt(card.get("value")) <= 0:
			continue
		key = (section_key, metric_label)
		if key in seen:
			continue
		seen.add(key)
		section = sections.get(section_key) or {}
		items.append(
			{
				"section": section_key,
				"label": _(message),
				"metric": card.get("label") or metric_label,
				"value": card.get("value"),
				"datatype": card.get("datatype") or card.get("type") or "Data",
				"time_basis": section.get("time_basis") or "period",
				"tone": tone,
				"route": route,
			}
		)
	return items


def _summary_card(section: dict[str, Any] | None, label: str) -> dict[str, Any] | None:
	if not section or not section.get("available"):
		return None
	for card in section.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return dict(card)
	return None


def _safe_section(
	label: str,
	loader: Callable[[], dict[str, Any]],
	route: str,
	*,
	time_basis: str = "period",
) -> dict[str, Any]:
	try:
		payload = loader() or {}
		return {
			"available": True,
			"label": _(label),
			"route": route,
			"time_basis": time_basis,
			"summary": payload.get("summary") or [],
			"scope": payload.get("scope") or {},
			"show_costs": payload.get("show_costs"),
			"balance_basis": payload.get("balance_basis"),
			"ageing_date": payload.get("ageing_date") or payload.get("current_balance_date"),
			"messages": payload.get("messages") or [],
		}
	except frappe.PermissionError:
		return {
			"available": False,
			"label": _(label),
			"route": route,
			"time_basis": time_basis,
			"reason": _("Your current permissions do not allow this dashboard section."),
		}


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
