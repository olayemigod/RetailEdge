from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate, nowdate

from retailedge.bank_exception_summary import get_bank_exception_summary
from retailedge.branch_context import user_has_global_branch_access
from retailedge.cash_shift_verification import get_cash_shift_verification
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.owner_dashboard import get_owner_dashboard_data
from retailedge.utils.settings import get_retailedge_settings


MAX_HOME_ATTENTION_ITEMS = 12


@frappe.whitelist()
def get_business_hub_home_snapshot(
	company: str = "",
	branch: str = "",
	date_preset: str = "Today",
	from_date: str = "",
	to_date: str = "",
	date_label: str = "",
) -> dict[str, Any]:
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		branch
		or frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	if not company:
		frappe.throw(_("Company is required."))

	period = _resolve_period(date_preset, from_date=from_date, to_date=to_date, date_label=date_label)
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	allowed = [str(value or "").strip() for value in scope.get("allowed_branches") or [] if str(value or "").strip()]
	if branch:
		if scope.get("restricted") and branch not in allowed:
			frappe.throw(_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch), frappe.PermissionError)
		validate_operating_branch(company=company, branch=branch, user=frappe.session.user, throw=True)
	elif scope.get("restricted"):
		if len(allowed) == 1:
			branch = allowed[0]
			validate_operating_branch(company=company, branch=branch, user=frappe.session.user, throw=True)
		elif not allowed:
			return _unavailable_scope_snapshot(
				company=company,
				reason=_("Your RetailEdge Branch access is not active for this Company."),
				period=period,
			)
		else:
			return _unavailable_scope_snapshot(
				company=company,
				reason=_("Choose a Branch to load scoped business signals."),
				allowed_branches=allowed,
				period=period,
			)
	elif not (
		user_has_global_branch_access(user=frappe.session.user)
		or frappe.has_permission("Company", "read", doc=company)
	):
		frappe.throw(_("You do not have permission to view this Company."), frappe.PermissionError)

	period_filters = {
		"company": company,
		"branch": branch,
		"from_date": period["from_date"],
		"to_date": period["to_date"],
	}

	owner = _safe_payload(lambda: get_owner_dashboard_data(period_filters), _("Business summary"))
	banking = _safe_payload(lambda: get_bank_exception_summary(period_filters), _("Banking exceptions"))
	cash_shift = _safe_payload(
		lambda: get_cash_shift_verification(period_filters, page=1, page_size=25),
		_("Cash shift verification"),
	)

	sections = {
		"today": _today_section(owner),
		"stock": _owner_section(owner, "stock"),
		"branch": _owner_section(owner, "branches"),
		"banking": _banking_section(banking),
		"cash_shift": _cash_shift_section(cash_shift),
	}
	action_settings = _business_hub_action_settings()
	indices = _business_indices(
		owner,
		banking,
		cash_shift,
		company=company,
		branch=branch,
		period=period,
		action_settings=action_settings,
	)
	return {
		"as_of_date": period["to_date"],
		"period": period,
		"company": company,
		"branch": branch,
		"scope": {
			"restricted": bool(scope.get("restricted")),
			"allowed_branches": allowed if scope.get("restricted") else [],
		},
		"cards": _headline_cards(owner),
		"sections": sections,
		"indices": indices,
		"settings": action_settings,
		"attention": _prioritized_attention(
			owner,
			indices,
			company=company,
			branch=branch,
			period=period,
		),
	}



MAX_CUSTOM_PERIOD_DAYS = 366


def _parse_dmy_date(value: str):
	match = re.fullmatch(r"\s*(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})\s*", str(value or ""))
	if not match:
		return None
	day, month, year = (int(part) for part in match.groups())
	try:
		return getdate(f"{year:04d}-{month:02d}-{day:02d}")
	except Exception:
		return None


def _custom_range_from_text(value: str):
	text = str(value or "").strip()
	if not text:
		return None
	parts = re.split(r"\s+(?:to|–|—|-)\s+", text, maxsplit=1, flags=re.IGNORECASE)
	if len(parts) == 2:
		start = _parse_dmy_date(parts[0])
		end = _parse_dmy_date(parts[1])
		if start and end:
			return start, end
	single = _parse_dmy_date(text)
	return (single, single) if single else None


def _assert_bounded_period(resolved_from, resolved_to) -> None:
	if resolved_from > resolved_to:
		frappe.throw(_("From Date cannot be after To Date."))
	if (resolved_to - resolved_from).days + 1 > MAX_CUSTOM_PERIOD_DAYS:
		frappe.throw(_("Business Hub periods cannot exceed {0} days.").format(MAX_CUSTOM_PERIOD_DAYS))


def _resolve_period(
	date_preset: str,
	*,
	from_date: str = "",
	to_date: str = "",
	date_label: str = "",
) -> dict[str, str]:
	preset = str(date_preset or "Today").strip() or "Today"
	custom_from = str(from_date or "").strip()
	custom_to = str(to_date or "").strip()
	if custom_from or custom_to:
		if not custom_from or not custom_to:
			frappe.throw(_("Both From Date and To Date are required for a custom Business Hub period."))
		resolved_from = getdate(custom_from)
		resolved_to = getdate(custom_to)
		_assert_bounded_period(resolved_from, resolved_to)
		label = str(date_label or "").strip() or _("Custom Period")
		return {
			"preset": "Custom Period",
			"label": label,
			"from_date": str(resolved_from),
			"to_date": str(resolved_to),
		}

	normalized = re.sub(r"\s+", " ", preset.strip()).lower()
	aliases = {
		"today": "Today",
		"tdy": "Today",
		"yesterday": "Yesterday",
		"yday": "Yesterday",
		"this week": "This Week",
		"week to date": "This Week",
		"wtd": "This Week",
		"this month": "This Month",
		"month to date": "This Month",
		"mtd": "This Month",
		"last 7 days": "Last 7 Days",
		"last week": "Last 7 Days",
		"last 30 days": "Last 30 Days",
		"this year": "Year to Date",
		"year to date": "Year to Date",
		"ytd": "Year to Date",
		"last month": "Last Month",
	}
	canonical = aliases.get(normalized)

	custom_range = _custom_range_from_text(preset)
	if custom_range:
		resolved_from, resolved_to = custom_range
		_assert_bounded_period(resolved_from, resolved_to)
		return {
			"preset": "Custom Period",
			"label": preset,
			"from_date": str(resolved_from),
			"to_date": str(resolved_to),
		}

	last_days = re.fullmatch(r"(?:last|past)\s+(\d{1,3})\s+days?", normalized)
	if last_days:
		days = int(last_days.group(1))
		if days < 1 or days > MAX_CUSTOM_PERIOD_DAYS:
			frappe.throw(_("Business Hub periods cannot exceed {0} days.").format(MAX_CUSTOM_PERIOD_DAYS))
		resolved_to = getdate(nowdate())
		resolved_from = getdate(add_days(resolved_to, -(days - 1)))
		return {
			"preset": f"Last {days} Days",
			"label": f"Last {days} Days",
			"from_date": str(resolved_from),
			"to_date": str(resolved_to),
		}

	if not canonical:
		frappe.throw(_("Unsupported Business Hub period."))

	today = getdate(nowdate())
	resolved_to = today
	if canonical == "Today":
		resolved_from = today
	elif canonical == "Yesterday":
		resolved_from = getdate(add_days(today, -1))
		resolved_to = resolved_from
	elif canonical == "This Week":
		resolved_from = getdate(add_days(today, -today.weekday()))
	elif canonical == "This Month":
		resolved_from = getdate(get_first_day(today))
	elif canonical == "Last 7 Days":
		resolved_from = getdate(add_days(today, -6))
	elif canonical == "Last 30 Days":
		resolved_from = getdate(add_days(today, -29))
	elif canonical == "Year to Date":
		resolved_from = getdate(f"{today.year}-01-01")
	elif canonical == "Last Month":
		this_month = getdate(get_first_day(today))
		resolved_to = getdate(add_days(this_month, -1))
		resolved_from = getdate(get_first_day(resolved_to))
	else:
		frappe.throw(_("Unsupported Business Hub period."))

	_assert_bounded_period(resolved_from, resolved_to)
	return {
		"preset": canonical,
		"label": canonical,
		"from_date": str(resolved_from),
		"to_date": str(resolved_to),
	}

def _unavailable_scope_snapshot(
	*,
	company: str,
	reason: str,
	allowed_branches: list[str] | None = None,
	period: dict[str, str] | None = None,
) -> dict[str, Any]:
	"""Return a no-data Home state when restricted scope cannot be resolved safely."""
	period = period or _resolve_period("Today")
	def unavailable(label: str, route: str = "") -> dict[str, Any]:
		return {
			"available": False,
			"label": label,
			"summary": [],
			"route": route,
			"reason": reason,
		}
	return {
		"as_of_date": period["to_date"],
		"period": period,
		"company": company,
		"branch": "",
		"scope": {
			"restricted": True,
			"allowed_branches": list(allowed_branches or []),
		},
		"cards": [],
		"indices": [],
		"settings": {"variance_tolerance": 0.0},
		"sections": {
			"today": unavailable(_("Today")),
			"stock": unavailable(_("Stock")),
			"branch": unavailable(_("Branch")),
			"banking": unavailable(_("Banking"), "/app/bank-matching-reconciliation"),
			"cash_shift": unavailable(_("Cash Shift"), "/app/cash-shift-verification"),
		},
		"attention": [],
	}



def _business_hub_action_settings() -> dict[str, Any]:
	try:
		settings = get_retailedge_settings()
		variance_tolerance = max(flt(getattr(settings, "business_hub_variance_tolerance", 0)), 0.0)
	except Exception:
		variance_tolerance = 0.0
	return {"variance_tolerance": variance_tolerance}


def _route_filters(
	*,
	company: str,
	branch: str,
	period: dict[str, str],
	current: bool = False,
) -> dict[str, Any]:
	filters: dict[str, Any] = {"company": company}
	if branch:
		filters["branch"] = branch
	if not current:
		filters.update(
			{
				"from_date": period.get("from_date") or "",
				"to_date": period.get("to_date") or "",
			}
		)
	return filters


def _owner_payload_section(owner: dict[str, Any], key: str) -> dict[str, Any]:
	if not owner.get("available"):
		return {"available": False, "summary": [], "reason": owner.get("reason") or ""}
	return dict((owner.get("payload") or {}).get("sections", {}).get(key) or {})


def _first_summary_card(section: dict[str, Any], labels: tuple[str, ...]) -> dict[str, Any] | None:
	for label in labels:
		card = _summary_card(section, label)
		if card:
			return card
	return None


def _signal(
	card: dict[str, Any] | None,
	*,
	tone: str = "neutral",
	requires_action: bool = False,
	message: str = "",
) -> dict[str, Any]:
	card = dict(card or {})
	return {
		"label": card.get("label") or "",
		"value": card.get("value") if card else 0,
		"datatype": card.get("datatype") or card.get("type") or "Data",
		"tone": tone,
		"requires_action": bool(requires_action),
		"message": message,
	}


def _index_card(
	*,
	key: str,
	label: str,
	route: str,
	route_filters: dict[str, Any],
	headline: dict[str, Any] | None,
	signal: dict[str, Any],
	recommendation: str,
	action_label: str,
	available: bool = True,
	reason: str = "",
) -> dict[str, Any]:
	if not available:
		return {
			"key": key,
			"label": label,
			"available": False,
			"reason": reason,
			"route": route,
			"route_filters": route_filters,
			"headline": {},
			"signal": {},
			"recommendation": "",
			"action_label": action_label,
			"tone": "neutral",
			"requires_action": False,
			"priority": 99,
		}
	headline = dict(headline or {})
	requires_action = bool(signal.get("requires_action"))
	tone = str(signal.get("tone") or "neutral")
	priority = 1 if tone == "danger" and requires_action else 2 if tone == "warning" and requires_action else 3
	return {
		"key": key,
		"label": label,
		"available": True,
		"reason": "",
		"route": route,
		"route_filters": route_filters,
		"headline": {
			"label": headline.get("label") or "",
			"value": headline.get("value") if headline else 0,
			"datatype": headline.get("datatype") or headline.get("type") or "Data",
		},
		"signal": signal,
		"recommendation": recommendation,
		"action_label": action_label,
		"tone": tone,
		"requires_action": requires_action,
		"priority": priority,
	}


def _business_indices(
	owner: dict[str, Any],
	banking: dict[str, Any],
	cash_shift: dict[str, Any],
	*,
	company: str,
	branch: str,
	period: dict[str, str],
	action_settings: dict[str, Any],
) -> list[dict[str, Any]]:
	period_filters = _route_filters(company=company, branch=branch, period=period)
	current_filters = _route_filters(company=company, branch=branch, period=period, current=True)
	variance_tolerance = max(flt(action_settings.get("variance_tolerance")), 0.0)

	sales = _owner_payload_section(owner, "sales")
	cash = _owner_payload_section(owner, "cash")
	stock = _owner_payload_section(owner, "stock")
	expenses = _owner_payload_section(owner, "expenses")
	receivables = _owner_payload_section(owner, "receivables")
	payables = _owner_payload_section(owner, "payables")
	branches = _owner_payload_section(owner, "branches")
	banking_section = _banking_section(banking)
	cash_shift_section = _cash_shift_section(cash_shift)

	returns = _summary_card(sales, "Returns")
	sales_signal = _signal(
		returns or _summary_card(sales, "Invoices"),
		tone="warning" if returns and flt(returns.get("value")) > 0 else "neutral",
		requires_action=bool(returns and flt(returns.get("value")) > 0),
		message=_("Review sales returns and unusual reversals.") if returns and flt(returns.get("value")) > 0 else _("Sales activity is available for review."),
	)

	cash_variance = _summary_card(cash_shift_section, "Cash Variance")
	cash_exceptions = _summary_card(cash_shift_section, "Exceptions")
	cash_variance_value = abs(flt((cash_variance or {}).get("value")))
	if cash_variance and cash_variance_value > variance_tolerance:
		cash_signal = _signal(
			cash_variance,
			tone="danger",
			requires_action=True,
			message=_("Cash variance exceeds the Business Hub tolerance."),
		)
	elif cash_exceptions and flt(cash_exceptions.get("value")) > 0:
		cash_signal = _signal(
			cash_exceptions,
			tone="warning",
			requires_action=True,
			message=_("Cash-shift exceptions require review."),
		)
	else:
		cash_signal = _signal(_summary_card(cash, "Movements"), message=_("Cash movement is within the configured exception threshold."))

	negative_stock = _summary_card(stock, "Negative Stock")
	out_of_stock = _summary_card(stock, "Out of Stock")
	reorder_due = _summary_card(stock, "Reorder Due")
	fully_reserved = _summary_card(stock, "Fully Reserved")
	if negative_stock and flt(negative_stock.get("value")) > 0:
		stock_signal = _signal(negative_stock, tone="danger", requires_action=True, message=_("Negative stock requires immediate review."))
	elif reorder_due and flt(reorder_due.get("value")) > 0:
		stock_signal = _signal(reorder_due, tone="warning", requires_action=True, message=_("Replenishment is due for one or more stock items."))
	elif out_of_stock and flt(out_of_stock.get("value")) > 0:
		stock_signal = _signal(out_of_stock, tone="warning", requires_action=True, message=_("Items are currently out of stock."))
	elif fully_reserved and flt(fully_reserved.get("value")) > 0:
		stock_signal = _signal(fully_reserved, tone="warning", requires_action=True, message=_("Available stock is fully reserved for one or more items."))
	else:
		stock_signal = _signal(_summary_card(stock, "Available Items"), message=_("No critical stock exception is currently visible."))

	posting_blocked = _summary_card(expenses, "Posting Blocked")
	expense_review = _summary_card(expenses, "Submitted for Review")
	if posting_blocked and flt(posting_blocked.get("value")) > 0:
		expense_signal = _signal(posting_blocked, tone="danger", requires_action=True, message=_("Expense posting is blocked."))
	elif expense_review and flt(expense_review.get("value")) > 0:
		expense_signal = _signal(expense_review, tone="warning", requires_action=True, message=_("Expenses are awaiting review."))
	else:
		expense_signal = _signal(_summary_card(expenses, "Expense Count"), message=_("Expense activity is available for review."))

	receivable_90 = _summary_card(receivables, "Over 90 Days")
	receivable_overdue = _summary_card(receivables, "Overdue")
	if receivable_90 and flt(receivable_90.get("value")) > 0:
		receivable_signal = _signal(receivable_90, tone="danger", requires_action=True, message=_("Long-overdue customer balances need collection action."))
	elif receivable_overdue and flt(receivable_overdue.get("value")) > 0:
		receivable_signal = _signal(receivable_overdue, tone="warning", requires_action=True, message=_("Customer balances are overdue."))
	else:
		receivable_signal = _signal(_summary_card(receivables, "Open Invoices"), message=_("No overdue balance is currently flagged."))

	payable_90 = _summary_card(payables, "Over 90 Days")
	payable_overdue = _summary_card(payables, "Overdue")
	if payable_90 and flt(payable_90.get("value")) > 0:
		payable_signal = _signal(payable_90, tone="danger", requires_action=True, message=_("Long-overdue supplier balances need payment planning."))
	elif payable_overdue and flt(payable_overdue.get("value")) > 0:
		payable_signal = _signal(payable_overdue, tone="warning", requires_action=True, message=_("Supplier balances are overdue."))
	else:
		payable_signal = _signal(_summary_card(payables, "Open Bills"), message=_("No overdue supplier balance is currently flagged."))

	branch_variance = _summary_card(branches, "Audit Variance")
	branch_issues = _summary_card(branches, "Payment Issues")
	if branch_variance and abs(flt(branch_variance.get("value"))) > variance_tolerance:
		branch_signal = _signal(branch_variance, tone="danger", requires_action=True, message=_("Branch audit variance exceeds the Business Hub tolerance."))
	elif branch_issues and flt(branch_issues.get("value")) > 0:
		branch_signal = _signal(branch_issues, tone="warning", requires_action=True, message=_("Branch payment issues require review."))
	else:
		branch_signal = _signal(_summary_card(branches, "Cash Sales"), message=_("Branch performance has no configured exception signal."))

	bank_exceptions = _summary_card(banking_section, "Reconciliation Exceptions")
	bank_review = _summary_card(banking_section, "Bank Matches Need Review")
	if bank_exceptions and flt(bank_exceptions.get("value")) > 0:
		bank_signal = _signal(bank_exceptions, tone="danger", requires_action=True, message=_("Bank reconciliation exceptions require correction."))
	elif bank_review and flt(bank_review.get("value")) > 0:
		bank_signal = _signal(bank_review, tone="warning", requires_action=True, message=_("Bank matches are waiting for review."))
	else:
		bank_signal = _signal(_summary_card(banking_section, "Ready for Reconciliation"), message=_("Banking work is ready for normal review and reconciliation."))

	return [
		_index_card(
			key="sales",
			label=_("Sales"),
			route="/app/sales-invoice-register",
			route_filters=period_filters,
			headline=_summary_card(sales, "Net Invoiced"),
			signal=sales_signal,
			recommendation=_("Review sales invoices and returns for the selected period."),
			action_label=_("Review Sales"),
			available=bool(sales.get("available")),
			reason=sales.get("reason") or "",
		),
		_index_card(
			key="cash",
			label=_("Cash"),
			route="/app/cash-movement",
			route_filters=period_filters,
			headline=_summary_card(cash, "Net Change"),
			signal=cash_signal,
			recommendation=_("Review cash movement and investigate cash-shift exceptions where present."),
			action_label=_("Review Cash"),
			available=bool(cash.get("available")),
			reason=cash.get("reason") or "",
		),
		_index_card(
			key="stock",
			label=_("Stock"),
			route="/app/stock-position",
			route_filters=current_filters,
			headline=_first_summary_card(stock, ("Stock Value", "Items in Scope")),
			signal=stock_signal,
			recommendation=_("Review stock availability and replenish or correct exceptions."),
			action_label=_("Review Stock"),
			available=bool(stock.get("available")),
			reason=stock.get("reason") or "",
		),
		_index_card(
			key="expenses",
			label=_("Expenses"),
			route="/app/expense-register",
			route_filters=period_filters,
			headline=_summary_card(expenses, "Total Expenses"),
			signal=expense_signal,
			recommendation=_("Review expense approvals, posting readiness and period spend."),
			action_label=_("Review Expenses"),
			available=bool(expenses.get("available")),
			reason=expenses.get("reason") or "",
		),
		_index_card(
			key="receivables",
			label=_("Receivables"),
			route="/app/customer-receivables",
			route_filters=current_filters,
			headline=_summary_card(receivables, "Total Receivables"),
			signal=receivable_signal,
			recommendation=_("Prioritise overdue customer balances and collection follow-up."),
			action_label=_("Collect Receivables"),
			available=bool(receivables.get("available")),
			reason=receivables.get("reason") or "",
		),
		_index_card(
			key="payables",
			label=_("Payables"),
			route="/app/supplier-payables",
			route_filters=current_filters,
			headline=_summary_card(payables, "Total Payables"),
			signal=payable_signal,
			recommendation=_("Review supplier balances and schedule overdue payments."),
			action_label=_("Review Payables"),
			available=bool(payables.get("available")),
			reason=payables.get("reason") or "",
		),
		_index_card(
			key="branch",
			label=_("Branch Performance"),
			route="/app/branch-performance-dashboard",
			route_filters=period_filters,
			headline=_summary_card(branches, "Gross Sales"),
			signal=branch_signal,
			recommendation=_("Compare branch sales, cash expectations, variances and payment issues."),
			action_label=_("Review Branches"),
			available=bool(branches.get("available")),
			reason=branches.get("reason") or "",
		),
		_index_card(
			key="banking",
			label=_("Banking"),
			route="/app/bank-matching-reconciliation",
			route_filters=period_filters,
			headline=_summary_card(banking_section, "Ready for Reconciliation"),
			signal=bank_signal,
			recommendation=_("Review bank matches and clear reconciliation exceptions."),
			action_label=_("Open Banking"),
			available=bool(banking_section.get("available")),
			reason=banking_section.get("reason") or "",
		),
	]


def _prioritized_attention(
	owner: dict[str, Any],
	indices: list[dict[str, Any]],
	*,
	company: str,
	branch: str,
	period: dict[str, str],
) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	period_filters = _route_filters(company=company, branch=branch, period=period)
	if owner.get("available"):
		for item in (owner.get("payload") or {}).get("attention") or []:
			if str(item.get("section") or "") != "profitability":
				continue
			items.append(
				{
					**item,
					"priority": 1 if item.get("tone") == "danger" else 2,
					"recommendation": item.get("label") or _("Review profitability exceptions."),
					"action_label": _("Review Profitability"),
					"route_filters": period_filters,
				}
			)

	for index in indices:
		if not index.get("available") or not index.get("requires_action"):
			continue
		signal = index.get("signal") or {}
		items.append(
			{
				"section": index.get("key"),
				"label": signal.get("message") or index.get("recommendation") or index.get("label"),
				"metric": signal.get("label") or index.get("label"),
				"value": signal.get("value"),
				"datatype": signal.get("datatype") or "Data",
				"tone": index.get("tone") or "warning",
				"priority": index.get("priority") or 3,
				"recommendation": index.get("recommendation") or "",
				"action_label": index.get("action_label") or _("Open"),
				"route": index.get("route") or "",
				"route_filters": index.get("route_filters") or {},
			}
		)

	items.sort(key=lambda item: (int(item.get("priority") or 99), str(item.get("section") or ""), str(item.get("metric") or "")))
	return items[:MAX_HOME_ATTENTION_ITEMS]


def _safe_payload(loader: Callable[[], dict[str, Any]], label: str) -> dict[str, Any]:
	previous_messages = list(getattr(frappe.local, "message_log", []) or [])
	try:
		return {"available": True, "payload": loader() or {}, "reason": ""}
	except (frappe.PermissionError, frappe.ValidationError) as exc:
		return {"available": False, "payload": {}, "reason": str(exc)}
	except Exception:
		frappe.log_error(title=f"RetailEdge Business Hub: {label}")
		return {
			"available": False,
			"payload": {},
			"reason": _("This section is temporarily unavailable."),
		}
	finally:
		frappe.local.message_log = previous_messages


def _owner_section(owner: dict[str, Any], key: str) -> dict[str, Any]:
	if not owner.get("available"):
		return {"available": False, "label": key.replace("_", " ").title(), "summary": [], "route": "", "reason": owner.get("reason") or ""}
	section = dict((owner.get("payload") or {}).get("sections", {}).get(key) or {})
	return {
		"available": bool(section.get("available")),
		"label": section.get("label") or key.replace("_", " ").title(),
		"summary": list(section.get("summary") or []),
		"route": section.get("route") or "",
		"reason": section.get("reason") or "",
	}


def _today_section(owner: dict[str, Any]) -> dict[str, Any]:
	if not owner.get("available"):
		return {"available": False, "label": _("Today"), "summary": [], "route": "", "reason": owner.get("reason") or ""}
	sections = (owner.get("payload") or {}).get("sections") or {}
	summary: list[dict[str, Any]] = []
	for section_key, metric, label in (
		("sales", "Net Invoiced", _("Sales")),
		("cash", "Money In", _("Money In")),
		("cash", "Money Out", _("Money Out")),
		("expenses", "Total Expenses", _("Expenses")),
	):
		card = _summary_card(sections.get(section_key), metric)
		if card:
			summary.append({**card, "label": label})
	return {"available": bool(summary), "label": _("Today"), "summary": summary, "route": "/app/owner-dashboard", "reason": ""}


def _headline_cards(owner: dict[str, Any]) -> list[dict[str, Any]]:
	if not owner.get("available"):
		return []
	payload = owner.get("payload") or {}
	route_by_label = {
		"Sales": "/app/sales-invoice-register",
		"Expenses": "/app/expense-register",
		"Receivables": "/app/customer-receivables",
		"Payables": "/app/supplier-payables",
		"Stock Value": "/app/stock-position",
	}
	cards = []
	for card in payload.get("headline_summary") or []:
		label = str(card.get("label") or "").strip()
		if label not in route_by_label:
			continue
		cards.append({**card, "route": route_by_label[label]})
	return cards[:6]


def _banking_section(banking: dict[str, Any]) -> dict[str, Any]:
	if not banking.get("available"):
		return {"available": False, "label": _("Banking"), "summary": [], "route": "/app/bank-matching-reconciliation", "reason": banking.get("reason") or ""}
	payload = banking.get("payload") or {}
	return {
		"available": True,
		"label": _("Banking"),
		"summary": list(payload.get("summary") or []),
		"route": "/app/bank-matching-reconciliation",
		"reason": "",
	}


def _cash_shift_section(cash_shift: dict[str, Any]) -> dict[str, Any]:
	if not cash_shift.get("available"):
		return {"available": False, "label": _("Cash Shift"), "summary": [], "route": "/app/cash-shift-verification", "reason": cash_shift.get("reason") or ""}
	payload = cash_shift.get("payload") or {}
	return {
		"available": True,
		"label": _("Cash Shift"),
		"summary": list(payload.get("summary") or []),
		"route": "/app/cash-shift-verification",
		"reason": "",
	}


def _attention(owner: dict[str, Any], banking: dict[str, Any], cash_shift: dict[str, Any]) -> list[dict[str, Any]]:
	items = []
	if owner.get("available"):
		items.extend(list((owner.get("payload") or {}).get("attention") or []))

	if banking.get("available"):
		for card in (banking.get("payload") or {}).get("summary") or []:
			value = flt(card.get("value"))
			if value <= 0:
				continue
			label = str(card.get("label") or "")
			tone = "danger" if "Exception" in label else "warning"
			items.append({
				"section": "banking",
				"label": label,
				"value": value,
				"datatype": card.get("datatype") or "Int",
				"tone": tone,
				"route": "/app/bank-matching-reconciliation",
			})

	if cash_shift.get("available"):
		for card in (cash_shift.get("payload") or {}).get("summary") or []:
			label = str(card.get("label") or "")
			value = flt(card.get("value"))
			if label not in {"Cash Variance", "Exceptions"} or value == 0:
				continue
			items.append({
				"section": "cash_shift",
				"label": label,
				"value": value,
				"datatype": card.get("datatype") or ("Currency" if label == "Cash Variance" else "Int"),
				"tone": "danger" if label == "Cash Variance" else "warning",
				"route": "/app/cash-shift-verification",
			})
	return items[:10]


def _summary_card(section: dict[str, Any] | None, label: str) -> dict[str, Any] | None:
	if not section or not section.get("available"):
		return None
	for card in section.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return dict(card)
	return None
