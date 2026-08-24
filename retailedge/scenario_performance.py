from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from retailedge.planning_intelligence import get_planning_intelligence
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

	filters = _scenario_filters(doc)
	baseline = get_planning_intelligence(filters)
	completed_periods = _completed_future_periods(doc.as_of_date, doc.horizon_months)
	sales_comparison = _sales_actual_comparison(doc, baseline, completed_periods)

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
		"rows": sales_comparison,
		"summary": _summary(sales_comparison),
		"metadata": {
			"comparison_scope": "Sales forecast vs subsequently completed submitted Sales Invoice actuals",
			"future_periods_without_completed_actuals": "Remain pending and are not scored",
			"accounting_truth": "ERPNext posted accounting remains authoritative; this comparison does not create accounting entries",
			"scenario_snapshot_semantics": "Forecast is recalculated from the scenario's saved as-of date and assumptions so performance is measured against the saved planning basis",
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


def _sales_actual_comparison(doc, baseline: dict[str, Any], completed_periods: list[str]) -> list[dict[str, Any]]:
	sales = baseline.get("domains", {}).get("sales") or {}
	if not sales.get("available"):
		return []
	forecast_map = {str(row.get("period_start")): row for row in sales.get("future_rows") or []}
	rows: list[dict[str, Any]] = []
	for period_start in completed_periods:
		period_end = str(get_last_day(period_start))
		actual_payload = get_sales_forecast({
			"company": doc.company,
			"branch": doc.branch or "",
			"as_of_date": period_end,
			"history_months": 1,
			"forecast_months": 1,
		})
		actual_rows = [row for row in actual_payload.get("rows") or [] if row.get("row_type") == _("Actual")]
		actual = flt(actual_rows[-1].get("net_sales")) if actual_rows else 0.0
		planned = forecast_map.get(period_start) or {}
		forecast = flt(planned.get("forecast"))
		plan = flt(planned.get("plan"))
		rows.append({
			"domain": _("Sales"),
			"period_start": period_start,
			"forecast": forecast,
			"plan": plan,
			"actual": actual,
			"forecast_variance": actual - forecast,
			"plan_variance": actual - plan,
			"forecast_accuracy_percent": _accuracy(actual, forecast),
			"plan_accuracy_percent": _accuracy(actual, plan),
		})
	return rows


def _accuracy(actual: float, expected: float) -> float | None:
	if expected == 0:
		return 100.0 if actual == 0 else None
	return max(0.0, 100.0 - abs(actual - expected) / abs(expected) * 100.0)


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	if not rows:
		return [
			{"label": _("Completed Forecast Months"), "value": 0, "datatype": "Int"},
			{"label": _("Average Forecast Accuracy"), "value": None, "datatype": "Percent"},
			{"label": _("Average Plan Accuracy"), "value": None, "datatype": "Percent"},
		]
	forecast_scores = [flt(row.get("forecast_accuracy_percent")) for row in rows if row.get("forecast_accuracy_percent") is not None]
	plan_scores = [flt(row.get("plan_accuracy_percent")) for row in rows if row.get("plan_accuracy_percent") is not None]
	return [
		{"label": _("Completed Forecast Months"), "value": len(rows), "datatype": "Int"},
		{"label": _("Average Forecast Accuracy"), "value": sum(forecast_scores) / len(forecast_scores) if forecast_scores else None, "datatype": "Percent"},
		{"label": _("Average Plan Accuracy"), "value": sum(plan_scores) / len(plan_scores) if plan_scores else None, "datatype": "Percent"},
	]
