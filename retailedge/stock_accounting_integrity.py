from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

from retailedge.reporting_scope import assert_company_wide_report_scope

NATIVE_REPORT_NAME = "Stock and Account Value Comparison"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_MISMATCH_ROWS = 5000
MAX_REVIEW_WINDOW_DAYS = 366
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_stock_accounting_integrity_context() -> dict[str, Any]:
	"""Return permission-checked defaults for the Company-wide C22 review."""
	_assert_authenticated()
	_assert_native_report_access()
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if company:
		_assert_company_read(company)
		_assert_company_wide_branch_scope(company)
	return {
		"default_filters": {
			"company": company,
			"account": "",
			"from_date": add_days(nowdate(), -30),
			"as_on_date": nowdate(),
		},
		"tenant_name": company,
		"branch_name": "Company-wide",
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"company_currency": _company_currency(company),
		"native_report_name": NATIVE_REPORT_NAME,
		"can_open_native_report": 1,
		"limits": {
			"review_window_days": MAX_REVIEW_WINDOW_DAYS,
			"mismatch_rows": MAX_MISMATCH_ROWS,
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
		},
	}


@frappe.whitelist()
def search_stock_accounting_integrity_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
	"""Return bounded, permission-aware Company or Stock Account options."""
	_assert_authenticated()
	_assert_native_report_access()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or "").strip()

	if kind == "company":
		rows = frappe.get_list(
			"Company",
			filters={"name": ["like", f"%{txt}%"]},
			fields=["name", "default_currency"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.name,
				"description": row.default_currency or "",
			}
			for row in rows
		]

	if kind == "account":
		if not company:
			return []
		_assert_company_read(company)
		_assert_company_wide_branch_scope(company)
		rows = frappe.get_list(
			"Account",
			filters={
				"company": company,
				"account_type": "Stock",
				"is_group": 0,
				"name": ["like", f"%{txt}%"],
			},
			fields=["name", "account_name"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.account_name or row.name,
				"description": row.name,
			}
			for row in rows
		]

	frappe.throw(_("Unsupported Stock & Accounting Integrity search type."))


@frappe.whitelist()
def get_stock_accounting_integrity(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	dataset = _build_stock_accounting_integrity_dataset(_coerce_filters(filters))
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_stock_accounting_integrity_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	"""Return the exact same governed mismatch dataset used by the page."""
	return _build_stock_accounting_integrity_dataset(_coerce_filters(filters))


def _build_stock_accounting_integrity_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_authenticated()
	_assert_company_read(filters.company)
	_assert_native_report_access()
	_assert_company_wide_branch_scope(filters.company)
	_assert_stock_account(filters.get("account"), filters.company)

	native_filters = frappe._dict(
		{
			"company": filters.company,
			"account": filters.get("account") or None,
			"from_date": getdate(filters.from_date),
			"as_on_date": getdate(filters.as_on_date),
		}
	)
	columns, rows = _load_native_mismatches(native_filters)
	rows = [_plain_row(row) for row in rows]
	if len(rows) > MAX_MISMATCH_ROWS:
		frappe.throw(
			_(
				"More than {0} stock/accounting exceptions match this review. Narrow the date range or select one Stock Account before continuing."
			).format(MAX_MISMATCH_ROWS)
		)

	return {
		"columns": [_plain_column(column) for column in columns],
		"rows": rows,
		"summary": _summary(rows),
		"company_currency": _company_currency(filters.company),
		"scope": {
			"company": filters.company,
			"account": filters.get("account") or "",
			"from_date": str(getdate(filters.from_date)),
			"as_on_date": str(getdate(filters.as_on_date)),
			"scope_type": "Company-wide accounting control",
		},
		"scan": {
			"mismatch_rows": len(rows),
			"mismatch_limit": MAX_MISMATCH_ROWS,
		},
		"native_report_name": NATIVE_REPORT_NAME,
		"read_only": 1,
	}


def _load_native_mismatches(filters: frappe._dict) -> tuple[list[Any], list[Any]]:
	"""Delegate C22 mismatch truth to ERPNext's native comparison report."""
	from erpnext.stock.report.stock_and_account_value_comparison import (
		stock_and_account_value_comparison as native_report,
	)

	columns, rows = native_report.execute(filters)
	return list(columns or []), list(rows or [])


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	differences = [flt(row.get("difference_value")) for row in rows]
	return [
		{"label": _("Mismatched Vouchers"), "value": len(rows), "datatype": "Int"},
		{"label": _("Absolute Difference"), "value": sum(abs(value) for value in differences), "datatype": "Currency"},
		{"label": _("Net Difference"), "value": sum(differences), "datatype": "Currency"},
		{
			"label": _("Stock-led Exceptions"),
			"value": sum(1 for row in rows if row.get("ledger_type") == "Stock Ledger Entry"),
			"datatype": "Int",
		},
		{
			"label": _("GL-led Exceptions"),
			"value": sum(1 for row in rows if row.get("ledger_type") == "GL Entry"),
			"datatype": "Int",
		},
	]


def _validate_filters(filters: frappe._dict) -> None:
	company = str(filters.get("company") or "").strip()
	from_date = filters.get("from_date")
	as_on_date = filters.get("as_on_date")
	if not company:
		frappe.throw(_("Company is required."))
	if not from_date or not as_on_date:
		frappe.throw(_("From Date and As On Date are required."))
	start = getdate(from_date)
	end = getdate(as_on_date)
	if start > end:
		frappe.throw(_("From Date cannot be after As On Date."))
	if date_diff(end, start) > MAX_REVIEW_WINDOW_DAYS - 1:
		frappe.throw(
			_("Stock & Accounting Integrity supports at most {0} days per review. Narrow the date range.").format(
				MAX_REVIEW_WINDOW_DAYS
			)
		)
	filters.company = company
	filters.from_date = start
	filters.as_on_date = end
	filters.account = str(filters.get("account") or "").strip()


def _assert_authenticated() -> None:
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to review stock and accounting integrity."), frappe.PermissionError)


def _assert_company_read(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to Company {0}.").format(company), frappe.PermissionError)


def _assert_native_report_access() -> None:
	try:
		from frappe.desk.query_report import get_report_doc

		get_report_doc(NATIVE_REPORT_NAME)
	except frappe.PermissionError:
		raise
	except Exception:
		frappe.throw(
			_("You do not have permission to open ERPNext Stock and Account Value Comparison."),
			frappe.PermissionError,
		)


def _assert_company_wide_branch_scope(company: str, *, user: str | None = None) -> None:
	assert_company_wide_report_scope(company, user=user)


def _assert_stock_account(account: str, company: str) -> None:
	if not account:
		return
	if not frappe.db.exists("Account", account):
		frappe.throw(_("Account {0} does not exist.").format(account))
	if not frappe.has_permission("Account", "read", doc=account):
		frappe.throw(_("You do not have permission to use Account {0}.").format(account), frappe.PermissionError)
	row = frappe.db.get_value("Account", account, ["company", "account_type", "is_group"], as_dict=True) or {}
	if row.get("company") != company:
		frappe.throw(_("Account {0} does not belong to Company {1}.").format(account, company))
	if row.get("account_type") != "Stock" or cint(row.get("is_group")):
		frappe.throw(_("Select a non-group Stock Account belonging to the selected Company."))


def _plain_row(row: Any) -> dict[str, Any]:
	return dict(row or {})


def _plain_column(column: Any) -> dict[str, Any]:
	return dict(column or {})


def _company_currency(company: str) -> str:
	return str(frappe.get_cached_value("Company", company, "default_currency") or "") if company else ""


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})


def _page_response(dataset: dict[str, Any], *, page: int | str, page_size: int | str) -> dict[str, Any]:
	rows = list(dataset.get("rows") or [])
	resolved_page_size = max(25, min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	resolved_page = max(cint(page), 1)
	total_rows = len(rows)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	resolved_page = min(resolved_page, total_pages)
	start = (resolved_page - 1) * resolved_page_size
	end = start + resolved_page_size
	return {
		**dataset,
		"rows": rows[start:end],
		"pagination": {
			"page": resolved_page,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": resolved_page > 1,
			"has_next": resolved_page < total_pages,
		},
	}
