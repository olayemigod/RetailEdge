from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, nowdate, today

from retailedge.branch_context import user_has_global_branch_access
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.owner_dashboard import get_owner_dashboard_data

DASHBOARD_KEY = "owner-dashboard"
MAX_LIQUID_ACCOUNT_SCAN = 250


@frappe.whitelist()
def get_financial_position_context() -> dict[str, Any]:
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	capabilities = require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	return {
		"title": _("Financial Position Snapshot"),
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
		},
		"capabilities": capabilities,
		"as_of_date": nowdate(),
		"limits": {"liquid_account_scan": MAX_LIQUID_ACCOUNT_SCAN},
	}


@frappe.whitelist()
def get_financial_position(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)
	resolved = {
		"company": company,
		"branch": branch,
		"from_date": str(filters.get("from_date") or get_first_day(today())),
		"to_date": str(filters.get("to_date") or today()),
	}
	owner = get_owner_dashboard_data(resolved)
	global_branch_scope = user_has_global_branch_access(user=frappe.session.user)
	liquid = _get_liquid_position(company=company, branch=branch, global_branch_scope=global_branch_scope)
	return _build_snapshot(
		owner=owner,
		liquid=liquid,
		allow_company_accounting=bool(not branch and global_branch_scope),
	)


def _build_snapshot(
	*,
	owner: dict[str, Any],
	liquid: dict[str, Any],
	allow_company_accounting: bool = True,
) -> dict[str, Any]:
	sections = owner.get("sections") or {}
	filters = owner.get("filters") or {}
	receivables = _metric(sections, "receivables", "Total Receivables")
	payables = _metric(sections, "payables", "Total Payables")
	stock_value = _stock_value(sections)
	accounting_net_profit = (
		_metric_or_none(sections, "profitability", "Accounting Net Profit") if allow_company_accounting else None
	)
	accounting_gross_profit = (
		_metric_or_none(sections, "profitability", "Accounting Gross Profit") if allow_company_accounting else None
	)
	transactional_gross_profit = _metric_or_none(sections, "profitability", "Transactional Gross Profit")
	money_in = _metric_or_none(sections, "cash", "Money In")
	money_out = _metric_or_none(sections, "cash", "Money Out")
	net_cash_movement = _metric_or_none(sections, "cash", "Net Change")

	current_cards = [
		_card("Receivables", receivables, "current", available=_section_available(sections, "receivables")),
		_card("Payables", payables, "current", available=_section_available(sections, "payables")),
		_card(
			"Net Trade Position",
			receivables - payables,
			"current",
			available=_section_available(sections, "receivables") and _section_available(sections, "payables"),
		),
	]
	if stock_value is not None:
		current_cards.append(_card("Stock Value", stock_value, "current", available=True))

	liquid_card = _card(
		"Cash & Bank Balance",
		liquid.get("balance"),
		"current",
		available=bool(liquid.get("available")),
		reason=liquid.get("reason"),
	)
	current_cards.insert(0, liquid_card)

	accounting_reason = ""
	if not allow_company_accounting:
		accounting_reason = _(
			"Company-level accounting profit is hidden because your Branch scope is restricted or a Branch filter is active."
		)
	period_cards = [
		_card(
			"Accounting Gross Profit",
			accounting_gross_profit,
			"period",
			available=accounting_gross_profit is not None,
			reason=accounting_reason,
		),
		_card(
			"Accounting Net Profit",
			accounting_net_profit,
			"period",
			available=accounting_net_profit is not None,
			reason=accounting_reason,
		),
		_card(
			"Sales Margin Contribution",
			transactional_gross_profit,
			"period",
			available=transactional_gross_profit is not None,
		),
		_card("Money In", money_in, "period", available=money_in is not None),
		_card("Money Out", money_out, "period", available=money_out is not None),
		_card("Net Cash Movement", net_cash_movement, "period", available=net_cash_movement is not None),
	]

	return {
		"title": _("Financial Position Snapshot"),
		"filters": filters,
		"as_of_date": nowdate(),
		"current_position": current_cards,
		"selected_period": period_cards,
		"liquid_accounts": liquid.get("accounts") or [],
		"metadata": {
			"accounting_truth": "ERPNext General Ledger and ERPNext accounting reports remain authoritative.",
			"cash_balance_definition": "closing balance of permitted non-group Cash/Bank accounts as of the current date",
			"cash_movement_definition": "posted Cash/Bank General Ledger movement for the selected period; not a closing balance",
			"trade_position_definition": "current receivables minus current payables; not accounting net assets or complete working capital",
			"stock_value_definition": "ERPNext stock valuation exposed only when RetailEdge cost visibility permits it",
			"branch_limit": "company accounting balances and company P&L are withheld unless the user has global Branch scope; Branch-filtered accounting remains unavailable until safe ERPNext accounting attribution exists",
		},
	}


def _get_liquid_position(*, company: str, branch: str, global_branch_scope: bool = True) -> dict[str, Any]:
	if branch:
		return {
			"available": False,
			"reason": _(
				"Cash & Bank closing balance is company-level in this snapshot. Branch balance is hidden until Branch is represented by a safe ERPNext accounting dimension or Cost Center mapping."
			),
			"accounts": [],
		}
	if not global_branch_scope:
		return {
			"available": False,
			"reason": _(
				"Company-wide Cash & Bank balance is hidden because your Branch access is restricted. Select a permitted Branch for operational views; a safe Branch accounting balance is not inferred."
			),
			"accounts": [],
		}
	if not frappe.has_permission("Account", "read"):
		return {"available": False, "reason": _("You do not have permission to view accounting balances."), "accounts": []}

	accounts = frappe.get_list(
		"Account",
		filters={
			"company": company,
			"is_group": 0,
			"disabled": 0,
			"account_type": ["in", ["Cash", "Bank"]],
		},
		fields=["name", "account_name", "account_type"],
		order_by="account_type asc, name asc",
		limit=MAX_LIQUID_ACCOUNT_SCAN + 1,
	)
	if len(accounts) > MAX_LIQUID_ACCOUNT_SCAN:
		frappe.throw(
			_("More than {0} Cash/Bank accounts are in scope. Narrow the Company configuration before loading this snapshot.").format(
				MAX_LIQUID_ACCOUNT_SCAN
			)
		)

	from erpnext.accounts.utils import get_balance_on

	rows: list[dict[str, Any]] = []
	balance = 0.0
	for account in accounts:
		value = flt(get_balance_on(account=account.name, date=nowdate(), in_account_currency=False))
		balance += value
		rows.append(
			{
				"account": account.name,
				"account_name": account.account_name or account.name,
				"account_type": account.account_type,
				"balance": value,
			}
		)
	return {"available": True, "balance": balance, "accounts": rows, "as_of_date": nowdate()}


def _stock_value(sections: dict[str, dict[str, Any]]) -> float | None:
	section = sections.get("stock") or {}
	if not section.get("available") or not section.get("show_costs"):
		return None
	return _metric_or_none(sections, "stock", "Stock Value")


def _section_available(sections: dict[str, dict[str, Any]], section_key: str) -> bool:
	return bool((sections.get(section_key) or {}).get("available"))


def _metric(sections: dict[str, dict[str, Any]], section_key: str, label: str) -> float:
	value = _metric_or_none(sections, section_key, label)
	return flt(value) if value is not None else 0.0


def _metric_or_none(sections: dict[str, dict[str, Any]], section_key: str, label: str) -> float | None:
	section = sections.get(section_key) or {}
	if not section.get("available"):
		return None
	for card in section.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return flt(card.get("value"))
	return None


def _card(
	label: str,
	value: float | None,
	time_basis: str,
	*,
	available: bool,
	reason: str | None = None,
) -> dict[str, Any]:
	return {
		"label": _(label),
		"value": value if available else None,
		"datatype": "Currency",
		"time_basis": time_basis,
		"available": available,
		"reason": reason or "",
	}


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
