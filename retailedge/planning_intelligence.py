from __future__ import annotations

from calendar import monthrange
from datetime import timedelta
from math import isfinite
from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from retailedge.budget_spend_control import get_budget_spend_control
from retailedge.cash_movement import get_cash_movement
from retailedge.customer_receivables import get_customer_receivables_export
from retailedge.forecasting import MAX_FORECAST_HORIZON, apply_plan_adjustment, build_baseline_forecast
from retailedge.inventory_demand import get_historical_inventory_demand
from retailedge.inventory_replenishment import get_inventory_replenishment
from retailedge.planning_scope import resolve_planning_branch_scope
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
	return _build_planning_export(dataset)


@frappe.whitelist()
def get_planning_action_summary(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return bounded read-only planning signals without assembling the full planning workspace."""
	resolved = _normalise_filters(filters)
	items: list[dict[str, Any]] = []
	cash = _safe_domain("cash", lambda: _cash_domain(resolved, include_commitments=False))
	profit = _safe_domain("profitability", lambda: _profitability_domain(resolved))
	inventory = _safe_domain("inventory", lambda: _inventory_risk_signal(resolved))

	if cash.get("available") and any(flt(row.get("plan")) < 0 for row in cash.get("future_rows") or []):
		items.append(_action("cash_plan_negative", _("Planned net cash movement is negative in at least one forecast month"), "warning"))
	if profit.get("available") and any(flt(row.get("forecast")) < 0 for row in profit.get("future_rows") or []):
		items.append(_action("profit_forecast_negative", _("Accounting profit forecast is negative in at least one forecast month"), "danger"))
	at_risk_count = int(inventory.get("at_risk_count") or 0) if inventory.get("available") else 0
	if at_risk_count:
		items.append({
			**_action("inventory_plan_shortfall", _("Planned cumulative demand exceeds current projected stock for some items"), "warning"),
			"value": at_risk_count,
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
	resolved.branch = resolve_planning_branch_scope(resolved.company, resolved.get("branch"))
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
			"inventory_truth": "Observed ERPNext Stock Ledger demand plus permission-safe current Bin projected quantity and Item Reorder context; projected-stock coverage is available only for today's as-of date",
			"scenario_truth": "RetailEdge Planning Scenario stores explicit planning assumptions and an immutable forecast/plan snapshot; forecasted accounting and stock transactions are never persisted",
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


def _cash_domain(filters: frappe._dict, *, include_commitments: bool = True) -> dict[str, Any]:
	start, end, forecast_start = _completed_month_window(filters.as_of_date, filters.history_months)
	actuals: list[dict[str, Any]] = []
	for period_start in _month_starts(start, end):
		payload = get_cash_movement(
			{
				"company": filters.company,
				"branch": filters.branch,
				"from_date": period_start,
				"to_date": str(get_last_day(period_start)),
			},
			page=1,
			page_size=1,
		)
		actuals.append({"period_start": period_start, "actual": _summary_value(payload.get("summary") or [], "net_change", _("Net Change"))})
	forecast = build_baseline_forecast(actuals, horizon=filters.forecast_months, period="Monthly", as_of_date=end)
	planned = apply_plan_adjustment(forecast["rows"], adjustment_percent=filters.cash_adjustment_percent)
	future_periods = [row["period_start"] for row in planned]
	commitments = _cash_commitment_schedule(filters, future_periods) if include_commitments else {
		"rows": [],
		"metadata": {"available": False, "reason": "Omitted from lightweight Action Centre signal."},
	}
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
			"commitment_separation": "Current submitted receivable/payable due amounts are evidence only; collection/payment is not assumed or automatically added to the historical-behaviour cash forecast, avoiding double counting.",
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
			"closing_entry_policy": "Period Closing Voucher entries are excluded to match ERPNext Profit and Loss closing-entry semantics.",
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
			"closing_entry_policy": "Period Closing Voucher entries are excluded to match ERPNext Profit and Loss closing-entry semantics.",
		},
	}


def _inventory_domain(filters: frappe._dict) -> dict[str, Any]:
	_require_current_inventory_snapshot(filters)
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
			"coverage_semantics": "Today's Bin projected quantity is compared with cumulative planned demand through each forecast month. Historical projected-stock reconstruction is intentionally not invented.",
			"projected_stock_snapshot": "Current stock-position projected quantity as of scenario generation time, not recommended reorder quantity",
			"historical_as_of_supported": False,
			"creates_material_request": False,
		},
	}


def _inventory_risk_signal(filters: frappe._dict) -> dict[str, Any]:
	"""Return only the predictive inventory count needed by Action Centre."""
	_require_current_inventory_snapshot(filters)
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
	periods = _forecast_period_starts(filters.as_of_date, filters.forecast_months)
	at_risk: set[str] = set()
	for item in demand.get("rows") or []:
		item_code = str(item.get("item_code") or "")
		if not item_code:
			continue
		avg_daily = max(flt(item.get("average_daily_demand")), 0.0)
		planned = sum(
			avg_daily * monthrange(getdate(period).year, getdate(period).month)[1] * (1 + filters.inventory_safety_percent / 100.0)
			for period in periods
		)
		if planned > stock_map.get(item_code, 0.0):
			at_risk.add(item_code)
	return {"key": "inventory", "at_risk_count": len(at_risk)}


def _require_current_inventory_snapshot(filters: frappe._dict) -> None:
	if getdate(filters.as_of_date) != getdate(nowdate()):
		frappe.throw(
			_(
				"Historical Inventory Planning is unavailable because current projected stock cannot be mixed with historical demand. "
				"Use today's As of Date; saved scenarios preserve the inventory risk snapshot captured when they are saved."
			)
		)


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
			"voucher_type": ["!=", "Period Closing Voucher"],
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
		{"key": "sales_forecast", "label": _("Sales Forecast"), "value": total("sales", "forecast"), "datatype": "Currency"},
		{"key": "sales_plan", "label": _("Sales Plan"), "value": total("sales", "plan"), "datatype": "Currency"},
		{"key": "cash_plan", "label": _("Cash Plan"), "value": total("cash", "plan"), "datatype": "Currency"},
		{"key": "expense_plan", "label": _("Expense Plan"), "value": total("expenses", "plan"), "datatype": "Currency"},
		{"key": "accounting_profit_forecast", "label": _("Accounting Profit Forecast"), "value": total("profitability", "forecast"), "datatype": "Currency"},
	]
	budget = domains.get("budget") or {}
	if budget.get("available"):
		remaining = _find_summary_card(budget.get("summary") or [], "remaining_budget", _("Remaining Budget"))
		used = _find_summary_card(budget.get("summary") or [], "budget_used", _("Budget Used"))
		if remaining and remaining.get("value") is not None:
			cards.append({"key": "current_period_budget_remaining", "label": _("Current Period Budget Remaining"), "value": remaining.get("value"), "datatype": "Currency"})
		if used and used.get("value") is not None:
			cards.append({"key": "current_period_budget_used", "label": _("Current Period Budget Used"), "value": used.get("value"), "datatype": "Percent"})
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


def _build_planning_export(dataset: dict[str, Any]) -> dict[str, Any]:
	currency = str(dataset.get("company_currency") or "")
	rows: list[dict[str, Any]] = []
	for row in dataset.get("rows") or []:
		for fieldname, metric in (
			("actual", _("Actual")),
			("forecast", _("Forecast")),
			("plan", _("Plan")),
			("variance", _("Plan vs Forecast")),
		):
			if row.get(fieldname) is None:
				continue
			_append_export_metric(
				rows,
				domain=row.get("domain"),
				section=_("Planning Timeline"),
				period_start=row.get("period_start"),
				metric=metric,
				value=row.get(fieldname),
				unit=currency,
				status=row.get("row_type"),
			)

	domains = dataset.get("domains") or {}
	cash = domains.get("cash") or {}
	if cash.get("available"):
		for row in cash.get("commitment_rows") or []:
			for fieldname, metric in (
				("receivables_due", _("Receivables Due")),
				("payables_due", _("Payables Due")),
				("net_known_due", _("Net Known Due")),
			):
				_append_export_metric(rows, domain=_("Cash Movement"), section=_("Known Due Commitments"), period_start=row.get("period_start"), metric=metric, value=row.get(fieldname), unit=currency)

	inventory = domains.get("inventory") or {}
	if inventory.get("available"):
		for row in inventory.get("rows") or []:
			status = _("Coverage risk") if row.get("coverage_risk") else _("Covered")
			notes = str(row.get("replenishment_status") or "")
			for fieldname, metric in (
				("forecast_demand_qty", _("Forecast Demand")),
				("planned_demand_qty", _("Planned Demand + Safety")),
				("cumulative_planned_demand_qty", _("Cumulative Planned Demand")),
				("current_projected_qty", _("Projected Stock")),
				("coverage_shortfall_qty", _("Coverage Shortfall")),
			):
				_append_export_metric(
					rows,
					domain=_("Inventory Demand"),
					section=_("Inventory Coverage"),
					period_start=row.get("period_start"),
					reference=row.get("item_code"),
					metric=metric,
					value=row.get(fieldname),
					unit=row.get("stock_uom"),
					status=status,
					notes=notes,
				)

	budget = domains.get("budget") or {}
	if budget.get("available"):
		for card in budget.get("summary") or []:
			_append_export_metric(
				rows,
				domain=_("Budget & Spend Governance"),
				section=_("Budget Summary"),
				metric=card.get("label"),
				value=card.get("value"),
				unit=_export_unit(card.get("datatype"), currency),
				status=_("Available") if card.get("available", True) else _("Unavailable"),
			)
		for control in budget.get("controls") or []:
			_append_export_metric(
				rows,
				domain=_("Budget & Spend Governance"),
				section=_("Budget Controls"),
				reference=control.get("category") or control.get("family"),
				metric=control.get("label"),
				value=control.get("value"),
				unit=_export_unit(control.get("datatype"), currency),
				status=control.get("severity"),
			)

	for key, value in (dataset.get("assumptions") or {}).items():
		_append_export_metric(
			rows,
			domain=_("Planning Scenario"),
			section=_("Assumptions"),
			metric=key.replace("_", " ").title(),
			value=value,
			unit="%",
		)

	for key, domain in domains.items():
		if domain and domain.get("available") is False:
			_append_export_metric(
				rows,
				domain=domain.get("title") or key.replace("_", " ").title(),
				section=_("Availability"),
				metric=_("Domain Status"),
				status=_("Unavailable"),
				notes=domain.get("reason"),
			)

	return {
		"title": dataset.get("title") or _("Forecasting & Planning"),
		"columns": _export_columns(),
		"rows": rows,
		"summary": dataset.get("summary") or [],
		"company_currency": currency,
		"metadata": {
			**(dataset.get("metadata") or {}),
			"export_contract": "Long-form shared EdgeSuite dataset covering planning timeline, known due commitments, inventory coverage, budget governance, assumptions, and domain availability.",
		},
	}


def _append_export_metric(
	rows: list[dict[str, Any]],
	*,
	domain: Any,
	section: Any,
	metric: Any,
	value: Any = None,
	period_start: Any = None,
	reference: Any = None,
	unit: Any = None,
	status: Any = None,
	notes: Any = None,
) -> None:
	rows.append({
		"domain": str(domain or ""),
		"section": str(section or ""),
		"period_start": str(period_start or ""),
		"reference": str(reference or ""),
		"metric": str(metric or ""),
		"value": value,
		"unit": str(unit or ""),
		"status": str(status or ""),
		"notes": str(notes or ""),
	})


def _export_columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "domain", "label": _("Domain"), "fieldtype": "Data"},
		{"fieldname": "section", "label": _("Section"), "fieldtype": "Data"},
		{"fieldname": "period_start", "label": _("Period"), "fieldtype": "Data"},
		{"fieldname": "reference", "label": _("Reference"), "fieldtype": "Data"},
		{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data"},
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Data"},
		{"fieldname": "unit", "label": _("Unit"), "fieldtype": "Data"},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data"},
		{"fieldname": "notes", "label": _("Notes"), "fieldtype": "Data"},
	]


def _export_unit(datatype: Any, currency: str) -> str:
	if datatype == "Currency":
		return currency
	if datatype == "Percent":
		return "%"
	return str(datatype or "")


def _summary_value(cards: list[dict[str, Any]], key: str, label: str | None = None) -> float:
	card = _find_summary_card(cards, key, label)
	return flt(card.get("value")) if card else 0.0


def _find_summary_card(cards: list[dict[str, Any]], key: str, label: str | None = None) -> dict[str, Any] | None:
	for card in cards:
		if str(card.get("key") or "") == key:
			return card
	if label is not None:
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
	if not isfinite(resolved):
		frappe.throw(_("{0} must be a finite percentage.").format(label))
	if resolved < minimum or resolved > maximum:
		frappe.throw(_("{0} must be between {1}% and {2}%.").format(label, minimum, maximum))
	return resolved
