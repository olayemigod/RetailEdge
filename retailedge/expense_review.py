from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.cashier_expense import user_is_reviewer
from retailedge.cashier_expense_audit import (
	get_cashier_expenses_for_daily_audit,
	mark_cashier_expense_excluded_from_daily_audit,
	mark_cashier_expense_included_for_daily_audit,
	mark_cashier_expense_needs_clarification,
)
from retailedge.retailedge.report.retailedge_cashier_expense_review.retailedge_cashier_expense_review import (
	build_review_summary,
)
from retailedge.stock_movement_filters import branch_query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_REVIEW_ROWS = 5000
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_expense_review_context() -> dict[str, Any]:
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
			"cashier": "",
			"expense_category": "",
			"expense_status": "",
			"daily_audit_inclusion_status": "Pending Review",
			"posting_ready": "",
			"from_date": f"{nowdate()[:7]}-01",
			"to_date": nowdate(),
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"can_review": bool(user_is_reviewer()),
		"limits": {"rows": MAX_REVIEW_ROWS, "page_size": MAX_PAGE_SIZE, "link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_expense_review_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
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
	if kind == "expense_category":
		return _search_named("RetailEdge Expense Category", txt)
	frappe.throw(_("Unsupported Expense Review search type."))


@frappe.whitelist()
def get_expense_review(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	dataset = _build_expense_review_dataset(_coerce_filters(filters))
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_expense_review_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	dataset = _build_expense_review_dataset(_coerce_filters(filters))
	return {
		"title": dataset["title"],
		"columns": dataset["columns"],
		"rows": dataset["rows"],
		"summary": dataset["summary"],
		"scan": dataset["scan"],
	}


@frappe.whitelist()
def apply_expense_review_action(
	expense_name: str,
	action: str,
	note: str = "",
) -> dict[str, Any]:
	action = str(action or "").strip().lower()
	note = str(note or "").strip()
	if action == "include":
		return mark_cashier_expense_included_for_daily_audit(expense_name, note=note or None)
	if action == "exclude":
		return mark_cashier_expense_excluded_from_daily_audit(expense_name, reason=note or None)
	if action == "clarify":
		return mark_cashier_expense_needs_clarification(expense_name, note=note or None)
	frappe.throw(_("Unsupported Expense Review action."))


def _build_expense_review_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	if not frappe.has_permission("RetailEdge Cashier Expense", "read"):
		frappe.throw(_("You do not have permission to view cashier expenses."), frappe.PermissionError)
	rows = get_cashier_expenses_for_daily_audit(filters=filters, limit_page_length=MAX_REVIEW_ROWS + 1)
	if len(rows) > MAX_REVIEW_ROWS:
		frappe.throw(
			_("More than {0} cashier expenses match these filters. Narrow the period or business scope before loading Expense Review.").format(MAX_REVIEW_ROWS)
		)
	if filters.get("posting_ready") not in (None, ""):
		expected = 1 if str(filters.get("posting_ready")) in {"1", "true", "True"} else 0
		rows = [row for row in rows if (1 if row.get("posting_ready") else 0) == expected]
	for row in rows:
		row["review_action"] = _("Review")
	summary_values = build_review_summary(rows)
	summary = [
		{"label": _("Total Expenses"), "value": flt(summary_values["total_amount"]), "datatype": "Currency"},
		{"label": _("Pending Review"), "value": cint(summary_values["pending_review_count"]), "datatype": "Int"},
		{"label": _("Needs Clarification"), "value": cint(summary_values["needs_clarification_count"]), "datatype": "Int"},
		{"label": _("Posting Ready"), "value": cint(summary_values["posting_ready_count"]), "datatype": "Int"},
		{"label": _("Posting Blocked"), "value": cint(summary_values["posting_blocked_count"]), "datatype": "Int"},
	]
	return {
		"title": _("Expense Review"),
		"columns": _columns(),
		"rows": rows,
		"summary": summary,
		"scan": {"rows": len(rows), "row_limit": MAX_REVIEW_ROWS},
		"can_review": bool(user_is_reviewer()),
	}


def _columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "name", "label": _("Expense"), "fieldtype": "Link", "options": "RetailEdge Cashier Expense"},
		{"fieldname": "expense_date", "label": _("Date"), "fieldtype": "Date"},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Link", "options": "Branch"},
		{"fieldname": "cashier", "label": _("Cashier"), "fieldtype": "Link", "options": "User"},
		{"fieldname": "expense_category", "label": _("Category"), "fieldtype": "Link", "options": "RetailEdge Expense Category"},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency"},
		{"fieldname": "expense_status", "label": _("Expense Status"), "fieldtype": "Data"},
		{"fieldname": "daily_audit_inclusion_status", "label": _("Review Status"), "fieldtype": "Data"},
		{"fieldname": "daily_audit_classification", "label": _("Classification"), "fieldtype": "Data"},
		{"fieldname": "posting_ready", "label": _("Posting Ready"), "fieldtype": "Check"},
		{"fieldname": "posting_block_reason", "label": _("Posting Block"), "fieldtype": "Small Text"},
		{"fieldname": "ledger_status", "label": _("Ledger Status"), "fieldtype": "Data"},
		{"fieldname": "review_action", "label": _("Action"), "fieldtype": "Data"},
	]


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


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
