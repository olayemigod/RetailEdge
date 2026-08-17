from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cstr

from retailedge.branch_context import get_branch_query_filters
from retailedge.branch_performance import _coerce_filters, assert_can_access_branch_performance, get_branch_performance_rows
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.reporting.date_ranges import get_preset_dates
from retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary import get_columns, get_report_summary

DASHBOARD_KEY = "branch-performance"
MAX_LINK_RESULTS = 20


def _default_company() -> str:
	return cstr(frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company") or "")


def _filters(value=None) -> frappe._dict:
	filters = _coerce_filters(value or {})
	if not filters.get("company"):
		filters.company = _default_company()
	return filters


def _assert_company(company: str) -> None:
	if company and not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)


def _format_summary(rows: list[dict]) -> list[dict]:
	tones = {"Red": "danger", "Orange": "warning", "Green": "success", "Blue": "info"}
	return [{**card, "tone": tones.get(card.get("indicator"), "neutral")} for card in get_report_summary(rows)]


@frappe.whitelist()
def get_branch_performance_dashboard_context() -> dict:
	assert_can_access_branch_performance()
	company = _default_company()
	from_date, to_date = get_preset_dates("This Month")
	capabilities = require_dashboard_action(DASHBOARD_KEY, "view", company=company)
	return {
		"dashboard_key": DASHBOARD_KEY,
		"default_filters": {
			"company": company,
			"branch": "",
			"pos_profile": "",
			"cashier": "",
			"date_range_preset": "This Month",
			"from_date": str(from_date or ""),
			"to_date": str(to_date or ""),
			"payment_method": "",
			"only_pos_invoices": 0,
			"include_unattributed": 1,
			"include_fallback_branch_resolution": 0,
		},
		"payment_methods": ["Cash", "Bank Transfer", "Card / POS", "Mobile Money", "Other"],
		"capabilities": capabilities,
		"user_name": frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"tenant_name": company,
	}


@frappe.whitelist()
def get_branch_performance_dashboard_data(filters=None) -> dict:
	assert_can_access_branch_performance()
	filters = _filters(filters)
	_assert_company(filters.get("company"))
	require_dashboard_action(DASHBOARD_KEY, "view", company=filters.get("company"), branch=filters.get("branch"))
	rows = get_branch_performance_rows(filters)
	messages = []
	for row in rows:
		for message in row.get("messages") or []:
			if message and message not in messages:
				messages.append(message)
	return {
		"title": _("Branch Performance"),
		"columns": get_columns(),
		"rows": rows,
		"summary": _format_summary(rows),
		"messages": messages,
		"filters": dict(filters),
		"metadata": {
			"source": "RetailEdge Branch Performance engine",
			"detail_report": "RetailEdge Branch Performance Summary",
			"accounting_truth": "Submitted ERPNext sales and posted RetailEdge control records",
		},
	}


@frappe.whitelist()
def search_branch_performance_options(kind: str, txt: str = "", company: str = "") -> list[dict]:
	assert_can_access_branch_performance()
	kind = cstr(kind).strip().lower()
	txt = cstr(txt).strip()
	company = cstr(company or _default_company()).strip()
	like = f"%{txt}%"
	if kind == "company":
		rows = frappe.get_list("Company", filters={"name": ["like", like]}, fields=["name"], order_by="name asc", limit_page_length=MAX_LINK_RESULTS)
		return [{"value": row.name, "label": row.name} for row in rows]
	if kind == "branch":
		scope = get_branch_query_filters("RetailEdge Daily Sales Audit", company=company)
		allowed = scope.get("allowed_branches") or []
		filters = {"name": ["like", like]}
		if allowed:
			filters["name"] = ["in", allowed]
		rows = frappe.get_list("Branch", filters=filters, fields=["name"], order_by="name asc", limit_page_length=MAX_LINK_RESULTS)
		return [{"value": row.name, "label": row.name} for row in rows if not txt or txt.lower() in row.name.lower()]
	if kind == "pos_profile" and frappe.db.exists("DocType", "POS Profile"):
		filters = {"name": ["like", like]}
		if company and frappe.get_meta("POS Profile").has_field("company"):
			filters["company"] = company
		rows = frappe.get_list("POS Profile", filters=filters, fields=["name"], order_by="name asc", limit_page_length=MAX_LINK_RESULTS)
		return [{"value": row.name, "label": row.name} for row in rows]
	if kind == "cashier":
		rows = frappe.get_list("User", filters={"enabled": 1, "name": ["like", like]}, fields=["name", "full_name"], order_by="full_name asc", limit_page_length=MAX_LINK_RESULTS)
		return [{"value": row.name, "label": row.full_name or row.name} for row in rows]
	frappe.throw(_("Unsupported Branch Performance search type."))
