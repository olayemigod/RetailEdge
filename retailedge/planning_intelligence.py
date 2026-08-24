from __future__ import annotations

from calendar import monthrange
from datetime import timedelta
from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from retailedge.budget_spend_control import get_budget_spend_control
from retailedge.cash_movement import get_cash_movement_export
from retailedge.customer_receivables import get_customer_receivables_export
from retailedge.forecasting import MAX_FORECAST_HORIZON, apply_plan_adjustment, build_baseline_forecast
from retailedge.inventory_demand import get_historical_inventory_demand
from retailedge.inventory_replenishment import get_inventory_replenishment
from retailedge.sales_forecasting import get_sales_forecast
from retailedge.sales_reporting import _company_currency, _coerce_filters
from retailedge.stock_position import get_stock_position_export
from retailedge.supplier_payables import get_supplier_payables_export

DEFAULT_HISTORY_MONTHS = 6
DEFAULT_HORIZON_MONTHS = 3
MAX_HISTORY_MONTHS = 24
MAX_GL_SCAN_ROWS = 30000
MAX_ACCOUNT_SCOPE = 5000
MAX_INVENTORY_FORECAST_ITEMS = 5000


@frappe.whitelist()
def get_planning_intelligence(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	return _build_planning_dataset(_normalise_filters(filters))


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
	"""Return read-only planning signals without creating parallel transaction truth."""
	data = get_planning_intelligence(filters)
	items: list[dict[str, Any]] = []
	cash = data.get("domains", {}).get("cash") or {}
	profit = data.get("domains", {}).get("profitability") or {}
	inventory = data.get("domains", {}).get("inventory") or {}

	if cash.get("available") and any(flt(row.get("plan")) < 0 for row in cash.get("future_rows") or []):
		items.append(_action("cash_plan_negative", _("Planned net cash movement is negative in at least one forecast month"), "warning"))
	if profit.get("available") and any(flt(row.get("forecast")) < 0 for row in profit.get("future_rows") or []):
		items.append(_action("profit_forecast_negative", _("Accounting profit forecast is negative in at least one forecast month"), "danger"))
	at_risk_items = {
		str(row.get("item_code") or "")
		for row in inventory.get("rows") or []
		if row.get("coverage_risk") and row.get("item_code")
	}
	if inventory.get("available") and at_risk_items:
		items.append({
			**_action("inventory_plan_shortfall", _("Planned cumulative demand exceeds current projected stock for some items"), "warning"),
			"value": len(at_risk_items),
			"datatype": "Int",
		})
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
	if getdate(resolved.as_of_date) > getdate(nowdate()):
		frappe.throw(_("As of Date cannot be in the future."))
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
	expenses = _safe_domain("expenses", lambda: _expense_domain(filters))
	profitability = _safe_domain("profitability", lambda: _profitability_domain(filters))
	inventory = _safe_domain("inventory", lambda: _inventory_domain(filters))
	budget = _safe_domain("budget", lambda: _budget_reference(filters))

	domains = {
		"sales": sales,
		"cash": cash,
		"expenses": expenses,
		"profitability": profitability,
		"inventory": inventory,
		"budget": budget,
	}
	return {
		"title": _("Forecasting & Planning"),
		"columns": _columns(currency),
		"rows": _flatten_domain_rows(domains),
		"summary": _summary_cards(domains),
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
			"accounting_truth": "ERPNext General Ledger / Profit and Loss semantics remain authoritative for posted accounting results",
			"sales_truth": "Submitted ERPNext Sales Invoice / Sales Invoice Item",
			"cash_truth": "Posted ERPNext GL cash/bank movement through RetailEdge Cash Movement; current receivable/payable due dates are shown separately and are not assumed to be paid",
			"budget_truth": "Submitted ERPNext Budget remains authoritative; R12 reuses R9 Budget & Spend Governance as a reference and does not create another budget ledger",
			"inventory_truth": "Observed ERPNext Stock Ledger demand plus permission-safe current Bin projected quantity and Item Reorder context",
			"scenario_truth": "RetailEdge Planning Scenario stores assumptions only; forecasted accounting and stock transactions are never persisted",
			"branch_accounting_policy": "Accounting expense/profit forecasts fail closed at Branch scope until valid ERPNext accounting attribution exists",
			"mutates_accounting_documents": False,
			"creates_stock_documents": False,
		},
	}


def _safe_domain(key: str, loader: Callable[[], dict[str, Any]]) -> dict[str, Any]:
	try:
		return {"available": True, **(loader() or {})}
	except frappe.PermissionError:
		return {"available": False, "key": key, "title": key.replace("_", " ").title(), "reason": _("Your permissions do not allow this forecast domain.")}
	except frappe.ValidationError as exc:
		return {"available": False, "key": key, "title": key.replace("_", " ").title(), "reason": str(exc)}


def _sales_domain(filters: frappe._dict) -> dict[str, Any]:
	payload = get_sales_forecast({
		"company": filters.company,
		"branch": filters.branch,
		"as_of_date": filters.as_of_date,
		"history_months": filters.history_months,
		"forecast_months": filters.forecast_months,
	})
	forecast_rows = [row for row in payload.get("rows") or [] if row.get("row_type") == _("Forecast")]
	planned = apply_plan_adjustment(
		[{"period_start": row["period_start"], "forecast": flt(row.get("forecast"))} for row in forecast_rows],
		adjustment_percent=filters.sales_adjustment_percent,
		floor=0.0,
	)
	return {
		"key": "sales",
		"title": _("Sales"),
		"future_rows": planned,
		"actual_rows": [row for row in payload.get("rows") or [] if row.get("row_type") == _("Actual")],
		"source": payload.get("metadata", {}).get("sales_truth"),
		"metadata": payload.get("metadata") or {},
	}


def _cash_domain(filters: frappe._dict) -> dict[str, Any]:
	start, end, forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	actuals: list[dict[str, Any]] = []
	for period_start in _month_starts(start, end):
		payload = get_cash_movement_export({
			"company": filters.company,
			"branch": filters.branch,
			"from_date": period_start,
			"to_date": str(get_last_day(period_start)),
		})
		actuals.append({"period_start": period_start, "actual": _summary_value(payload.get("summary") or [], "Net Change")})
	forecast = build_baseline_forecast(actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end)
	planned = apply_plan_adjustment(forecast["rows"], adjustment_percent=filters.cash_adjustment_percent)
	future_periods = [row["period_start"] for row in planned]
	commitments = _cash_commitment_schedule(filters, future_periods)
	return {
		"key": "cash",
		"title": _("Cash Movement"),
		"actual_rows": actuals,
		"future_rows": planned,
		"commitment_rows": commitments["rows"],
		"source": "Posted ERPNext GL cash/bank movements",
		"metadata": {
			**forecast["metadata"],
			"forecast_start": forecast_start,
			"known_due_schedule": commitments["metadata"],
			"commitment_separation": "Current submitted receivable/payable due amounts are evidence only; they are not automatically added to the historical-behaviour cash forecast to avoid double counting or assuming collection/payment timing.",
		},
	}


def _cash_commitment_schedule(filters: frappe._dict, future_periods: list[str]) -> dict[str, Any]:
	if not future_periods:
		return {"rows": [], "metadata": {"available": False, "reason": "No future periods."}}
	if getdate(filters.as_of_date) != getdate(nowdate()):
		return {
			"rows": [],
			"metadata": {
				"available": False,
				"reason": "Historical receivable/payable outstanding snapshots are not reconstructed; known-due commitments are shown only for a current as-of date.",
			},
		}
	receivables = get_customer_receivables_export({"company": filters.company, "branch": filters.branch, "ageing_bucket": "All"})
	payables = get_supplier_payables_export({"company": filters.company, "branch": filters.branch})
	buckets = {
		period: {"period_start": period, "receivables_due": 0.0, "payables_due": 0.0, "net_known_due": 0.0}
		for period in future_periods
	}
	first_period = getdate(future_periods[0])
	last_period = getdate(future_periods[-1])

	def add_rows(rows: list[dict[str, Any]], field: str) -> None:
		for row in rows:
			amount = max(flt(row.get("outstanding")), 0.0)
			if not amount:
				continue
			due = getdate(row.get("due_date") or row.get("posting_date") or filters.as_of_date)
			period = getdate(get_first_day(due))
			if period < first_period:
				period = first_period
			if period > last_period:
				continue
			key = period.isoformat()
			if key in buckets:
				buckets[key][field] += amount

	add_rows(receivables.get("rows") or [], "receivables_due")
	add_rows(payables.get("rows") or [], "payables_due")
	rows = []
	for period in future_periods:
		row = buckets[period]
		row["net_known_due"] = flt(row["receivables_due"]) - flt(row["payables_due"])
		rows.append(row)
	return {
		"rows": rows,
		"metadata": {
			"available": True,
			"basis": "Current submitted ERPNext Sales Invoice and Purchase Invoice outstanding amounts grouped by due month",
			"collection_or_payment_assumed": False,
			"historical_snapshot_supported": False,
		},
	}


def _expense_domain(filters: frappe._dict) -> dict[str, Any]:
	if filters.branch:
		frappe.throw(_("Accounting expense forecast is company-level until Branch is mapped to a valid ERPNext accounting dimension or Cost Center."))
	start, end, _forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	actuals = _monthly_gl_actuals(filters.company, start, end, root_type="Expense")
	forecast = build_baseline_forecast(actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end, floor=0.0)
	planned = apply_plan_adjustment(forecast["rows"], adjustment_percent=filters.expense_adjustment_percent, floor=0.0)
	return {
		"key": "expenses",
		"title": _("Accounting Expenses"),
		"actual_rows": actuals,
		"future_rows": planned,
		"source": "Permission-aware ERPNext GL Entry on Expense root-type accounts",
		"metadata": {
			**forecast["metadata"],
			"budget_relationship": "Expense Plan is an analytical scenario. ERPNext Budget/R9 Budget & Spend Governance remains the budget truth and enforcement reference.",
		},
	}


def _profitability_domain(filters: frappe._dict) -> dict[str, Any]:
	if filters.branch:
		frappe.throw(_("Accounting profitability forecast is company-level until Branch is mapped to a valid ERPNext accounting dimension or Cost Center."))
	start, end, _forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	income_actuals = _monthly_gl_actuals(filters.company, start, end, root_type="Income")
	expense_actuals = _monthly_gl_actuals(filters.company, start, end, root_type="Expense")
	expense_actual_map = {row["period_start"]: flt(row["actual"]) for row in expense_actuals}
	actuals = [
		{"period_start": row["period_start"], "actual": flt(row["actual"]) - expense_actual_map.get(row["period_start"], 0.0)}
		for row in income_actuals
	]
	income_forecast = build_baseline_forecast(income_actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end)
	expense_forecast = build_baseline_forecast(expense_actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end)
	expense_forecast_map = {row["period_start"]: flt(row["forecast"]) for row in expense_forecast["rows"]}
	future = [
		{
			"period_start": row["period_start"],
			"forecast": flt(row["forecast"]) - expense_forecast_map.get(row["period_start"], 0.0),
			"plan": None,
			"plan_adjustment_percent": None,
		}
		for row in income_forecast["rows"]
	]
	return {
		"key": "profitability",
		"title": _("Accounting Profitability"),
		"actual_rows": actuals,
		"future_rows": future,
		"source": "Permission-aware ERPNext GL Income less Expense accounts",
		"metadata": {
			"forecast_method": "Income-root forecast less Expense-root forecast using the shared R12 engine",
			"plan_semantics": "No owner Plan overlay is applied to accounting profitability because the saved scenario does not contain a complete GL-income assumption. This avoids mixing Sales Invoice revenue with Profit & Loss GL semantics.",
			"profit_truth": "ERPNext Profit and Loss remains authoritative for posted accounting profit.",
		},
	}


def _inventory_domain(filters: frappe._dict) -> dict[str, Any]:
	lookback_days = min(max(filters.history_months * 30, 30), 365)
	demand = get_historical_inventory_demand({
		"company": filters.company,
		"branch": filters.branch,
		"as_of_date": filters.as_of_date,
		"lookback_days": lookback_days,
	})
	if len(demand.get("rows") or []) > MAX_INVENTORY_FORECAST_ITEMS:
		frappe.throw(_("Inventory forecast scope is too broad. Narrow Branch, Warehouse, Item Group, or Item."))

	stock = get_stock_position_export({
		"company": filters.company,
		"branch": filters.branch,
		"stock_status": "All",
		"include_zero": 1,
	})
	stock_map = {str(row.get("item_code")): flt(row.get("projected_qty")) for row in stock.get("rows") or [] if row.get("item_code")}
	replenishment = get_inventory_replenishment({"company": filters.company, "branch": filters.branch})
	reorder_map = {str(row.get("item_code")): row for row in replenishment.get("items") or [] if row.get("item_code")}
	forecast_periods = _forecast_period_starts(filters.as_of_date, filters.forecast_months)
	rows: list[dict[str, Any]] = []
	for item in demand.get("rows") or []:
		item_code = str(item.get("item_code") or "")
		avg_daily = max(flt(item.get("average_daily_demand")), 0.0)
		current_projected = stock_map.get(item_code, 0.0)
		reorder = reorder_map.get(item_code) or {}
		cumulative = 0.0
		for period_start in forecast_periods:
			period = getdate(period_start)
			forecast_qty = avg_daily * monthrange(period.year, period.month)[1]
			planned_qty = forecast_qty * (1 + filters.inventory_safety_percent / 100.0)
			cumulative += planned_qty
			shortfall = max(cumulative - current_projected, 0.0)
			rows.append({
				"period_start": period_start,
				"item_code": item_code,
				"item_name": item.get("item_name") or item_code,
				"stock_uom": item.get("stock_uom") or "",
				"forecast_demand_qty": forecast_qty,
				"planned_demand_qty": planned_qty,
				"cumulative_planned_demand_qty": cumulative,
				"current_projected_qty": current_projected,
				"coverage_shortfall_qty": shortfall,
				"coverage_risk": bool(shortfall > 0),
				"replenishment_status": reorder.get("replenishment_status") or "No reorder rule",
			})
	return {
		"key": "inventory",
		"title": _("Inventory Demand"),
		"rows": rows,
		"source": "Observed outward ERPNext Stock Ledger demand + current permission-safe ERPNext Bin projected quantity + Item Reorder context",
		"metadata": {
			"lookback_days": lookback_days,
			"forecast_method": "Average observed daily demand × calendar days",
			"safety_allowance_percent": filters.inventory_safety_percent,
			"coverage_semantics": "Current Bin projected quantity is compared with cumulative planned demand through each forecast month. Future receipts are not invented; configured replenishment status is context only.",
			"projected_stock_snapshot": "Current stock-position projected quantity, not recommended reorder quantity",
			"creates_material_request": False,
		},
	}


def _budget_reference(filters: frappe._dict) -> dict[str, Any]:
	period_start = str(get_first_day(filters.as_of_date))
	control = get_budget_spend_control({
		"company": filters.company,
		"branch": filters.branch,
		"from_date": period_start,
		"to_date": filters.as_of_date,
	})
	if not control.get("available"):
		frappe.throw(control.get("reason") or _("ERPNext Budget reference is not available for this scope."))
	return {
		"key": "budget",
		"title": _("Budget & Spend Governance"),
		"summary": control.get("summary") or [],
		"controls": control.get("controls") or [],
		"source": "R9 Budget & Spend Governance / submitted ERPNext Budget",
		"metadata": control.get("metadata") or {},
	}


def _monthly_gl_actuals(company: str, from_date: str, to_date: str, *, root_type: str) -> list[dict[str, Any]]:
	if not frappe.has_permission("GL Entry", "read"):
		frappe.throw(_("You do not have permission to read ERPNext General Ledger entries."), frappe.PermissionError)
	accounts = frappe.get_list(
		"Account",
		filters={"company": company, "root_type": root_type, "is_group": 0},
		pluck="name",
		order_by="name asc",
		limit=MAX_ACCOUNT_SCOPE + 1,
	)
	if len(accounts) > MAX_ACCOUNT_SCOPE:
		frappe.throw(_("Accounting account scope is too broad for planning. Narrow the company/account structure."))
	periods = _month_starts(from_date, to_date)
	if not accounts:
		return [{"period_start": period, "actual": 0.0} for period in periods]
	rows = frappe.get_list(
		"GL Entry",
		filters={
			"company": company,
			"account": ["in", accounts],
			"posting_date": ["between", [from_date, to_date]],
			"is_cancelled": 0,
		},
		fields=["posting_date", "debit", "credit"],
		order_by="posting_date asc, name asc",
		limit=MAX_GL_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_GL_SCAN_ROWS:
		frappe.throw(_("More than {0} General Ledger rows match this planning window. Narrow the history window.").format(MAX_GL_SCAN_ROWS))
	by_period = {period: 0.0 for period in periods}
	for row in rows:
		period = f"{str(row.posting_date)[:7]}-01"
		if period not in by_period:
			continue
		value = flt(row.credit) - flt(row.debit) if root_type == "Income" else flt(row.debit) - flt(row.credit)
		by_period[period] += value
	return [{"period_start": period, "actual": flt(by_period.get(period))} for period in periods]


def _flatten_domain_rows(domains: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for key in ("sales", "cash", "expenses", "profitability"):
		domain = domains.get(key) or {}
		if not domain.get("available"):
			continue
		for row in domain.get("actual_rows") or []:
			actual = row.get("actual") if "actual" in row else row.get("net_sales")
			rows.append({
				"domain": domain.get("title") or key,
				"period_start": row.get("period_start"),
				"row_type": _("Actual"),
				"actual": actual,
				"forecast": None,
				"plan": None,
				"variance": None,
			})
		for row in domain.get("future_rows") or []:
			plan = row.get("plan")
			rows.append({
				"domain": domain.get("title") or key,
				"period_start": row.get("period_start"),
				"row_type": _("Forecast / Plan") if plan is not None else _("Forecast"),
				"actual": None,
				"forecast": row.get("forecast"),
				"plan": plan,
				"variance": flt(plan) - flt(row.get("forecast")) if plan is not None else None,
			})
	rows.sort(key=lambda row: (str(row.get("period_start") or ""), str(row.get("domain") or ""), str(row.get("row_type") or "")))
	return rows


def _summary_cards(domains: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	def total(key: str, field: str) -> float:
		domain = domains.get(key) or {}
		return sum(flt(row.get(field)) for row in domain.get("future_rows") or []) if domain.get("available") else 0.0

	cards = [
		{"label": _("Sales Forecast"), "value": total("sales", "forecast"), "datatype": "Currency"},
		{"label": _("Sales Plan"), "value": total("sales", "plan"), "datatype": "Currency"},
		{"label": _("Cash Plan"), "value": total("cash", "plan"), "datatype": "Currency"},
		{"label": _("Expense Plan"), "value": total("expenses", "plan"), "datatype": "Currency"},
		{"label": _("Accounting Profit Forecast"), "value": total("profitability", "forecast"), "datatype": "Currency"},
	]
	budget = domains.get("budget") or {}
	if budget.get("available"):
		remaining = _find_summary_card(budget.get("summary") or [], "Remaining Budget")
		used = _find_summary_card(budget.get("summary") or [], "Budget Used")
		if remaining and remaining.get("value") is not None:
			cards.append({"label": _("Current Period Budget Remaining"), "value": remaining.get("value"), "datatype": "Currency"})
		if used and used.get("value") is not None:
			cards.append({"label": _("Current Period Budget Used"), "value": used.get("value"), "datatype": "Percent"})
	return cards


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
	card = _find_summary_card(cards, label)
	return flt(card.get("value")) if card else 0.0


def _find_summary_card(cards: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
	for card in cards:
		if str(card.get("label") or "") == label:
			return card
	return None


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


def _forecast_period_starts(as_of_date: str, horizon: int) -> list[str]:
	_forecast_from, _forecast_to, forecast_start = _completed_month_window(as_of_date, 1)
	start = getdate(forecast_start)
	return [getdate(add_months(start, offset)).isoformat() for offset in range(horizon)]


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
