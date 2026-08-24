from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from retailedge.cash_movement import get_cash_movement_export
from retailedge.planning_intelligence import get_planning_intelligence, _monthly_gl_actuals
from retailedge.sales_forecasting import get_sales_forecast

SCENARIO_DOCTYPE = "RetailEdge Planning Scenario"


@frappe.whitelist()
def get_scenario_performance(scenario: str) -> dict[str, Any]:
	name = str(scenario or "").strip()
	if not name:
		frappe.throw(_("Planning Scenario is required."))
	if not frappe.has_permission(SCENARIO_DOCTYPE, "read", doc=name):
		frappe.throw(_("You do not have permission to view this Planning Scenario."), frappe.PermissionError)
	doc = frappe.get_doc(SCENARIO_DOCTYPE, name)
	baseline = get_planning_intelligence(_scenario_filters(doc))
	completed_periods = _completed_future_periods(doc.as_of_date, doc.horizon_months)
	rows: list[dict[str, Any]] = []

	rows.extend(_domain_comparison(
		domain_key="sales",
		domain_label=_("Sales"),
		baseline=baseline,
		completed_periods=completed_periods,
		actual_loader=lambda period_start: _sales_actual(doc, period_start),
	))
	rows.extend(_domain_comparison(
		domain_key="cash",
		domain_label=_("Cash Movement"),
		baseline=baseline,
		completed_periods=completed_periods,
		actual_loader=lambda period_start: _cash_actual(doc, period_start),
	))
	if not doc.branch:
		rows.extend(_domain_comparison(
			domain_key="expenses",
			domain_label=_("Accounting Expenses"),
			baseline=baseline,
			completed_periods=completed_periods,
			actual_loader=lambda period_start: _gl_actual(doc.company, period_start, "Expense"),
		))
		rows.extend(_domain_comparison(
			domain_key="profitability",
			domain_label=_("Accounting Profitability"),
			baseline=baseline,
			completed_periods=completed_periods,
			actual_loader=lambda period_start: _profit_actual(doc.company, period_start),
		))

	rows.sort(key=lambda row: (str(row.get("period_start") or ""), str(row.get("domain") or "")))
	return {
		"title": _("Forecast vs Actual"),
		"scenario": {
			"name": doc.name,
			"scenario_name": doc.scenario_name,
			"scenario_type": doc.scenario_type,
			"status": doc.status,
			"company": doc.company,
			"branch": doc.branch or "",
			"as_of_date": str(doc.as_of_date),
			"history_months": doc.history_months,
			"horizon_months": doc.horizon_months,
		},
		"rows": rows,
		"summary": _summary(rows),
		"metadata": {
			"comparison_scope": "Completed Sales, Cash Movement, Accounting Expense and Accounting Profit forecast periods where source truth can be reconstructed safely",
			"future_periods_without_completed_actuals": "Remain pending and are not scored",
			"branch_accounting_policy": "Branch scenarios score Sales and Cash only; accounting Expense/Profit remain company-level until valid ERPNext accounting attribution exists",
			"accounting_truth": "ERPNext posted accounting remains authoritative; this comparison creates no accounting entries",
			"scenario_snapshot_semantics": "Forecast and Plan are recalculated from the scenario's saved as-of date and assumptions, then compared only with subsequently completed actual periods",
		},
	}


def _scenario_filters(doc) -> dict[str, Any]:
	return {
		"company": doc.company,
		"branch": doc.branch or "",
		"as_of_date": str(doc.as_of_date),
		"history_months": doc.history_months,
		"forecast_months": doc.horizon_months,
		"sales_adjustment_percent": flt(doc.sales_adjustment_percent),
		"expense_adjustment_percent": flt(doc.expense_adjustment_percent),
		"cash_adjustment_percent": flt(doc.cash_adjustment_percent),
		"inventory_safety_percent": flt(doc.inventory_safety_percent),
	}


def _completed_future_periods(as_of_date, horizon: int) -> list[str]:
	as_of = getdate(as_of_date)
	first = getdate(add_months(get_first_day(as_of), 1 if as_of == getdate(get_last_day(as_of)) else 0))
	today = getdate(nowdate())
	periods: list[str] = []
	current = first
	for _ in range(int(horizon or 0)):
		if getdate(get_last_day(current)) > today:
			break
		periods.append(current.isoformat())
		current = getdate(add_months(current, 1))
	return periods


def _domain_comparison(
	*,
	domain_key: str,
	domain_label: str,
	baseline: dict[str, Any],
	completed_periods: list[str],
	actual_loader: Callable[[str], float],
) -> list[dict[str, Any]]:
	domain = baseline.get("domains", {}).get(domain_key) or {}
	if not domain.get("available"):
		return []
	forecast_map = {str(row.get("period_start")): row for row in domain.get("future_rows") or []}
	rows: list[dict[str, Any]] = []
	for period_start in completed_periods:
		planned = forecast_map.get(period_start)
		if not planned:
			continue
		actual = flt(actual_loader(period_start))
		forecast = flt(planned.get("forecast"))
		plan_value = planned.get("plan")
		plan = flt(plan_value) if plan_value is not None else None
		rows.append({
			"domain": domain_label,
			"period_start": period_start,
			"forecast": forecast,
			"plan": plan,
			"actual": actual,
			"forecast_variance": actual - forecast,
			"plan_variance": actual - plan if plan is not None else None,
			"forecast_accuracy_percent": _accuracy(actual, forecast),
			"plan_accuracy_percent": _accuracy(actual, plan) if plan is not None else None,
		})
	return rows


def _sales_actual(doc, period_start: str) -> float:
	period_end = str(get_last_day(period_start))
	payload = get_sales_forecast({
		"company": doc.company,
		"branch": doc.branch or "",
		"as_of_date": period_end,
		"history_months": 1,
		"forecast_months": 1,
	})
	actual_rows = [row for row in payload.get("rows") or [] if row.get("row_type") == _("Actual")]
	return flt(actual_rows[-1].get("net_sales")) if actual_rows else 0.0


def _cash_actual(doc, period_start: str) -> float:
	payload = get_cash_movement_export({
		"company": doc.company,
		"branch": doc.branch or "",
		"from_date": period_start,
		"to_date": str(get_last_day(period_start)),
	})
	for card in payload.get("summary") or []:
		if str(card.get("label") or "") == "Net Change":
			return flt(card.get("value"))
	return 0.0


def _gl_actual(company: str, period_start: str, root_type: str) -> float:
	rows = _monthly_gl_actuals(company, period_start, str(get_last_day(period_start)), root_type=root_type)
	return flt(rows[0].get("actual")) if rows else 0.0


def _profit_actual(company: str, period_start: str) -> float:
	return _gl_actual(company, period_start, "Income") - _gl_actual(company, period_start, "Expense")


def _accuracy(actual: float, expected: float | None) -> float | None:
	if expected is None:
		return None
	if expected == 0:
		return 100.0 if actual == 0 else None
	return max(0.0, 100.0 - abs(actual - expected) / abs(expected) * 100.0)


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	forecast_scores = [flt(row.get("forecast_accuracy_percent")) for row in rows if row.get("forecast_accuracy_percent") is not None]
	plan_scores = [flt(row.get("plan_accuracy_percent")) for row in rows if row.get("plan_accuracy_percent") is not None]
	return [
		{"label": _("Completed Comparisons"), "value": len(rows), "datatype": "Int"},
		{"label": _("Domains Scored"), "value": len({row.get("domain") for row in rows if row.get("domain")}), "datatype": "Int"},
		{"label": _("Average Forecast Accuracy"), "value": sum(forecast_scores) / len(forecast_scores) if forecast_scores else None, "datatype": "Percent"},
		{"label": _("Average Plan Accuracy"), "value": sum(plan_scores) / len(plan_scores) if plan_scores else None, "datatype": "Percent"},
	]
