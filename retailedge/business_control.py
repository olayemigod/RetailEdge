from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, today

from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.owner_dashboard import get_owner_dashboard_data

DASHBOARD_KEY = "owner-dashboard"


@frappe.whitelist()
def get_business_control_context() -> dict[str, Any]:
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	capabilities = require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	return {
		"title": _("Business Control Centre"),
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
		},
		"capabilities": capabilities,
		"source_contract": "existing_retailedge_reporting_engines_via_owner_dashboard",
	}


@frappe.whitelist()
def get_business_control_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)

	resolved = {
		"company": company,
		"branch": branch,
		"from_date": str(filters.get("from_date") or get_first_day(today())),
		"to_date": str(filters.get("to_date") or today()),
	}
	owner = get_owner_dashboard_data(resolved)
	return _build_control_snapshot(owner)


def _build_control_snapshot(owner: dict[str, Any]) -> dict[str, Any]:
	sections = owner.get("sections") or {}
	filters = owner.get("filters") or {}

	receivables = _metric(sections, "receivables", "Total Receivables")
	receivables_overdue = _metric(sections, "receivables", "Overdue")
	receivables_90 = _metric(sections, "receivables", "Over 90 Days")
	payables = _metric(sections, "payables", "Total Payables")
	payables_overdue = _metric(sections, "payables", "Overdue")
	payables_90 = _metric(sections, "payables", "Over 90 Days")
	money_in = _metric(sections, "cash", "Money In")
	money_out = _metric(sections, "cash", "Money Out")
	net_cash_change = _metric(sections, "cash", "Net Change")
	expenses = _metric(sections, "expenses", "Total Expenses")
	accounting_net_profit = _metric(sections, "profitability", "Accounting Net Profit")
	transactional_gross_profit = _metric(sections, "profitability", "Transactional Gross Profit")

	controls = _control_items(sections)
	return {
		"title": _("Business Control Centre"),
		"filters": filters,
		"position": [
			_card("Receivables", receivables, "Currency", "current"),
			_card("Payables", payables, "Currency", "current"),
			_card("Net Trade Position", receivables - payables, "Currency", "current"),
			_card("Money In", money_in, "Currency", "period"),
			_card("Money Out", money_out, "Currency", "period"),
			_card("Net Cash Movement", net_cash_change, "Currency", "period"),
			_card("Expenses", expenses, "Currency", "period"),
			_card("Accounting Net Profit", accounting_net_profit, "Currency", "period"),
			_card("Sales Margin Contribution", transactional_gross_profit, "Currency", "period"),
		],
		"pressure": {
			"receivables_overdue": receivables_overdue,
			"receivables_over_90": receivables_90,
			"receivables_overdue_percent": _percent(receivables_overdue, receivables),
			"payables_overdue": payables_overdue,
			"payables_over_90": payables_90,
			"payables_overdue_percent": _percent(payables_overdue, payables),
		},
		"controls": controls,
		"summary": {
			"critical": sum(1 for item in controls if item["severity"] == "critical"),
			"warning": sum(1 for item in controls if item["severity"] == "warning"),
			"total_open_controls": len(controls),
		},
		"metadata": {
			"accounting_truth": "ERPNext remains authoritative; RetailEdge derives control signals from existing permission-aware reporting engines.",
			"trade_position_definition": "current receivables minus current payables; not cash, working capital or accounting net assets",
			"cash_basis": "selected-period posted Cash/Bank GL movement, not closing cash balance",
			"branch_accounting_limit": "branch accounting conclusions remain limited by valid ERPNext branch/accounting attribution",
		},
	}


def _control_items(sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	rules = (
		("receivables", "Over 90 Days", "critical", "Collections", "Customer debt is more than 90 days overdue", "/app/customer-receivables"),
		("receivables", "Overdue", "warning", "Collections", "Customer balances are overdue", "/app/customer-receivables"),
		("payables", "Over 90 Days", "critical", "Supplier Obligations", "Supplier balances are more than 90 days overdue", "/app/supplier-payables"),
		("payables", "Overdue", "warning", "Supplier Obligations", "Supplier balances are overdue", "/app/supplier-payables"),
		("profitability", "Negative Margin Items", "critical", "Margin", "Items are selling at negative margin", "/app/profitability-intelligence"),
		("profitability", "Low Margin Items", "warning", "Margin", "Items are below the configured margin threshold", "/app/profitability-intelligence"),
		("profitability", "Items Missing Recorded Cost", "warning", "Cost Integrity", "Sold items have no recorded item cost", "/app/profitability-intelligence"),
		("expenses", "Posting Blocked", "critical", "Expense Control", "Expense posting is blocked", "/app/expense-register"),
		("expenses", "Submitted for Review", "warning", "Expense Control", "Expenses are awaiting review", "/app/expense-register"),
		("stock", "Negative Stock", "critical", "Stock Control", "Items have negative stock", "/app/stock-position"),
		("stock", "Out of Stock", "warning", "Stock Control", "Items are out of stock", "/app/stock-position"),
		("stock", "Fully Reserved", "warning", "Stock Control", "Stock is fully reserved", "/app/stock-position"),
	)
	items: list[dict[str, Any]] = []
	seen: set[tuple[str, str]] = set()
	for section_key, label, severity, family, message, route in rules:
		value = _metric(sections, section_key, label)
		if value <= 0 or (section_key, label) in seen:
			continue
		seen.add((section_key, label))
		items.append(
			{
				"key": f"{section_key}:{label}",
				"family": _(family),
				"severity": severity,
				"label": _(message),
				"metric": _(label),
				"value": value,
				"route": route,
				"source_section": section_key,
				"time_basis": "current" if section_key in {"receivables", "payables", "stock"} else "period",
			}
		)
	items.sort(key=lambda item: (0 if item["severity"] == "critical" else 1, -abs(flt(item["value"])), item["key"]))
	return items


def _metric(sections: dict[str, dict[str, Any]], section_key: str, label: str) -> float:
	section = sections.get(section_key) or {}
	if not section.get("available"):
		return 0.0
	for card in section.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return flt(card.get("value"))
	return 0.0


def _percent(numerator: float, denominator: float) -> float | None:
	return numerator / denominator * 100.0 if denominator else None


def _card(label: str, value: float, datatype: str, time_basis: str) -> dict[str, Any]:
	return {"label": _(label), "value": value, "datatype": datatype, "time_basis": time_basis}


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
