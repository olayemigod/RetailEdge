from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from retailedge.customer_receivables import get_customer_receivables_export
from retailedge.financial_position import get_financial_position
from retailedge.supplier_payables import get_supplier_payables_export

DEFAULT_HORIZON_DAYS = 30
MAX_HORIZON_DAYS = 90


@frappe.whitelist()
def get_liquidity_control(filters: dict[str, Any] | str | None = None, horizon_days: int | str = DEFAULT_HORIZON_DAYS) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	horizon = max(1, min(cint(horizon_days) or DEFAULT_HORIZON_DAYS, MAX_HORIZON_DAYS))
	company = str(resolved.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	resolved.company = company

	position = get_financial_position(resolved)
	receivables = get_customer_receivables_export(resolved)
	payables_filters = frappe._dict(resolved)
	payables_filters.as_of_date = nowdate()
	payables = get_supplier_payables_export(payables_filters)
	return _build_liquidity_control(position, receivables, payables, horizon_days=horizon)


def _build_liquidity_control(
	position: dict[str, Any],
	receivables: dict[str, Any],
	payables: dict[str, Any],
	*,
	horizon_days: int,
) -> dict[str, Any]:
	today_date = getdate(nowdate())
	horizon_date = getdate(add_days(today_date, horizon_days))
	cash_card = _card_by_label(position.get("current_position") or [], "Cash & Bank Balance")
	cash_available = bool(cash_card and cash_card.get("available"))
	cash_balance = flt(cash_card.get("value")) if cash_available else None

	receivable_rows = list(receivables.get("rows") or [])
	payable_rows = list(payables.get("rows") or [])
	collections_due = sum(
		flt(row.get("outstanding"))
		for row in receivable_rows
		if _due_within_horizon(row.get("due_date"), today_date=today_date, horizon_date=horizon_date)
	)
	obligations_due = sum(
		flt(row.get("outstanding"))
		for row in payable_rows
		if _due_within_horizon(row.get("due_date"), today_date=today_date, horizon_date=horizon_date)
	)
	overdue_receivables = sum(
		flt(row.get("outstanding")) for row in receivable_rows if int(row.get("overdue_days") or 0) > 0
	)
	overdue_payables = sum(
		flt(row.get("outstanding")) for row in payable_rows if int(row.get("overdue_days") or 0) > 0
	)

	immediate_coverage = _ratio(cash_balance, obligations_due) if cash_available else None
	indicative_coverage = _ratio((cash_balance or 0.0) + collections_due, obligations_due) if cash_available else None
	indicative_gap = ((cash_balance or 0.0) + collections_due - obligations_due) if cash_available else None
	period = {str(card.get("label") or ""): card for card in position.get("selected_period") or []}

	return {
		"title": _("Cash-flow & Liquidity Control"),
		"as_of_date": nowdate(),
		"horizon_days": horizon_days,
		"horizon_date": str(horizon_date),
		"current_liquidity": {
			"cash_bank_balance": cash_balance,
			"cash_bank_available": cash_available,
			"cash_bank_unavailable_reason": (cash_card or {}).get("reason") or "",
			"receivables_due_within_horizon": collections_due,
			"supplier_obligations_due_within_horizon": obligations_due,
			"overdue_receivables": overdue_receivables,
			"overdue_payables": overdue_payables,
			"immediate_obligation_coverage_ratio": immediate_coverage,
			"indicative_coverage_ratio_including_due_receivables": indicative_coverage,
			"indicative_liquidity_gap": indicative_gap,
		},
		"period_flow": {
			"money_in": _available_value(period.get("Money In")),
			"money_out": _available_value(period.get("Money Out")),
			"net_cash_movement": _available_value(period.get("Net Cash Movement")),
		},
		"metadata": {
			"cash_balance_definition": "ERPNext closing balance of permitted company-level Cash/Bank accounts; not selected-period movement.",
			"due_receivables_definition": "Current outstanding customer invoices whose due date is on or before the horizon date; not a cash forecast or guaranteed collection.",
			"due_obligations_definition": "Current outstanding supplier invoices whose due date is on or before the horizon date; not a payment instruction.",
			"coverage_definition": "Indicative management ratio only. It does not model payment timing, disputes, unrecorded obligations, financing facilities or collection probability.",
			"branch_limit": "If a safe ERPNext branch accounting balance is unavailable, cash-based liquidity ratios are withheld rather than inferred from branch transaction movement.",
		},
		"scan": {
			"receivables": receivables.get("scan") or {},
			"payables": payables.get("scan") or {},
		},
	}


def _due_within_horizon(value: Any, *, today_date, horizon_date) -> bool:
	if not value:
		return False
	due_date = getdate(value)
	return due_date <= horizon_date


def _card_by_label(cards: list[dict[str, Any]], label: str) -> dict[str, Any] | None:
	for card in cards:
		if str(card.get("label") or "").strip() == label:
			return card
	return None


def _available_value(card: dict[str, Any] | None) -> float | None:
	if not card or not card.get("available"):
		return None
	return flt(card.get("value"))


def _ratio(numerator: float | None, denominator: float) -> float | None:
	if numerator is None or not denominator:
		return None
	return numerator / denominator


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
