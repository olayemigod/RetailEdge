from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import get_first_day, today

from retailedge.branch_performance_dashboard import get_branch_performance_dashboard_data
from retailedge.cash_movement import get_cash_movement
from retailedge.customer_receivables import get_customer_receivables
from retailedge.expense_register import get_expense_register
from retailedge.sales_reporting import get_sales_invoice_register
from retailedge.stock_position import get_stock_position
from retailedge.supplier_payables import get_supplier_payables

DASHBOARD_KEY = "owner-dashboard"
DEFAULT_PAGE_SIZE = 1


@frappe.whitelist()
def get_owner_dashboard_context() -> dict[str, Any]:
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if company and not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	return {
		"dashboard_key": DASHBOARD_KEY,
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"sections": [
			"sales",
			"expenses",
			"cash",
			"receivables",
			"payables",
			"stock",
			"branches",
		],
	}


@frappe.whitelist()
def get_owner_dashboard_data(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)
	branch = str(filters.get("branch") or "").strip()
	from_date = str(filters.get("from_date") or get_first_day(today()))
	to_date = str(filters.get("to_date") or today())
	common = {
		"company": company,
		"branch": branch,
		"from_date": from_date,
		"to_date": to_date,
	}

	sections = {
		"sales": _safe_section(
			"Sales",
			lambda: get_sales_invoice_register(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/sales-invoice-register",
		),
		"expenses": _safe_section(
			"Expenses",
			lambda: get_expense_register(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/expense-register",
		),
		"cash": _safe_section(
			"Cash Movement",
			lambda: get_cash_movement(filters=common, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/cash-movement",
		),
		"receivables": _safe_section(
			"Receivables",
			lambda: get_customer_receivables(filters={"company": company, "branch": branch}, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/customer-receivables",
		),
		"payables": _safe_section(
			"Payables",
			lambda: get_supplier_payables(filters={"company": company, "branch": branch}, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/supplier-payables",
		),
		"stock": _safe_section(
			"Stock Position",
			lambda: get_stock_position(filters={"company": company, "branch": branch}, page=1, page_size=DEFAULT_PAGE_SIZE),
			"/app/stock-position",
		),
		"branches": _safe_section(
			"Branch Performance",
			lambda: get_branch_performance_dashboard_data(filters=common),
			"/app/branch-performance-dashboard",
		),
	}
	return {
		"title": _("Owner Dashboard"),
		"filters": common,
		"sections": sections,
		"metadata": {
			"composition": "existing_retailedge_reporting_engines",
			"accounting_truth": "ERPNext submitted/posted documents and existing RetailEdge control records",
			"generated_for": frappe.session.user,
		},
	}


def _safe_section(label: str, loader: Callable[[], dict[str, Any]], route: str) -> dict[str, Any]:
	try:
		payload = loader() or {}
		return {
			"available": True,
			"label": _(label),
			"route": route,
			"summary": payload.get("summary") or [],
			"scope": payload.get("scope") or {},
			"show_costs": payload.get("show_costs"),
			"messages": payload.get("messages") or [],
		}
	except frappe.PermissionError:
		return {
			"available": False,
			"label": _(label),
			"route": route,
			"reason": _("Your current permissions do not allow this dashboard section."),
		}


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
