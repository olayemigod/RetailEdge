from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cstr

from retailedge.branch_context import get_branch_query_filters
from retailedge.branch_performance import assert_can_access_branch_performance
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.reporting.date_ranges import get_preset_dates
from retailedge.salesperson_performance import (
	MAX_EXPORT_ROWS,
	MAX_LINK_RESULTS,
	get_salesperson_performance,
)

DASHBOARD_KEY = "salesperson-performance"

COLUMNS = [
	{"label": _("Salesperson"), "fieldname": "salesperson", "fieldtype": "Link", "options": "Sales Person", "width": 170},
	{"label": _("Allocation"), "fieldname": "allocation_percentage", "fieldtype": "Percent", "width": 105},
	{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
	{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
	{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
	{"label": _("Items Sold"), "fieldname": "items", "fieldtype": "Data", "width": 210},
	{"label": _("Qty"), "fieldname": "total_qty", "fieldtype": "Float", "width": 90},
	{"label": _("Gross"), "fieldname": "gross_amount", "fieldtype": "Currency", "width": 130},
	{"label": _("Discount"), "fieldname": "discount", "fieldtype": "Currency", "width": 120},
	{"label": _("Net"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 130},
	{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 135},
	{"label": _("Status"), "fieldname": "payment_status", "fieldtype": "Data", "width": 110},
]


def _default_company() -> str:
	return cstr(
		frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
		or ""
	)


def _summary_cards(summary: dict) -> list[dict]:
	return [
		{"label": _("Gross Sales"), "value": summary.get("gross_sales") or 0, "datatype": "Currency", "tone": "info"},
		{"label": _("Net Sales"), "value": summary.get("net_sales") or 0, "datatype": "Currency", "tone": "success"},
		{"label": _("Sales Invoices"), "value": summary.get("total_invoices") or 0, "datatype": "Int", "tone": "neutral"},
		{"label": _("Average Invoice"), "value": summary.get("avg_invoice_value") or 0, "datatype": "Currency", "tone": "neutral"},
		{"label": _("Discount"), "value": summary.get("total_discount") or 0, "datatype": "Currency", "tone": "warning"},
		{"label": _("Outstanding"), "value": summary.get("total_outstanding") or 0, "datatype": "Currency", "tone": "danger"},
	]


def _normalise_filters(filters=None, *, export_mode: bool = False) -> dict:
	value = frappe.parse_json(filters) if isinstance(filters, str) else dict(filters or {})
	if not value.get("company"):
		value["company"] = _default_company()
	value["offset"] = 0 if export_mode else max(0, int(value.get("offset") or 0))
	value["limit"] = MAX_EXPORT_ROWS if export_mode else min(max(1, int(value.get("limit") or 50)), 100)
	value["export_mode"] = 1 if export_mode else 0
	return value


def _build_salesperson_dashboard_dataset(filters=None, *, export_mode: bool = False) -> dict:
	value = _normalise_filters(filters, export_mode=export_mode)
	require_dashboard_action(
		DASHBOARD_KEY,
		"view",
		company=value.get("company"),
		branch=value.get("branch"),
	)
	result = get_salesperson_performance(value)
	rows = result.get("rows") or []
	offset = result.get("offset") or 0
	page_size = result.get("limit") or value["limit"]
	total_rows = result.get("total_rows") or 0
	return {
		"title": _("Salesperson Performance"),
		"columns": COLUMNS,
		"rows": rows,
		"summary": _summary_cards(result.get("summary") or {}),
		"pagination": {
			"offset": offset,
			"page_size": page_size,
			"total_rows": total_rows,
			"has_previous": offset > 0,
			"has_next": (not export_mode) and (offset + len(rows) < total_rows),
		},
		"filters": {key: val for key, val in value.items() if key != "export_mode"},
		"metadata": {
			"source": "Submitted ERPNext Sales Invoices with ERPNext Sales Team",
			"allocation": "Shared R8/R11 contract: positive percentages respected, residual explicitly unallocated, blank/zero teams split evenly, invoices without Sales Team explicitly unassigned",
			"export_row_cap": MAX_EXPORT_ROWS,
		},
	}


@frappe.whitelist()
def get_salesperson_dashboard_context() -> dict:
	assert_can_access_branch_performance(frappe.session.user)
	company = _default_company()
	from_date, to_date = get_preset_dates("This Month")
	capabilities = require_dashboard_action(DASHBOARD_KEY, "view", company=company)
	return {
		"dashboard_key": DASHBOARD_KEY,
		"default_filters": {
			"company": company,
			"date_range_preset": "This Month",
			"from_date": str(from_date or ""),
			"to_date": str(to_date or ""),
			"branch": "",
			"salesperson": "",
			"customer": "",
			"item": "",
			"item_group": "",
			"limit": 50,
			"offset": 0,
		},
		"capabilities": capabilities,
		"tenant_name": company,
		"user_name": frappe.get_cached_value("User", frappe.session.user, "full_name") or frappe.session.user,
	}


@frappe.whitelist()
def get_salesperson_dashboard_data(filters=None) -> dict:
	assert_can_access_branch_performance(frappe.session.user)
	return _build_salesperson_dashboard_dataset(filters, export_mode=False)


def _search_doctype(doctype: str, txt: str, *, fields: list[str] | None = None, filters=None, or_filters=None) -> list[dict]:
	rows = frappe.get_list(
		doctype,
		filters=filters or {},
		or_filters=or_filters or {},
		fields=fields or ["name"],
		order_by="modified desc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	result = []
	for row in rows:
		value = row.get("name")
		label = row.get("customer_name") or row.get("item_name") or value
		result.append({"value": value, "label": label, "description": value if label != value else ""})
	return result


@frappe.whitelist()
def search_salesperson_dashboard_options(kind: str, txt: str = "", company: str = "") -> list[dict]:
	assert_can_access_branch_performance(frappe.session.user)
	kind = cstr(kind).strip().lower()
	txt = cstr(txt).strip()
	company = cstr(company or _default_company()).strip()
	like = f"%{txt}%"
	if kind == "company":
		return _search_doctype("Company", txt, filters={"name": ["like", like]})
	if kind == "branch":
		scope = get_branch_query_filters("Sales Invoice", user=frappe.session.user, company=company)
		allowed = scope.get("allowed_branches") or []
		filters: list[list] = [["Branch", "name", "like", like]]
		if allowed:
			filters.append(["Branch", "name", "in", allowed])
		if company and frappe.get_meta("Branch").has_field("company"):
			filters.append(["Branch", "company", "=", company])
		return _search_doctype("Branch", txt, filters=filters)
	if kind == "salesperson":
		return _search_doctype("Sales Person", txt, filters={"enabled": 1, "name": ["like", like]})
	if kind == "customer":
		return _search_doctype(
			"Customer",
			txt,
			fields=["name", "customer_name"],
			or_filters={"name": ["like", like], "customer_name": ["like", like]},
		)
	if kind == "item":
		return _search_doctype(
			"Item",
			txt,
			fields=["name", "item_name"],
			filters={"disabled": 0},
			or_filters={"name": ["like", like], "item_name": ["like", like]},
		)
	if kind == "item_group":
		return _search_doctype("Item Group", txt, filters={"name": ["like", like]})
	frappe.throw(_("Unsupported Salesperson Performance search type."))