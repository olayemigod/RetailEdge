from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.expense_budget_api import get_expense_budget_insight
from retailedge.expense_dashboard import get_expense_dashboard_data

DASHBOARD_KEY = "owner-dashboard"
MAX_CATEGORY_CONTROLS = 20


@frappe.whitelist()
def get_budget_spend_control(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	company = str(resolved.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(resolved.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	resolved.company = company
	budget = get_expense_budget_insight(resolved)
	dashboard = get_expense_dashboard_data(resolved)
	return _build_budget_spend_control(budget=budget, dashboard=dashboard)


def _build_budget_spend_control(*, budget: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
	available = bool(budget.get("available"))
	used_pct = _optional_float(budget.get("used_pct"))
	projected_spend = _optional_float(budget.get("projected_period_spend"))
	target = _optional_float(budget.get("target_amount"))
	actual = _optional_float(budget.get("actual_amount"))
	remaining = _optional_float(budget.get("remaining_amount"))
	projected_variance = _optional_float(budget.get("projected_variance"))
	comparison = dashboard.get("comparison") or {}
	change_pct = _optional_float(comparison.get("change_pct"))

	controls: list[dict[str, Any]] = []
	if available and bool(budget.get("over_budget")):
		controls.append(_control("critical", "Budget", "Actual spend is already above the allocated budget", actual, "Currency"))
	elif available and bool(budget.get("projected_over_budget")):
		controls.append(_control("warning", "Budget", "Current burn rate projects a budget overrun", projected_spend, "Currency"))
	elif available and used_pct is not None and used_pct >= 80:
		controls.append(_control("warning", "Budget", "Budget consumption has reached at least 80%", used_pct, "Percent"))

	if change_pct is not None and change_pct >= 20:
		controls.append(_control("warning", "Spend Trend", "Spend increased materially versus the previous equal period", change_pct, "Percent"))

	ambiguous_count = int(budget.get("ambiguous_category_count") or 0)
	if ambiguous_count > 0:
		controls.append(_control("warning", "Budget Mapping", "Some expense categories share the same budget account and cost centre mapping", ambiguous_count, "Int"))

	category_controls = _category_controls(budget.get("category_targets") or [])
	controls.extend(category_controls)
	controls.sort(key=lambda item: (0 if item["severity"] == "critical" else 1, item["family"], item["label"]))

	return {
		"title": _("Budget & Spend Governance"),
		"available": available,
		"reason": budget.get("reason") or "",
		"summary": [
			_card("Budget for Period", target, "Currency", available),
			_card("Actual Spend", actual, "Currency", actual is not None),
			_card("Budget Used", used_pct, "Percent", used_pct is not None),
			_card("Remaining Budget", remaining, "Currency", remaining is not None),
			_card("Projected Period Spend", projected_spend, "Currency", projected_spend is not None),
			_card("Projected Variance", projected_variance, "Currency", projected_variance is not None),
		],
		"controls": controls,
		"category_pressure": category_controls,
		"trend": {
			"change_pct": change_pct,
			"current_total": comparison.get("current_total"),
			"previous_total": comparison.get("previous_total"),
			"current_daily_average": comparison.get("current_daily_average"),
			"previous_daily_average": comparison.get("previous_daily_average"),
			"previous_period_available": bool(comparison.get("previous_period_available")),
		},
		"metadata": {
			"budget_truth": "Submitted ERPNext Budget remains authoritative for configured budget amounts and enforcement.",
			"actual_truth": "RetailEdge Expense Register remains the source for actual expense spend used by this insight.",
			"projection_definition": "Straight-line burn-rate projection across the selected period; planning signal only, not an accounting forecast.",
			"mapping_limit": "Category-level budget pressure is withheld when multiple RetailEdge categories share one Expense Account and Cost Center budget pair.",
			"enforcement": budget.get("enforcement_note") or "RetailEdge does not change ERPNext Budget enforcement or workflow settings.",
			"authorization": "Owner Dashboard view capability plus underlying expense and budget permissions.",
		},
	}


def _category_controls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for row in rows:
		if row.get("ambiguous") or row.get("target") is None:
			continue
		actual = flt(row.get("actual"))
		target = flt(row.get("target"))
		if target <= 0:
			continue
		used_pct = actual / target * 100.0
		if actual > target:
			severity = "critical"
			label = "Category spend is above budget"
		elif used_pct >= 80:
			severity = "warning"
			label = "Category spend has reached at least 80% of budget"
		else:
			continue
		items.append(
			{
				**_control(severity, "Category Budget", label, used_pct, "Percent"),
				"category": row.get("category") or "",
				"actual": actual,
				"target": target,
				"variance": target - actual,
				"route": "/app/expense-register",
			}
		)
	items.sort(key=lambda item: (0 if item["severity"] == "critical" else 1, -flt(item["value"]), str(item.get("category") or "")))
	return items[:MAX_CATEGORY_CONTROLS]


def _control(severity: str, family: str, label: str, value: Any, datatype: str) -> dict[str, Any]:
	return {
		"severity": severity,
		"family": _(family),
		"label": _(label),
		"value": value,
		"datatype": datatype,
		"route": "/app/expense-register",
	}


def _card(label: str, value: Any, datatype: str, available: bool) -> dict[str, Any]:
	return {"label": _(label), "value": value if available else None, "datatype": datatype, "available": available, "time_basis": "period"}


def _optional_float(value: Any) -> float | None:
	return None if value is None else flt(value)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
