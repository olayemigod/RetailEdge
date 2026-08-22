from __future__ import annotations

from datetime import timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from retailedge.accounting_profitability import get_accounting_profitability
from retailedge.budget_spend_control import get_budget_spend_control
from retailedge.liquidity_control import get_liquidity_control


@frappe.whitelist()
def get_control_early_warning(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	company = str(resolved.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if not resolved.get("from_date") or not resolved.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))
	resolved.company = company

	budget = get_budget_spend_control(resolved)
	liquidity = get_liquidity_control(resolved)
	profitability = _profitability_trend(resolved)
	return _build_control_early_warning(budget=budget, liquidity=liquidity, profitability=profitability)


def _profitability_trend(filters: frappe._dict) -> dict[str, Any]:
	current = get_accounting_profitability(filters)
	if not current.get("available"):
		return {
			"available": False,
			"reason": current.get("reason") or _("Accounting profitability trend is unavailable for this scope."),
			"current": current,
			"previous": {},
		}
	start = getdate(filters.from_date)
	end = getdate(filters.to_date)
	if start > end:
		frappe.throw(_("From Date cannot be after To Date."))
	days = date_diff(end, start) + 1
	previous_end = start - timedelta(days=1)
	previous_start = previous_end - timedelta(days=days - 1)
	previous_filters = frappe._dict(filters)
	previous_filters.from_date = str(previous_start)
	previous_filters.to_date = str(previous_end)
	previous = get_accounting_profitability(previous_filters)
	return {
		"available": bool(previous.get("available")),
		"reason": previous.get("reason") or "",
		"current": current,
		"previous": previous,
		"previous_from_date": str(previous_start),
		"previous_to_date": str(previous_end),
	}


def _build_control_early_warning(
	*,
	budget: dict[str, Any],
	liquidity: dict[str, Any],
	profitability: dict[str, Any],
) -> dict[str, Any]:
	warnings: list[dict[str, Any]] = []

	for item in budget.get("controls") or []:
		if item.get("severity") not in {"critical", "warning"}:
			continue
		warnings.append(
			_warning(
				severity=str(item.get("severity")),
				family=str(item.get("family") or _("Spend")),
				label=str(item.get("label") or _("Budget or spend control requires attention")),
				value=item.get("value"),
				datatype=str(item.get("datatype") or "Data"),
				route=str(item.get("route") or "/app/expense-register"),
			)
		)

	current_liquidity = liquidity.get("current_liquidity") or {}
	cash_available = bool(current_liquidity.get("cash_bank_available"))
	immediate_coverage = _optional_float(current_liquidity.get("immediate_obligation_coverage_ratio"))
	indicative_gap = _optional_float(current_liquidity.get("indicative_liquidity_gap"))
	overdue_receivables = flt(current_liquidity.get("overdue_receivables"))
	overdue_payables = flt(current_liquidity.get("overdue_payables"))

	if cash_available and immediate_coverage is not None and immediate_coverage < 1:
		warnings.append(_warning("critical", "Liquidity", "Cash and bank balance does not cover supplier obligations due within the control horizon", immediate_coverage, "Float", "/app/supplier-payables"))
	elif cash_available and immediate_coverage is not None and immediate_coverage < 1.25:
		warnings.append(_warning("warning", "Liquidity", "Immediate supplier-obligation coverage is tight", immediate_coverage, "Float", "/app/supplier-payables"))
	if cash_available and indicative_gap is not None and indicative_gap < 0:
		warnings.append(_warning("warning", "Liquidity", "Cash plus receivables due within the horizon remains below supplier obligations due", indicative_gap, "Currency", "/app/supplier-payables"))
	if overdue_receivables > 0:
		warnings.append(_warning("warning", "Collections", "Overdue customer receivables require collection attention", overdue_receivables, "Currency", "/app/customer-receivables"))
	if overdue_payables > 0:
		warnings.append(_warning("warning", "Supplier Obligations", "Overdue supplier obligations require payment attention", overdue_payables, "Currency", "/app/supplier-payables"))

	profit_signal = _profitability_warning(profitability)
	if profit_signal:
		warnings.append(profit_signal)

	warnings.sort(key=lambda item: (0 if item["severity"] == "critical" else 1, item["family"], item["label"]))
	return {
		"title": _("Control Trends & Early Warning"),
		"warnings": warnings,
		"critical_count": sum(1 for item in warnings if item["severity"] == "critical"),
		"warning_count": sum(1 for item in warnings if item["severity"] == "warning"),
		"profitability_trend": profitability,
		"liquidity": liquidity,
		"budget_spend": budget,
		"metadata": {
			"composition": "existing_r8_r9_truth_and_control_engines",
			"historical_balance_limit": "Receivables and payables are current ERPNext outstanding balances. RetailEdge does not manufacture historical AR/AP balances for trend comparison.",
			"profit_truth": "Company profitability trend reuses ERPNext Profit and Loss Statement and Gross and Net Profit Report through the R8 accounting profitability engine.",
			"liquidity_limit": "Liquidity signals are management indicators, not a cash forecast or payment instruction.",
			"branch_limit": "Company accounting profitability trend is withheld for Branch scope until safe ERPNext accounting-dimension or Cost Center attribution exists.",
		},
	}


def _profitability_warning(profitability: dict[str, Any]) -> dict[str, Any] | None:
	if not profitability.get("available"):
		return None
	current = profitability.get("current") or {}
	previous = profitability.get("previous") or {}
	current_profit = flt(current.get("net_profit"))
	previous_profit = flt(previous.get("net_profit"))
	current_margin = _optional_float(current.get("gross_margin_percent"))
	previous_margin = _optional_float(previous.get("gross_margin_percent"))
	if current_profit < 0:
		return _warning("critical", "Profitability", "ERPNext accounting net profit is negative for the selected period", current_profit, "Currency", str(current.get("route") or "/app/query-report/Profit%20and%20Loss%20Statement"))
	if previous_profit > 0 and current_profit < previous_profit * 0.8:
		change_pct = (current_profit - previous_profit) / previous_profit * 100.0
		return _warning("warning", "Profitability", "Accounting net profit declined materially versus the previous equal period", change_pct, "Percent", str(current.get("route") or "/app/query-report/Profit%20and%20Loss%20Statement"))
	if current_margin is not None and previous_margin is not None and current_margin < previous_margin - 5:
		return _warning("warning", "Profitability", "Gross margin declined by more than 5 percentage points versus the previous equal period", current_margin - previous_margin, "Percent", str(current.get("route") or "/app/query-report/Profit%20and%20Loss%20Statement"))
	return None


def _warning(severity: str, family: str, label: str, value: Any, datatype: str, route: str) -> dict[str, Any]:
	return {
		"severity": severity,
		"family": _(family),
		"label": _(label),
		"value": value,
		"datatype": datatype,
		"route": route,
	}


def _optional_float(value: Any) -> float | None:
	return None if value is None else flt(value)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
