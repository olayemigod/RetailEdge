from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, today

from retailedge.action_follow_up import decorate_action_items
from retailedge.cash_shift_verification import get_cash_shift_verification
from retailedge.customer_receivables import get_customer_receivables
from retailedge.expense_register import get_expense_register
from retailedge.owner_dashboard import get_owner_dashboard_data
from retailedge.stock_position import get_stock_position
from retailedge.supplier_payables import get_supplier_payables

DEFAULT_PAGE_SIZE = 1
FOLLOW_UP_STATUSES = {"All", "Open", "Acknowledged", "Snoozed"}
ASSIGNMENT_SCOPES = {"all", "mine"}
DUE_SCOPES = {"all", "due"}


@frappe.whitelist()
def get_action_center_context() -> dict[str, Any]:
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	return {
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
			"follow_up_status": "All",
			"assignment_scope": "all",
			"due_scope": "all",
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
	}


@frappe.whitelist()
def get_action_center_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	from_date = str(filters.get("from_date") or get_first_day(today()))
	to_date = str(filters.get("to_date") or today())
	follow_up_status = _choice(filters.get("follow_up_status"), FOLLOW_UP_STATUSES, "All")
	assignment_scope = _choice(filters.get("assignment_scope"), ASSIGNMENT_SCOPES, "all")
	due_scope = _choice(filters.get("due_scope"), DUE_SCOPES, "all")
	common = {"company": company, "branch": branch, "from_date": from_date, "to_date": to_date}

	items: list[dict[str, Any]] = []
	sources: dict[str, dict[str, Any]] = {}

	owner = _safe_source("owner", lambda: get_owner_dashboard_data(common))
	sources["owner"] = owner
	if owner.get("available"):
		for item in owner.get("payload", {}).get("attention") or []:
			items.append(
				_action(
					source=str(item.get("section") or "management"),
					label=str(item.get("label") or item.get("metric") or _("Management exception")),
					value=item.get("value"),
					datatype=str(item.get("datatype") or "Data"),
					severity=str(item.get("tone") or "warning"),
					route=str(item.get("route") or "/app/owner-dashboard"),
					time_basis=str(item.get("time_basis") or "period"),
					kind="management_exception",
				)
			)
	elif _stock_fallback_allowed():
		stock = _safe_source(
			"stock_position",
			lambda: get_stock_position(
				filters={"company": company, "branch": branch},
				page=1,
				page_size=DEFAULT_PAGE_SIZE,
			),
		)
		sources["stock_position"] = stock
		if stock.get("available"):
			_append_stock_exceptions(items, stock["payload"])

	expenses = _safe_source(
		"expenses",
		lambda: get_expense_register(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
	)
	sources["expenses"] = expenses
	if expenses.get("available"):
		for label, severity, message in (
			("Posting Blocked", "danger", _("Expenses are blocked from ledger posting")),
			("Submitted for Review", "warning", _("Expenses are awaiting review")),
		):
			card = _summary_card(expenses["payload"], label)
			if card and flt(card.get("value")) > 0:
				items.append(
					_action(
						source="expenses",
						label=message,
						value=card.get("value"),
						datatype=str(card.get("datatype") or card.get("type") or "Int"),
						severity=severity,
						route="/app/expense-review",
						time_basis="period",
						kind="review_or_posting",
					)
				)

	cash = _safe_source(
		"cash_shift",
		lambda: get_cash_shift_verification(common, page=1, page_size=DEFAULT_PAGE_SIZE),
	)
	sources["cash_shift"] = cash
	if cash.get("available"):
		exceptions = _summary_card(cash["payload"], "Exceptions")
		if exceptions and flt(exceptions.get("value")) > 0:
			items.append(
				_action(
					source="cash_shift",
					label=_("Cash shifts have shortages, overages, missing shifts or review exceptions"),
					value=exceptions.get("value"),
					datatype="Int",
					severity="danger",
					route="/app/cash-shift-verification",
					time_basis="period",
					kind="cash_control",
				)
			)

	receivables = _safe_source(
		"receivables",
		lambda: get_customer_receivables(
			filters={"company": company, "branch": branch, "ageing_bucket": "All"},
			page=1,
			page_size=DEFAULT_PAGE_SIZE,
		),
	)
	sources["receivables"] = receivables
	if receivables.get("available"):
		_action_from_financial_exposure(
			items,
			payload=receivables["payload"],
			source="receivables",
			label=_("Customer receivables are overdue"),
			route="/app/customer-receivables",
			kind="overdue_receivables",
		)

	payables = _safe_source(
		"payables",
		lambda: get_supplier_payables(
			filters={"company": company, "branch": branch},
			page=1,
			page_size=DEFAULT_PAGE_SIZE,
		),
	)
	sources["payables"] = payables
	if payables.get("available"):
		_action_from_financial_exposure(
			items,
			payload=payables["payload"],
			source="payables",
			label=_("Supplier payables are overdue"),
			route="/app/supplier-payables",
			kind="overdue_payables",
		)

	all_items = decorate_action_items(_dedupe_and_sort(items), company=company, branch=branch)
	items = _apply_follow_up_filters(
		all_items,
		follow_up_status=follow_up_status,
		assignment_scope=assignment_scope,
		due_scope=due_scope,
	)
	return {
		"title": _("Action Centre"),
		"filters": {
			**common,
			"follow_up_status": follow_up_status,
			"assignment_scope": assignment_scope,
			"due_scope": due_scope,
		},
		"summary": _summary(items),
		"items": items,
		"sources": {key: {k: v for k, v in value.items() if k != "payload"} for key, value in sources.items()},
		"metadata": {
			"read_only": True,
			"follow_up_state_only": True,
			"resolution_model": "drill_through_to_existing_workflow_or_report",
			"accounting_truth": "existing ERPNext/RetailEdge documents and reporting engines",
			"generated_for": frappe.session.user,
			"unfiltered_action_count": len(all_items),
			"visible_action_count": len(items),
		},
	}


def _safe_source(key: str, loader: Callable[[], dict[str, Any]]) -> dict[str, Any]:
	try:
		return {"available": True, "key": key, "payload": loader() or {}}
	except frappe.PermissionError:
		return {"available": False, "key": key, "reason": _("Your permissions do not allow this action source.")}
	except frappe.ValidationError:
		return {
			"available": False,
			"key": key,
			"reason": _("This action source could not be evaluated safely for the current scope."),
		}


def _summary_card(payload: dict[str, Any], label: str) -> dict[str, Any] | None:
	for card in payload.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return dict(card)
	return None


def _append_stock_exceptions(items: list[dict[str, Any]], payload: dict[str, Any]) -> None:
	for metric, severity, label, kind in (
		("Negative Stock", "danger", _("Items have negative stock"), "negative_stock"),
		("Out of Stock", "warning", _("Items are out of stock"), "out_of_stock"),
		("Fully Reserved", "warning", _("Stock is fully reserved"), "fully_reserved_stock"),
	):
		card = _summary_card(payload, metric)
		if not card or flt(card.get("value")) <= 0:
			continue
		items.append(
			_action(
				source="stock",
				label=label,
				value=card.get("value"),
				datatype=str(card.get("datatype") or card.get("type") or "Int"),
				severity=severity,
				route="/app/stock-position",
				time_basis="current",
				kind=kind,
			)
		)


def _stock_fallback_allowed() -> bool:
	user = frappe.session.user
	if user in {"Guest", ""}:
		return False
	return "Stock Manager" in set(frappe.get_roles(user))


def _action_from_financial_exposure(
	items: list[dict[str, Any]],
	*,
	payload: dict[str, Any],
	source: str,
	label: str,
	route: str,
	kind: str,
) -> None:
	overdue = _summary_card(payload, "Overdue")
	if not overdue or flt(overdue.get("value")) <= 0:
		return
	over_90 = _summary_card(payload, "Over 90 Days")
	aged_exposure = flt((over_90 or {}).get("value"))
	rows = payload.get("rows") or []
	oldest_days = max((int(row.get("overdue_days") or 0) for row in rows), default=0)
	exposure = flt(overdue.get("value"))
	items.append(
		_action(
			source=source,
			label=label,
			value=exposure,
			datatype=str(overdue.get("datatype") or "Currency"),
			severity="danger" if aged_exposure > 0 else "warning",
			route=route,
			time_basis="current",
			kind=kind,
			exposure=exposure,
			aged_exposure=aged_exposure,
			age_days=oldest_days,
		)
	)


def _action(
	*,
	source: str,
	label: str,
	value: Any,
	datatype: str,
	severity: str,
	route: str,
	time_basis: str,
	kind: str,
	exposure: float | None = None,
	aged_exposure: float | None = None,
	age_days: int | None = None,
) -> dict[str, Any]:
	row = {
		"source": source,
		"label": label,
		"value": value,
		"datatype": datatype,
		"severity": severity if severity in {"danger", "warning", "info"} else "warning",
		"route": route,
		"time_basis": time_basis,
		"kind": kind,
	}
	if exposure is not None:
		row["exposure"] = exposure
	if aged_exposure is not None:
		row["aged_exposure"] = aged_exposure
	if age_days is not None:
		row["age_days"] = age_days
	return row


def _dedupe_and_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	severity_rank = {"danger": 0, "warning": 1, "info": 2}
	seen: set[tuple[str, str, str]] = set()
	result: list[dict[str, Any]] = []
	for item in items:
		key = (str(item.get("source")), str(item.get("label")), str(item.get("route")))
		if key in seen:
			continue
		seen.add(key)
		result.append(item)
	result.sort(key=lambda row: (severity_rank.get(str(row.get("severity")), 9), str(row.get("source")), str(row.get("label"))))
	return result


def _apply_follow_up_filters(
	items: list[dict[str, Any]],
	*,
	follow_up_status: str,
	assignment_scope: str,
	due_scope: str,
) -> list[dict[str, Any]]:
	result = []
	for item in items:
		state = item.get("follow_up") or {}
		if follow_up_status != "All" and state.get("effective_status", "Open") != follow_up_status:
			continue
		if assignment_scope == "mine" and state.get("assigned_to") != frappe.session.user:
			continue
		if due_scope == "due" and not state.get("is_due"):
			continue
		result.append(item)
	return result


def _summary(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Critical"), "value": len([row for row in items if row.get("severity") == "danger"]), "datatype": "Int"},
		{"label": _("Needs Attention"), "value": len([row for row in items if row.get("severity") == "warning"]), "datatype": "Int"},
		{"label": _("Due Follow-ups"), "value": len([row for row in items if (row.get("follow_up") or {}).get("is_due")]), "datatype": "Int"},
		{"label": _("Open Actions"), "value": len(items), "datatype": "Int"},
	]


def _choice(value: Any, allowed: set[str], default: str) -> str:
	candidate = str(value or default).strip()
	return candidate if candidate in allowed else default


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
