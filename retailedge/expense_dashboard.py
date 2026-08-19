from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.expense_register import get_expense_register_context, get_expense_register_export

DASHBOARD_KEY = "expense-overview"
TOP_LIMIT = 10


@frappe.whitelist()
def get_expense_dashboard_context() -> dict[str, Any]:
	context = get_expense_register_context()
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
def get_expense_dashboard_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)

	current_filters = _period_filters(filters, company=company, branch=branch)
	current = get_expense_register_export(current_filters)
	rows = list(current.get("rows") or [])
	previous_filters = _previous_period_filters(current_filters)
	previous = get_expense_register_export(previous_filters) if previous_filters else {"rows": [], "summary": []}
	previous_rows = list(previous.get("rows") or [])

	account_context = _account_context(rows)
	breakdowns = {
		"category": _aggregate(rows, "expense_category"),
		"branch": _aggregate(rows, "branch"),
		"cashier": _aggregate(rows, "cashier") if any("cashier" in row for row in rows) else [],
		"funding_source": _aggregate_account_context(account_context, "payment_account"),
		"expense_account": _aggregate_account_context(account_context, "expense_account"),
		"cost_center": _aggregate_account_context(account_context, "cost_center"),
	}
	comparison = _period_comparison(rows, previous_rows, current_filters, previous_filters)
	return {
		"title": _("Expenses Dashboard"),
		"filters": current_filters,
		"headline_summary": _headline_summary(current, rows, comparison),
		"comparison": comparison,
		"breakdowns": breakdowns,
		"attention": _attention_items(current, breakdowns, comparison),
		"recent_expenses": rows[:8],
		"routes": {
			"expense_register": "/app/expense-register",
			"expense_review": "/app/expense-review",
		},
		"metadata": {
			"composition": "existing_expense_register_engine",
			"account_context_visible": bool(account_context),
			"judgement_basis": "trend_concentration_and_control_signals_not_budget_compliance",
			"budget_note": _("Budget compliance is not inferred unless an explicit budget or target is configured."),
		},
	}


def build_expense_dashboard_export_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	result = get_expense_dashboard_data(filters)
	rows: list[dict[str, Any]] = []
	for card in result.get("headline_summary") or []:
		rows.append({"section": _("Headline"), "dimension": "", "metric": card.get("label"), "value": card.get("value")})
	for key, values in (result.get("breakdowns") or {}).items():
		for row in values:
			rows.append(
				{
					"section": _("Spend Breakdown"),
					"dimension": key.replace("_", " ").title(),
					"metric": row.get("label"),
					"value": row.get("amount"),
				}
			)
	return {
		"title": _("Expenses Dashboard"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 160},
			{"fieldname": "dimension", "label": _("Dimension"), "fieldtype": "Data", "width": 160},
			{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 220},
			{"fieldname": "value", "label": _("Value"), "fieldtype": "Currency", "width": 160},
		],
		"rows": rows,
		"summary": result.get("headline_summary") or [],
		"filters": result.get("filters") or {},
	}


def _period_filters(filters: frappe._dict, *, company: str, branch: str) -> dict[str, Any]:
	return {
		"company": company,
		"branch": branch,
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
		"expense_category": filters.get("expense_category") or "",
		"expense_status": filters.get("expense_status") or "",
	}


def _previous_period_filters(filters: dict[str, Any]) -> dict[str, Any] | None:
	if not filters.get("from_date") or not filters.get("to_date"):
		return None
	start = getdate(filters["from_date"])
	end = getdate(filters["to_date"])
	if start > end:
		return None
	days = date_diff(end, start) + 1
	previous_end = start - timedelta(days=1)
	previous_start = previous_end - timedelta(days=days - 1)
	return {**filters, "from_date": str(previous_start), "to_date": str(previous_end)}


def _period_comparison(
	current_rows: list[dict[str, Any]],
	previous_rows: list[dict[str, Any]],
	current_filters: dict[str, Any],
	previous_filters: dict[str, Any] | None,
) -> dict[str, Any]:
	current_total = sum(flt(row.get("amount")) for row in current_rows)
	previous_total = sum(flt(row.get("amount")) for row in previous_rows)
	current_days = _period_days(current_filters)
	previous_days = _period_days(previous_filters or {})
	change_pct = ((current_total - previous_total) / previous_total * 100) if previous_total else None
	return {
		"current_total": current_total,
		"previous_total": previous_total,
		"change_amount": current_total - previous_total,
		"change_pct": change_pct,
		"current_daily_average": current_total / current_days if current_days else 0,
		"previous_daily_average": previous_total / previous_days if previous_days else 0,
		"previous_period_available": bool(previous_filters),
		"current_days": current_days,
		"previous_days": previous_days,
	}


def _period_days(filters: dict[str, Any]) -> int:
	if not filters.get("from_date") or not filters.get("to_date"):
		return 0
	return max(1, date_diff(getdate(filters["to_date"]), getdate(filters["from_date"])) + 1)


def _aggregate(rows: list[dict[str, Any]], fieldname: str) -> list[dict[str, Any]]:
	buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"amount": 0.0, "count": 0})
	for row in rows:
		label = str(row.get(fieldname) or _("Unspecified")).strip() or _("Unspecified")
		buckets[label]["amount"] += flt(row.get("amount"))
		buckets[label]["count"] += 1
	total = sum(bucket["amount"] for bucket in buckets.values())
	result = [
		{
			"label": label,
			"amount": values["amount"],
			"count": values["count"],
			"share_pct": (values["amount"] / total * 100) if total else 0,
		}
		for label, values in buckets.items()
	]
	result.sort(key=lambda row: (-flt(row["amount"]), row["label"]))
	return result[:TOP_LIMIT]


def _account_context(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	if not rows or not frappe.has_permission("Account", "read"):
		return []
	names = [str(row.get("name") or "").strip() for row in rows if row.get("name")]
	if not names:
		return []
	context_rows = frappe.get_list(
		"RetailEdge Cashier Expense",
		filters={"name": ["in", names]},
		fields=["name", "amount", "payment_account", "expense_account", "cost_center"],
		limit_page_length=min(len(names), 5000),
	)
	return [dict(row) for row in context_rows]


def _aggregate_account_context(rows: list[dict[str, Any]], fieldname: str) -> list[dict[str, Any]]:
	return _aggregate(rows, fieldname) if rows else []


def _headline_summary(source: dict[str, Any], rows: list[dict[str, Any]], comparison: dict[str, Any]) -> list[dict[str, Any]]:
	total = sum(flt(row.get("amount")) for row in rows)
	count = len(rows)
	cards = [
		{"label": _("Total Expenses"), "value": total, "datatype": "Currency"},
		{"label": _("Expense Count"), "value": count, "datatype": "Int"},
		{"label": _("Average Expense"), "value": total / count if count else 0, "datatype": "Currency"},
		{"label": _("Daily Spend"), "value": comparison.get("current_daily_average") or 0, "datatype": "Currency"},
	]
	for label in ("Submitted for Review", "Posting Blocked"):
		card = _summary_card(source, label)
		if card:
			cards.append({**card, "datatype": card.get("datatype") or card.get("type") or "Int"})
	return cards


def _attention_items(source: dict[str, Any], breakdowns: dict[str, list[dict[str, Any]]], comparison: dict[str, Any]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	blocked = _summary_card(source, "Posting Blocked")
	if blocked and flt(blocked.get("value")) > 0:
		items.append({"label": _("Expenses are blocked from ledger posting"), "value": blocked.get("value"), "datatype": "Int", "tone": "danger", "route": "/app/expense-review"})
	review = _summary_card(source, "Submitted for Review")
	if review and flt(review.get("value")) > 0:
		items.append({"label": _("Expenses are waiting for review"), "value": review.get("value"), "datatype": "Int", "tone": "warning", "route": "/app/expense-review"})
	change_pct = comparison.get("change_pct")
	if change_pct is not None and change_pct >= 20:
		items.append({"label": _("Spend increased materially versus the previous equal period"), "value": change_pct, "datatype": "Percent", "tone": "warning", "route": "/app/expense-register"})
	categories = breakdowns.get("category") or []
	if categories and flt(categories[0].get("share_pct")) >= 50:
		items.append({"label": _("One expense category represents at least half of spending"), "value": categories[0].get("share_pct"), "datatype": "Percent", "tone": "warning", "route": "/app/expense-register", "detail": categories[0].get("label")})
	return items


def _summary_card(payload: dict[str, Any], label: str) -> dict[str, Any] | None:
	for card in payload.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return dict(card)
	return None


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
