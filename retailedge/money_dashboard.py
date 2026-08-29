from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.cash_movement import get_cash_movement, get_cash_movement_context
from retailedge.customer_receivables import get_customer_receivables
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.supplier_payables import get_supplier_payables

DASHBOARD_KEY = "money-overview"
PREVIEW_ROWS = 8


@frappe.whitelist()
def get_money_dashboard_context() -> dict[str, Any]:
	context = get_cash_movement_context()
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
def get_money_dashboard_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	require_dashboard_action(DASHBOARD_KEY, "view", company=company, branch=branch)

	period_filters = {
		"company": company,
		"branch": branch,
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}
	current_filters = {"company": company, "branch": branch}
	sections = {
		"cash": _safe_section(
			"Cash Movement",
			lambda: get_cash_movement(filters=period_filters, page=1, page_size=PREVIEW_ROWS),
			"/app/cash-movement",
			"selected_period",
		),
		"receivables": _safe_section(
			"Customer Receivables",
			lambda: get_customer_receivables(filters=current_filters, page=1, page_size=PREVIEW_ROWS),
			"/app/customer-receivables",
			"current_position",
		),
		"payables": _safe_section(
			"Supplier Payables",
			lambda: get_supplier_payables(filters=current_filters, page=1, page_size=PREVIEW_ROWS),
			"/app/supplier-payables",
			"current_position",
		),
	}
	return {
		"title": _("Money Overview"),
		"filters": period_filters,
		"headline_summary": _headline_summary(sections),
		"attention": _attention_items(sections),
		"sections": sections,
		"metadata": {
			"composition": "existing_money_reporting_engines",
			"cash_time_basis": "selected_period_flow",
			"receivables_time_basis": "current_outstanding",
			"payables_time_basis": "current_outstanding",
			"cash_balance_warning": "Period net change is a flow metric and is not presented as a closing cash or bank balance.",
		},
	}


def build_money_dashboard_export_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	result = get_money_dashboard_data(filters)
	rows: list[dict[str, Any]] = []
	for key, section in (result.get("sections") or {}).items():
		if not section.get("available"):
			continue
		for card in section.get("summary") or []:
			rows.append(
				{
					"section": section.get("label") or key,
					"time_basis": _time_basis_label(section.get("time_basis")),
					"metric": card.get("label") or "",
					"value": card.get("value"),
					"datatype": card.get("datatype") or card.get("type") or "Data",
				}
			)
	return {
		"title": _("Money Overview"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 180},
			{"fieldname": "time_basis", "label": _("Time Basis"), "fieldtype": "Data", "width": 160},
			{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 220},
			{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 160},
		],
		"rows": rows,
		"summary": result.get("headline_summary") or [],
		"filters": result.get("filters") or {},
	}


def _headline_summary(sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	preferred = (
		("cash", "Money In", "Money In"),
		("cash", "Money Out", "Money Out"),
		("cash", "Net Change", "Period Net Change"),
		("receivables", "Total Receivables", "Receivables"),
		("payables", "Total Payables", "Payables"),
	)
	cards: list[dict[str, Any]] = []
	for section_key, metric_label, display_label in preferred:
		card = _summary_card(sections.get(section_key), metric_label)
		if card:
			cards.append({**card, "label": _(display_label), "source_label": card.get("label")})
	return cards


def _attention_items(sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for section_key, metric, tone, message, route in (
		("receivables", "Over 90 Days", "danger", "Receivables are over 90 days overdue", "/app/customer-receivables"),
		("receivables", "Overdue", "warning", "Customer balances are overdue", "/app/customer-receivables"),
		("payables", "Over 90 Days", "danger", "Supplier balances are over 90 days overdue", "/app/supplier-payables"),
		("payables", "Overdue", "warning", "Supplier balances are overdue", "/app/supplier-payables"),
	):
		card = _summary_card(sections.get(section_key), metric)
		if not card or flt(card.get("value")) <= 0:
			continue
		items.append(
			{
				"section": section_key,
				"label": _(message),
				"metric": card.get("label") or metric,
				"value": card.get("value"),
				"datatype": card.get("datatype") or card.get("type") or "Data",
				"tone": tone,
				"route": route,
			}
		)
	return items


def _safe_section(
	label: str,
	loader: Callable[[], dict[str, Any]],
	route: str,
	time_basis: str,
) -> dict[str, Any]:
	try:
		payload = loader() or {}
		return {
			"available": True,
			"label": _(label),
			"route": route,
			"time_basis": time_basis,
			"summary": payload.get("summary") or [],
			"rows": payload.get("rows") or [],
			"scope": payload.get("scope") or {},
		}
	except frappe.PermissionError:
		return {
			"available": False,
			"label": _(label),
			"route": route,
			"time_basis": time_basis,
			"reason": _("Your current permissions do not allow this dashboard section."),
		}


def _summary_card(section: dict[str, Any] | None, label: str) -> dict[str, Any] | None:
	if not section or not section.get("available"):
		return None
	for card in section.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return dict(card)
	return None


def _time_basis_label(value: str | None) -> str:
	return _("Selected Period") if value == "selected_period" else _("Current Position")


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
