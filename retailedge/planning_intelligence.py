from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from retailedge.cash_movement import get_cash_movement_export
from retailedge.forecasting import MAX_FORECAST_HORIZON, apply_plan_adjustment, build_baseline_forecast
from retailedge.inventory_demand import get_historical_inventory_demand
from retailedge.inventory_replenishment import get_inventory_replenishment
from retailedge.sales_forecasting import get_sales_forecast
from retailedge.sales_reporting import _company_currency, _coerce_filters

DEFAULT_HISTORY_MONTHS = 6
DEFAULT_HORIZON_MONTHS = 3
MAX_HISTORY_MONTHS = 24
MAX_GL_SCAN_ROWS = 30000
MAX_INVENTORY_FORECAST_ITEMS = 5000


@frappe.whitelist()
def get_planning_intelligence(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _normalise_filters(filters)
	return _build_planning_dataset(resolved)


@frappe.whitelist()
def get_planning_intelligence_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	dataset = _build_planning_dataset(_normalise_filters(filters))
	return {
		"title": dataset["title"],
		"columns": dataset["columns"],
		"rows": dataset["rows"],
		"summary": dataset["summary"],
		"company_currency": dataset["company_currency"],
		"metadata": dataset["metadata"],
	}


@frappe.whitelist()
def get_planning_action_summary(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return lightweight R12 action signals without persisting forecast truth."""
	data = get_planning_intelligence(filters)
	items: list[dict[str, Any]] = []
	cash = data.get("domains", {}).get("cash") or {}
	profit = data.get("domains", {}).get("profitability") or {}
	inventory = data.get("domains", {}).get("inventory") or {}

	cash_rows = cash.get("future_rows") or []
	if cash.get("available") and any(flt(row.get("plan")) < 0 for row in cash_rows):
		items.append(_action("cash_plan_negative", _("Planned cash movement is negative in at least one forecast month"), "danger"))
	profit_rows = profit.get("future_rows") or []
	if profit.get("available") and any(flt(row.get("plan")) < 0 for row in profit_rows):
		items.append(_action("profit_plan_negative", _("Planned accounting result is negative in at least one forecast month"), "danger"))
	inv_rows = inventory.get("rows") or []
	at_risk = sum(1 for row in inv_rows if flt(row.get("planned_demand_qty")) > flt(row.get("current_projected_qty")))
	if at_risk:
		items.append({**_action("inventory_plan_shortfall", _("Forecast demand exceeds current projected stock for some items"), "warning"), "value": at_risk, "datatype": "Int"})
	return {"items": items, "count": len(items), "route": "/app/forecasting-planning"}


def _action(kind: str, label: str, severity: str) -> dict[str, Any]:
	return {
		"source": "r12_planning",
		"semantic_key": kind,
		"kind": kind,
		"label": label,
		"severity": severity,
		"value": 1,
		"datatype": "Int",
		"route": "/app/forecasting-planning",
		"target_type": "Page",
		"target": "forecasting-planning",
		"open_mode": "same_tab",
		"time_basis": "forecast",
	}


def _normalise_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	resolved = _coerce_filters(filters)
	resolved.company = str(resolved.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not resolved.company:
		frappe.throw(_("Company is required."))
	if not frappe.has_permission("Company", "read", doc=resolved.company):
		frappe.throw(_("You do not have permission to use Company {0}.").format(resolved.company), frappe.PermissionError)
	resolved.branch = str(resolved.get("branch") or "").strip()
	resolved.as_of_date = str(resolved.get("as_of_date") or nowdate())
	resolved.history_months = _bounded_int(resolved.get("history_months"), DEFAULT_HISTORY_MONTHS, 3, MAX_HISTORY_MONTHS, _("History Months"))
	resolved.forecast_months = _bounded_int(resolved.get("forecast_months"), DEFAULT_HORIZON_MONTHS, 1, MAX_FORECAST_HORIZON, _("Forecast Months"))
	for fieldname in ("sales_adjustment_percent", "expense_adjustment_percent", "cash_adjustment_percent"):
		resolved[fieldname] = _bounded_percent(resolved.get(fieldname), -100.0, 1000.0, fieldname)
	resolved.inventory_safety_percent = _bounded_percent(resolved.get("inventory_safety_percent", 10), 0.0, 500.0, "inventory_safety_percent")
	return resolved


def _build_planning_dataset(filters: frappe._dict) -> dict[str, Any]:
	currency = _company_currency(filters.company)
	sales = _safe_domain("sales", lambda: _sales_domain(filters))
	cash = _safe_domain("cash", lambda: _cash_domain(filters))
	expenses = _safe_domain("expenses", lambda: _accounting_domain(filters, root_type="Expense", adjustment=filters.expense_adjustment_percent))
	profitability = _safe_domain("profitability", lambda: _profitability_domain(filters))
	inventory = _safe_domain("inventory", lambda: _inventory_domain(filters))

	domains = {"sales": sales, "cash": cash, "expenses": expenses, "profitability": profitability, "inventory": inventory}
	rows = _flatten_domain_rows(domains)
	summary = _summary_cards(domains)
	return {
		"title": _("Forecasting & Planning"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"domains": domains,
		"scope": {
			"company": filters.company,
			"branch": filters.branch,
			"as_of_date": filters.as_of_date,
			"history_months": filters.history_months,
			"forecast_months": filters.forecast_months,
		},
		"assumptions": {
			"sales_adjustment_percent": filters.sales_adjustment_percent,
			"expense_adjustment_percent": filters.expense_adjustment_percent,
			"cash_adjustment_percent": filters.cash_adjustment_percent,
			"inventory_safety_percent": filters.inventory_safety_percent,
		},
		"metadata": {
			"actual_forecast_plan_separation": True,
			"accounting_truth": "ERPNext General Ledger / Profit and Loss semantics remain authoritative for accounting results",
			"sales_truth": "Submitted ERPNext Sales Invoice / Sales Invoice Item",
			"cash_truth": "Posted ERPNext GL entries for Cash and Bank accounts through RetailEdge Cash Movement",
			"inventory_truth": "ERPNext Stock Ledger Entry demand, Bin projected quantity and Item Reorder configuration",
			"scenario_truth": "RetailEdge Planning Scenario stores assumptions only; forecasted accounting transactions are never persisted",
			"branch_accounting_policy": "Accounting expense/profit forecasts fail closed at Branch scope until valid ERPNext accounting attribution exists",
			"mutates_accounting_documents": False,
		},
	}


def _safe_domain(key: str, loader: Callable[[], dict[str, Any]]) -> dict[str, Any]:
	try:
		return {"available": True, **(loader() or {})}
	except frappe.PermissionError:
		return {"available": False, "key": key, "reason": _("Your permissions do not allow this forecast domain.")}
	except frappe.ValidationError as exc:
		return {"available": False, "key": key, "reason": str(exc)}


def _sales_domain(filters: frappe._dict) -> dict[str, Any]:
	payload = get_sales_forecast({
		"company": filters.company,
		"branch": filters.branch,
		"as_of_date": filters.as_of_date,
		"history_months": filters.history_months,
		"forecast_months": filters.forecast_months,
	})
	forecast_rows = [row for row in payload.get("rows") or [] if row.get("row_type") == _("Forecast")]
	planned = apply_plan_adjustment([{"period_start": row["period_start"], "forecast": flt(row.get("forecast"))} for row in forecast_rows], adjustment_percent=filters.sales_adjustment_percent, floor=0.0)
	return {
		"key": "sales",
		"title": _("Sales"),
		"future_rows": planned,
		"actual_rows": [row for row in payload.get("rows") or [] if row.get("row_type") == _("Actual")],
		"source": payload.get("metadata", {}).get("sales_truth"),
		"metadata": payload.get("metadata") or {},
	}


def _cash_domain(filters: frappe._dict) -> dict[str, Any]:
	start, end, _forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	actuals: list[dict[str, Any]] = []
	for period_start in _month_starts(start, end):
		period_end = str(get_last_day(period_start))
		payload = get_cash_movement_export({"company": filters.company, "branch": filters.branch, "from_date": period_start, "to_date": period_end})
		net = _summary_value(payload.get("summary") or [], "Net Change")
		actuals.append({"period_start": period_start, "actual": net})
	forecast = build_baseline_forecast(actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end)
	planned = apply_plan_adjustment(forecast["rows"], adjustment_percent=filters.cash_adjustment_percent)
	return {
		"key": "cash",
		"title": _("Cash Movement"),
		"actual_rows": actuals,
		"future_rows": planned,
		"source": "Posted ERPNext GL Cash/Bank movements",
		"metadata": forecast["metadata"],
	}


def _accounting_domain(filters: frappe._dict, *, root_type: str, adjustment: float) -> dict[str, Any]:
	if filters.branch:
		frappe.throw(_("Accounting {0} forecast is company-level until Branch is mapped to a valid ERPNext accounting dimension or Cost Center.").format(root_type.lower()))
	start, end, _forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	actuals = _monthly_gl_actuals(filters.company, start, end, root_type=root_type)
	forecast = build_baseline_forecast(actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end, floor=0.0 if root_type == "Expense" else None)
	planned = apply_plan_adjustment(forecast["rows"], adjustment_percent=adjustment, floor=0.0 if root_type == "Expense" else None)
	return {
		"key": root_type.lower(),
		"title": _(root_type),
		"actual_rows": actuals,
		"future_rows": planned,
		"source": f"ERPNext GL Entry + {root_type} root-type accounts",
		"metadata": forecast["metadata"],
	}


def _profitability_domain(filters: frappe._dict) -> dict[str, Any]:
	if filters.branch:
		frappe.throw(_("Accounting profitability forecast is company-level until Branch is mapped to a valid ERPNext accounting dimension or Cost Center."))
	start, end, _forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	income = _monthly_gl_actuals(filters.company, start, end, root_type="Income")
	expense = _monthly_gl_actuals(filters.company, start, end, root_type="Expense")
	expense_by_period = {row["period_start"]: flt(row["actual"]) for row in expense}
	actuals = [{"period_start": row["period_start"], "actual": flt(row["actual"]) - expense_by_period.get(row["period_start"], 0.0)} for row in income]
	forecast = build_baseline_forecast(actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end)
	# Profit plan is derived from independently adjusted Sales and Expense assumptions, not an arbitrary profit multiplier.
	sales = _sales_domain(filters)
	expenses = _accounting_domain(filters, root_type="Expense", adjustment=filters.expense_adjustment_percent)
	sales_plan = {row["period_start"]: flt(row.get("plan")) for row in sales.get("future_rows") or []}
	expense_plan = {row["period_start"]: flt(row.get("plan")) for row in expenses.get("future_rows") or []}
	future = []
	for row in forecast["rows"]:
		period = row["period_start"]
		future.append({"period_start": period, "forecast": flt(row["forecast"]), "plan": sales_plan.get(period, 0.0) - expense_plan.get(period, 0.0), "plan_adjustment_percent": None})
	return {
		"key": "profitability",
		"title": _("Accounting Profitability"),
		"actual_rows": actuals,
		"future_rows": future,
		"source": "ERPNext GL Income less Expense accounts",
		"metadata": {**forecast["metadata"], "plan_semantics": "Sales Plan less Expense Plan; ERPNext Profit and Loss remains authoritative for posted results"},
	}


def _inventory_domain(filters: frappe._dict) -> dict[str, Any]:
	lookback_days = min(max(filters.history_months * 30, 30), 365)
	demand = get_historical_inventory_demand({"company": filters.company, "branch": filters.branch, "as_of_date": filters.as_of_date, "lookback_days": lookback_days})
	replenishment = get_inventory_replenishment({"company": filters.company, "branch": filters.branch})
	if len(demand.get("rows") or []) > MAX_INVENTORY_FORECAST_ITEMS:
		frappe.throw(_("Inventory forecast scope is too broad. Narrow Branch, Warehouse, Item Group, or Item."))
	reorder_map = {str(row.get("item_code")): row for row in replenishment.get("items") or [] if row.get("item_code")}
	rows = []
	as_of = getdate(filters.as_of_date)
	for item in demand.get("rows") or []:
		item_code = str(item.get("item_code") or "")
		avg_daily = max(flt(item.get("average_daily_demand")), 0.0)
		reorder = reorder_map.get(item_code) or {}
		current_projected = flt(reorder.get("recommended_reorder_qty"))
		for step in range(1, filters.forecast_months + 1):
			period = getdate(add_months(get_first_day(as_of), step if as_of == getdate(get_last_day(as_of)) else step - 1))
			days = monthrange(period.year, period.month)[1]
			forecast_qty = avg_daily * days
			planned_qty = forecast_qty * (1 + filters.inventory_safety_percent / 100.0)
			rows.append({
				"period_start": period.isoformat(),
				"item_code": item_code,
				"item_name": item.get("item_name") or item_code,
				"stock_uom": item.get("stock_uom") or "",
				"forecast_demand_qty": forecast_qty,
				"planned_demand_qty": planned_qty,
				"current_projected_qty": current_projected,
				"replenishment_status": reorder.get("replenishment_status") or "No reorder rule",
			})
	return {
		"key": "inventory",
		"title": _("Inventory Demand"),
		"rows": rows,
		"source": "Observed outward ERPNext Stock Ledger demand + ERPNext Item Reorder / Bin",
		"metadata": {"lookback_days": lookback_days, "forecast_method": "Average observed daily demand × calendar days", "safety_allowance_percent": filters.inventory_safety_percent, "creates_material_request": False},
	}


def _monthly_gl_actuals(company: str, from_date: str, to_date: str, *, root_type: str) -> list[dict[str, Any]]:
	if not frappe.has_permission("GL Entry", "read"):
		frappe.throw(_("You do not have permission to read ERPNext General Ledger entries."), frappe.PermissionError)
	rows = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(gle.posting_date, '%%Y-%%m-01') period_start,
		       COUNT(gle.name) row_count,
		       COALESCE(SUM(CASE WHEN acc.root_type = 'Income' THEN gle.credit - gle.debit ELSE gle.debit - gle.credit END), 0) actual
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		WHERE gle.company = %s AND acc.company = %s AND acc.root_type = %s
		  AND gle.posting_date BETWEEN %s AND %s
		  AND COALESCE(gle.is_cancelled, 0) = 0
		GROUP BY DATE_FORMAT(gle.posting_date, '%%Y-%%m-01')
		ORDER BY period_start ASC
		LIMIT %s
		""",
		values=[company, company, root_type, from_date, to_date, MAX_GL_SCAN_ROWS + 1],
		as_dict=True,
	)
	if len(rows) > MAX_GL_SCAN_ROWS:
		frappe.throw(_("Accounting forecast scope is too broad. Narrow the history window."))
	by_period = {str(row.period_start): flt(row.actual) for row in rows}
	return [{"period_start": period, "actual": by_period.get(period, 0.0)} for period in _month_starts(from_date, to_date)]


def _flatten_domain_rows(domains: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for key in ("sales", "cash", "expenses", "profitability"):
		domain = domains.get(key) or {}
		if not domain.get("available"):
			continue
		for row in domain.get("actual_rows") or []:
			actual = row.get("actual") if "actual" in row else row.get("net_sales")
			rows.append({"domain": domain.get("title") or key, "period_start": row.get("period_start"), "row_type": _("Actual"), "actual": actual, "forecast": None, "plan": None, "variance": None})
		for row in domain.get("future_rows") or []:
			rows.append({"domain": domain.get("title") or key, "period_start": row.get("period_start"), "row_type": _("Forecast / Plan"), "actual": None, "forecast": row.get("forecast"), "plan": row.get("plan"), "variance": flt(row.get("plan")) - flt(row.get("forecast"))})
	rows.sort(key=lambda row: (str(row.get("period_start") or ""), str(row.get("domain") or ""), str(row.get("row_type") or "")))
	return rows


def _summary_cards(domains: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	def future_total(key: str, field: str) -> float:
		domain = domains.get(key) or {}
		return sum(flt(row.get(field)) for row in domain.get("future_rows") or []) if domain.get("available") else 0.0
	return [
		{"label": _("Sales Forecast"), "value": future_total("sales", "forecast"), "datatype": "Currency"},
		{"label": _("Sales Plan"), "value": future_total("sales", "plan"), "datatype": "Currency"},
		{"label": _("Cash Plan"), "value": future_total("cash", "plan"), "datatype": "Currency"},
		{"label": _("Expense Plan"), "value": future_total("expenses", "plan"), "datatype": "Currency"},
		{"label": _("Profit Plan"), "value": future_total("profitability", "plan"), "datatype": "Currency"},
	]


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "domain", "label": _("Domain"), "fieldtype": "Data"},
		{"fieldname": "period_start", "label": _("Month"), "fieldtype": "Date"},
		{"fieldname": "row_type", "label": _("Type"), "fieldtype": "Data"},
		{"fieldname": "actual", "label": _("Actual"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "forecast", "label": _("Forecast"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "plan", "label": _("Plan"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "variance", "label": _("Plan vs Forecast"), "fieldtype": "Currency", "options": currency},
	]


def _summary_value(cards: list[dict[str, Any]], label: str) -> float:
	for card in cards:
		if str(card.get("label") or "") == label:
			return flt(card.get("value"))
	return 0.0


def _completed_month_window(as_of_date: str, history_months: int) -> tuple[str, str, str]:
	as_of = getdate(as_of_date)
	if as_of == getdate(get_last_day(as_of)):
		history_end = as_of
		forecast_start = getdate(add_months(get_first_day(as_of), 1))
	else:
		forecast_start = getdate(get_first_day(as_of))
		history_end = forecast_start - timedelta(days=1)
	history_start = getdate(add_months(get_first_day(history_end), -(history_months - 1)))
	return history_start.isoformat(), history_end.isoformat(), forecast_start.isoformat()


def _month_starts(from_date: str, to_date: str) -> list[str]:
	current = getdate(get_first_day(from_date))
	end = getdate(get_first_day(to_date))
	rows: list[str] = []
	while current <= end:
		rows.append(current.isoformat())
		current = getdate(add_months(current, 1))
	return rows


def _bounded_int(value: Any, default: int, minimum: int, maximum: int, label: str) -> int:
	try:
		resolved = default if value in (None, "") else int(value)
	except (TypeError, ValueError):
		frappe.throw(_("{0} must be a whole number.").format(label))
	if resolved < minimum or resolved > maximum:
		frappe.throw(_("{0} must be between {1} and {2}.").format(label, minimum, maximum))
	return resolved


def _bounded_percent(value: Any, minimum: float, maximum: float, label: str) -> float:
	try:
		resolved = flt(value or 0)
	except (TypeError, ValueError):
		frappe.throw(_("Invalid percentage for {0}.").format(label))
	if resolved < minimum or resolved > maximum:
		frappe.throw(_("{0} must be between {1}% and {2}%.").format(label, minimum, maximum))
	return resolved
