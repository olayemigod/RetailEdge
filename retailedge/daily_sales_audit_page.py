from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from retailedge.retailedge.report.retailedge_daily_sales_audit_register.retailedge_daily_sales_audit_register import (
	get_columns,
	get_data,
	validate_filters,
)
from retailedge.stock_movement_filters import branch_query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_AUDIT_ROWS = 1000
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_daily_sales_audit_page_context() -> dict[str, Any]:
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
			"pos_profile": "",
			"cashier": "",
			"audit_status": "",
			"audit_result": "",
			"from_date": f"{nowdate()[:7]}-01",
			"to_date": nowdate(),
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"limits": {"rows": MAX_AUDIT_ROWS, "page_size": MAX_PAGE_SIZE, "link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_daily_sales_audit_page_options(kind: str, txt: str = "", company: str = "") -> list[dict[str, str]]:
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	if kind == "company":
		return _search_named("Company", txt)
	if kind == "branch":
		rows = branch_query("Branch", txt, "name", 0, MAX_LINK_RESULTS, {"company": company})
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "cashier":
		rows = frappe.get_list(
			"User",
			filters={"enabled": 1},
			or_filters={"name": ["like", f"%{txt}%"], "full_name": ["like", f"%{txt}%"]},
			fields=["name", "full_name"],
			order_by="full_name asc, name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.full_name or row.name, "description": row.name} for row in rows]
	if kind == "pos_profile":
		filters: dict[str, Any] = {"name": ["like", f"%{txt}%"]}
		if company:
			filters["company"] = company
		rows = frappe.get_list(
			"POS Profile",
			filters=filters,
			fields=["name"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]
	frappe.throw(_("Unsupported Daily Sales Audit search type."))


@frappe.whitelist()
def get_daily_sales_audit_page(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	dataset = _build_dataset(_coerce_filters(filters))
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_daily_sales_audit_page_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	dataset = _build_dataset(_coerce_filters(filters))
	return {
		"title": dataset["title"],
		"columns": dataset["columns"],
		"rows": dataset["rows"],
		"summary": dataset["summary"],
		"scan": dataset["scan"],
	}


def _build_dataset(filters: frappe._dict) -> dict[str, Any]:
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	validate_filters(filters)
	if not frappe.has_permission("RetailEdge Daily Sales Audit", "read"):
		frappe.throw(_("You do not have permission to view Daily Sales Audit records."), frappe.PermissionError)
	rows = get_data(filters, limit_page_length=MAX_AUDIT_ROWS + 1)
	if len(rows) > MAX_AUDIT_ROWS:
		frappe.throw(
			_("More than {0} Daily Sales Audit records match these filters. Narrow the date range or business scope before loading the preview.").format(MAX_AUDIT_ROWS)
		)
	return {
		"title": _("Daily Sales Audit"),
		"columns": get_columns(),
		"rows": rows,
		"summary": _build_summary(rows),
		"scan": {"rows": len(rows), "row_limit": MAX_AUDIT_ROWS},
	}


def _build_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Audits"), "value": len(rows), "datatype": "Int"},
		{"label": _("Review Required"), "value": len([row for row in rows if cint(row.get("review_required"))]), "datatype": "Int"},
		{"label": _("Clarification Required"), "value": len([row for row in rows if cint(row.get("clarification_required"))]), "datatype": "Int"},
		{"label": _("Net Variance"), "value": sum(flt(row.get("net_variance_amount")) for row in rows), "datatype": "Currency"},
	]


def _page_response(dataset: dict[str, Any], *, page: int | str, page_size: int | str) -> dict[str, Any]:
	rows = list(dataset.get("rows") or [])
	resolved_page_size = max(25, min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	resolved_page = max(cint(page), 1)
	total_rows = len(rows)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	resolved_page = min(resolved_page, total_pages)
	start = (resolved_page - 1) * resolved_page_size
	return {
		**dataset,
		"rows": rows[start : start + resolved_page_size],
		"pagination": {
			"page": resolved_page,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": resolved_page > 1,
			"has_next": resolved_page < total_pages,
		},
	}


def _search_named(doctype: str, txt: str) -> list[dict[str, str]]:
	rows = frappe.get_list(
		doctype,
		filters={"name": ["like", f"%{txt}%"]},
		fields=["name"],
		order_by="name asc",
		limit=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
