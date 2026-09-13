from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from retailedge.bank_exception_summary import get_bank_exception_summary
from retailedge.cash_shift_verification import get_cash_shift_verification
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.owner_dashboard import get_owner_dashboard_data


@frappe.whitelist()
def get_business_hub_home_snapshot(company: str = "", branch: str = "") -> dict[str, Any]:
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		branch
		or frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	if not company:
		frappe.throw(_("Company is required."))

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
			)
		else:
			return _unavailable_scope_snapshot(
				company=company,
				reason=_("Choose a Branch to load scoped business signals."),
				allowed_branches=allowed,
			)
	elif not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to view this Company."), frappe.PermissionError)

	today = nowdate()
	period_filters = {"company": company, "branch": branch, "from_date": today, "to_date": today}

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
	return {
		"as_of_date": today,
		"company": company,
		"branch": branch,
		"scope": {
			"restricted": bool(scope.get("restricted")),
			"allowed_branches": allowed if scope.get("restricted") else [],
		},
		"cards": _headline_cards(owner),
		"sections": sections,
		"attention": _attention(owner, banking, cash_shift),
	}


def _unavailable_scope_snapshot(
	*,
	company: str,
	reason: str,
	allowed_branches: list[str] | None = None,
) -> dict[str, Any]:
	"""Return a no-data Home state when restricted scope cannot be resolved safely."""
	today = nowdate()
	def unavailable(label: str, route: str = "") -> dict[str, Any]:
		return {
			"available": False,
			"label": label,
			"summary": [],
			"route": route,
			"reason": reason,
		}
	return {
		"as_of_date": today,
		"company": company,
		"branch": "",
		"scope": {
			"restricted": True,
			"allowed_branches": list(allowed_branches or []),
		},
		"cards": [],
		"sections": {
			"today": unavailable(_("Today")),
			"stock": unavailable(_("Stock")),
			"branch": unavailable(_("Branch")),
			"banking": unavailable(_("Banking"), "/app/bank-matching-reconciliation"),
			"cash_shift": unavailable(_("Cash Shift"), "/app/cash-shift-verification"),
		},
		"attention": [],
	}


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
