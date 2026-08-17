from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, getdate, today

from retailedge.branch_context import (
	get_branch_query_filters,
	get_user_allowed_branches,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.cashier_expense import get_cashier_roles, get_reviewer_roles

EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
CATEGORY_DOCTYPE = "RetailEdge Expense Category"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_LINK_RESULTS = 20
MAX_EXPORT_ROWS = 5000
MAX_DATE_RANGE_DAYS = 366

_PRIVILEGED_CASHIER_VISIBILITY_ROLES = get_reviewer_roles() | {"Accounts User"}
_EXPENSE_STATUSES = (
	"Draft",
	"Submitted",
	"Pending Ledger",
	"Rejected",
	"Posted",
	"Cancelled",
)
_BASE_ROW_FIELDS = (
	"name",
	"expense_date",
	"branch",
	"expense_category",
	"amount",
	"expense_status",
	"ledger_status",
	"posting_ready",
	"description",
	"docstatus",
)


@frappe.whitelist()
def get_expense_register_context() -> dict[str, Any]:
	_assert_expense_read_access()
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if company:
		_assert_company_read_access(company)

	branch = ""
	candidate = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	if company and candidate:
		try:
			validate_user_branch_access(candidate, user=user, company=company, throw=True)
			branch = candidate
		except (frappe.PermissionError, frappe.ValidationError):
			branch = ""
	if company and not branch and not user_has_global_branch_access(user=user):
		allowed = list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
		if len(allowed) == 1:
			branch = allowed[0]

	return {
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
			"expense_category": "",
			"expense_status": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"show_cashier": int(_can_view_other_cashiers(user=user)),
		"statuses": list(_EXPENSE_STATUSES),
		"limits": {
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
			"export_rows": MAX_EXPORT_ROWS,
			"date_range_days": MAX_DATE_RANGE_DAYS,
		},
	}


@frappe.whitelist()
def search_expense_register_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
) -> list[dict[str, str]]:
	_assert_expense_read_access()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()

	if kind == "company":
		return _search_companies(txt)
	if company:
		_assert_company_read_access(company)
	if kind == "branch":
		return _search_branches(txt=txt, company=company)
	if kind == "expense_category":
		return _search_categories(txt=txt, company=company)
	frappe.throw(_("Unsupported Expense Register search type."))


@frappe.whitelist()
def get_expense_register(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	query_filters = _build_query_filters(filters)
	page = max(1, cint(page) or 1)
	page_size = max(1, min(cint(page_size) or cint(filters.get("page_size")) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	show_cashier = _can_view_other_cashiers()

	summary = _get_summary(query_filters)
	total_rows = cint(summary.get("count"))
	total_pages = max(1, ceil(total_rows / page_size)) if total_rows else 1
	if page > total_pages:
		page = total_pages

	fields = list(_BASE_ROW_FIELDS)
	if show_cashier:
		fields.insert(3, "cashier")
	rows = frappe.get_list(
		EXPENSE_DOCTYPE,
		filters=query_filters,
		fields=fields,
		order_by="expense_date desc, creation desc",
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	rows = [_serialise_row(row, show_cashier=show_cashier) for row in rows]
	return {
		"columns": _columns(show_cashier=show_cashier),
		"rows": rows,
		"summary": _summary_cards(summary),
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": page > 1,
			"has_next": page < total_pages,
		},
		"scope": {
			"company": filters.get("company") or "",
			"branch": filters.get("branch") or "",
			"cashier_scope": "permitted" if show_cashier else "self",
		},
	}


@frappe.whitelist()
def get_expense_register_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	query_filters = _build_query_filters(filters)
	show_cashier = _can_view_other_cashiers()
	fields = list(_BASE_ROW_FIELDS)
	if show_cashier:
		fields.insert(3, "cashier")
	rows = frappe.get_list(
		EXPENSE_DOCTYPE,
		filters=query_filters,
		fields=fields,
		order_by="expense_date desc, creation desc",
		limit_page_length=MAX_EXPORT_ROWS + 1,
	)
	if len(rows) > MAX_EXPORT_ROWS:
		frappe.throw(
			_("More than {0} expenses match this export. Narrow the date, Branch, Category, or Status filters first.").format(
				MAX_EXPORT_ROWS
			)
		)
	summary = _get_summary(query_filters)
	return {
		"columns": _columns(show_cashier=show_cashier),
		"rows": [_serialise_row(row, show_cashier=show_cashier) for row in rows],
		"summary": _summary_cards(summary),
	}


def _build_query_filters(filters: frappe._dict) -> dict[str, Any]:
	_assert_expense_read_access()
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_company_read_access(company)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	query_filters: dict[str, Any] = {"company": company}
	branch_scope = get_branch_query_filters(
		EXPENSE_DOCTYPE,
		user=frappe.session.user,
		company=company,
		branch=branch or None,
		strict=True,
	)
	query_filters.update(branch_scope.get("filters") or {})
	if branch:
		query_filters["branch"] = branch

	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None
	if from_date and to_date:
		if from_date > to_date:
			frappe.throw(_("From Date cannot be after To Date."))
		if (to_date - from_date).days + 1 > MAX_DATE_RANGE_DAYS:
			frappe.throw(
				_("Expense Register supports up to {0} days per request. Narrow the date range.").format(
					MAX_DATE_RANGE_DAYS
				)
			)
		query_filters["expense_date"] = ["between", [from_date, to_date]]
	elif from_date:
		query_filters["expense_date"] = [">=", from_date]
	elif to_date:
		query_filters["expense_date"] = ["<=", to_date]

	category = str(filters.get("expense_category") or "").strip()
	if category:
		_assert_category_in_company_scope(category=category, company=company)
		query_filters["expense_category"] = category

	status = str(filters.get("expense_status") or "").strip()
	if status:
		if status not in _EXPENSE_STATUSES:
			frappe.throw(_("Unsupported Expense Status."))
		if status == "Cancelled":
			query_filters["docstatus"] = 2
		else:
			query_filters["docstatus"] = ["!=", 2]
			query_filters["expense_status"] = status
	else:
		query_filters["docstatus"] = ["!=", 2]
		query_filters["expense_status"] = ["!=", "Cancelled"]

	if not _can_view_other_cashiers():
		query_filters["cashier"] = frappe.session.user
	return query_filters


def _get_summary(query_filters: dict[str, Any]) -> dict[str, Any]:
	overall = frappe.get_list(
		EXPENSE_DOCTYPE,
		filters=query_filters,
		fields=["count(name) as count", "sum(amount) as total_amount"],
		limit_page_length=1,
	)
	status_rows = frappe.get_list(
		EXPENSE_DOCTYPE,
		filters=query_filters,
		fields=["expense_status", "count(name) as count", "sum(amount) as amount"],
		group_by="expense_status",
		limit_page_length=len(_EXPENSE_STATUSES) + 1,
	)
	posting_rows = frappe.get_list(
		EXPENSE_DOCTYPE,
		filters=query_filters,
		fields=["posting_ready", "count(name) as count"],
		group_by="posting_ready",
		limit_page_length=3,
	)
	base = overall[0] if overall else frappe._dict(count=0, total_amount=0)
	by_status = {
		str(row.expense_status or "Draft"): {
			"count": cint(row.count),
			"amount": flt(row.amount),
		}
		for row in status_rows
	}
	by_posting = {cint(row.posting_ready): cint(row.count) for row in posting_rows}
	return {
		"count": cint(base.count),
		"total_amount": flt(base.total_amount),
		"submitted_count": cint((by_status.get("Submitted") or {}).get("count")),
		"pending_ledger_count": cint((by_status.get("Pending Ledger") or {}).get("count")),
		"rejected_count": cint((by_status.get("Rejected") or {}).get("count")),
		"posting_ready_count": cint(by_posting.get(1)),
		"posting_blocked_count": cint(by_posting.get(0)),
		"by_status": by_status,
	}


def _summary_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
	return [
		{"label": _("Total Expenses"), "value": flt(summary.get("total_amount")), "type": "Currency"},
		{"label": _("Expense Count"), "value": cint(summary.get("count")), "type": "Int"},
		{"label": _("Submitted for Review"), "value": cint(summary.get("submitted_count")), "type": "Int"},
		{"label": _("Posting Blocked"), "value": cint(summary.get("posting_blocked_count")), "type": "Int"},
	]


def _serialise_row(row, *, show_cashier: bool) -> dict[str, Any]:
	status = "Cancelled" if cint(row.docstatus) == 2 else str(row.expense_status or ("Submitted" if cint(row.docstatus) == 1 else "Draft"))
	result = {
		"name": row.name,
		"expense_date": row.expense_date,
		"branch": row.branch or "",
		"expense_category": row.expense_category or "",
		"amount": flt(row.amount),
		"expense_status": status,
		"ledger_status": row.ledger_status or "Not Applicable",
		"posting_ready": cint(row.posting_ready),
		"description": row.description or "",
	}
	if show_cashier:
		result["cashier"] = row.cashier or ""
	return result


def _columns(*, show_cashier: bool) -> list[dict[str, Any]]:
	columns = [
		{"label": _("Expense"), "fieldname": "name", "type": "Link", "doctype": EXPENSE_DOCTYPE},
		{"label": _("Date"), "fieldname": "expense_date", "type": "Date"},
		{"label": _("Branch"), "fieldname": "branch", "type": "Data"},
	]
	if show_cashier:
		columns.append({"label": _("Cashier"), "fieldname": "cashier", "type": "Data"})
	columns.extend(
		[
			{"label": _("Category"), "fieldname": "expense_category", "type": "Data"},
			{"label": _("Amount"), "fieldname": "amount", "type": "Currency"},
			{"label": _("Status"), "fieldname": "expense_status", "type": "Data"},
			{"label": _("Ledger"), "fieldname": "ledger_status", "type": "Data"},
			{"label": _("Posting Ready"), "fieldname": "posting_ready", "type": "Check"},
			{"label": _("Description"), "fieldname": "description", "type": "Data"},
		]
	)
	return columns


def _search_companies(txt: str) -> list[dict[str, str]]:
	rows = frappe.get_list(
		"Company",
		or_filters={"name": ["like", f"%{txt}%"], "company_name": ["like", f"%{txt}%"]},
		fields=["name", "company_name"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.company_name or row.name} for row in rows]


def _search_branches(*, txt: str, company: str) -> list[dict[str, str]]:
	if not company:
		return []
	filters: dict[str, Any] = {"company": company}
	if not user_has_global_branch_access(user=frappe.session.user):
		allowed = list(get_user_allowed_branches(user=frappe.session.user, company=company).get("branches") or [])
		if not allowed:
			return []
		filters["name"] = ["in", allowed]
	rows = frappe.get_list(
		"Branch",
		filters=filters,
		or_filters={"name": ["like", f"%{txt}%"]},
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _search_categories(*, txt: str, company: str) -> list[dict[str, str]]:
	filters: list[list[Any]] = [[CATEGORY_DOCTYPE, "is_active", "=", 1]]
	if txt:
		filters.append([CATEGORY_DOCTYPE, "category_name", "like", f"%{txt}%"])
	or_filters = None
	if company:
		or_filters = [
			[CATEGORY_DOCTYPE, "company", "=", company],
			[CATEGORY_DOCTYPE, "company", "is", "not set"],
		]
	rows = frappe.get_list(
		CATEGORY_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=["name", "category_name", "category_code", "description"],
		order_by="category_name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [
		{
			"value": row.name,
			"label": row.category_name or row.name,
			"description": row.description or (str(row.category_code or "")),
		}
		for row in rows
	]


def _assert_category_in_company_scope(*, category: str, company: str) -> None:
	if not frappe.db.exists(CATEGORY_DOCTYPE, category):
		frappe.throw(_("Expense Category {0} does not exist.").format(category))
	if not frappe.has_permission(CATEGORY_DOCTYPE, "read", doc=category):
		frappe.throw(_("You do not have permission to use Expense Category {0}.").format(category), frappe.PermissionError)
	row = frappe.db.get_value(CATEGORY_DOCTYPE, category, ["company", "is_active"], as_dict=True)
	if not row or not cint(row.is_active):
		frappe.throw(_("Expense Category {0} is inactive.").format(category))
	if row.company and row.company != company:
		frappe.throw(_("Expense Category {0} is outside Company {1}.").format(category, company), frappe.PermissionError)


def _assert_expense_read_access() -> None:
	if not frappe.db.exists("DocType", EXPENSE_DOCTYPE) or not frappe.has_permission(EXPENSE_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view Cashier Expenses."), frappe.PermissionError)


def _assert_company_read_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to use Company {0}.").format(company), frappe.PermissionError)


def _can_view_other_cashiers(user: str | None = None) -> bool:
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if roles.intersection(_PRIVILEGED_CASHIER_VISIBILITY_ROLES):
		return True
	if roles.intersection(get_cashier_roles()):
		return False
	return False


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if not filters:
		return frappe._dict()
	parsed = frappe.parse_json(filters) if isinstance(filters, str) else filters
	if isinstance(parsed, frappe._dict):
		return parsed
	if isinstance(parsed, dict):
		return frappe._dict(parsed)
	frappe.throw(_("Invalid Expense Register filters."))
	return frappe._dict()
