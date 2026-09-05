from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	has_field,
)
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.receivables_collections import enrich_receivable_rows
from retailedge.stock_movement_filters import branch_query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_LINK_RESULTS = 20
MAX_INVOICE_SCAN_ROWS = 2000
NO_BRANCH_SCOPE_SENTINEL = "__never__"


@frappe.whitelist()
def get_customer_receivables_context() -> dict[str, Any]:
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = ""
	if company and frappe.has_permission("Company", "read", doc=company):
		candidate = str(
			frappe.defaults.get_user_default("RetailEdge Branch")
			or frappe.defaults.get_user_default("Branch")
			or ""
		).strip()
		branch = _resolve_context_branch(company=company, candidate=candidate, user=user)

	today = nowdate()
	return {
		"default_filters": {
			"company": company,
			"branch": branch,
			"customer": "",
			"customer_group": "",
			"ageing_bucket": "All",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"company_currency": _company_currency(company) if company else "",
		"current_balance_date": today,
		"balance_basis": "current_outstanding",
		"limits": {
			"invoice_scan": MAX_INVOICE_SCAN_ROWS,
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
		},
	}


@frappe.whitelist()
def search_customer_receivables_options(
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
	if kind == "customer_group":
		return _search_named("Customer Group", txt)
	if kind == "customer":
		rows = frappe.get_list(
			"Customer",
			or_filters={"name": ["like", f"%{txt}%"], "customer_name": ["like", f"%{txt}%"]},
			fields=["name", "customer_name", "customer_group"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.customer_name or row.name,
				"description": " · ".join(value for value in (row.name, row.customer_group) if value),
			}
			for row in rows
		]
	frappe.throw(_("Unsupported Customer Receivables search type."))


@frappe.whitelist()
def get_customer_receivables(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	dataset = _build_customer_receivables_dataset(resolved)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_customer_receivables_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	return _export_response(_build_customer_receivables_dataset(_coerce_filters(filters)))


def _build_customer_receivables_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters)
	currency = _company_currency(filters.company)
	outstanding_is_base = _outstanding_is_company_currency()
	balance_date = getdate(nowdate())
	rows: list[dict[str, Any]] = []

	for row in headers:
		outstanding = flt(row.outstanding_amount)
		if not outstanding_is_base:
			outstanding *= flt(row.conversion_rate) or 1.0
		if outstanding <= 0:
			continue
		due_date = getdate(row.due_date or row.posting_date)
		overdue_days = max(0, date_diff(balance_date, due_date))
		bucket = _ageing_bucket(overdue_days)
		if filters.get("ageing_bucket") not in (None, "", "All", bucket):
			continue
		rows.append(
			{
				"customer": row.customer,
				"customer_name": row.customer_name or row.customer,
				"invoice": row.name,
				"branch": row.get("branch") or "",
				"posting_date": row.posting_date,
				"due_date": row.due_date,
				"outstanding": outstanding,
				"overdue_days": overdue_days,
				"ageing_bucket": bucket,
				"status": row.status or "",
			}
		)

	collections = enrich_receivable_rows(rows, company=filters.company)
	rows = collections["rows"]
	collection_meta = collections["metadata"]
	rows.sort(
		key=lambda row: (row["overdue_days"], str(row["due_date"] or ""), row["invoice"]),
		reverse=True,
	)
	bucket_totals = defaultdict(float)
	customer_totals = defaultdict(float)
	for row in rows:
		bucket_totals[row["ageing_bucket"]] += flt(row["outstanding"])
		customer_totals[row["customer"]] += flt(row["outstanding"])

	summary = [
		{
			"label": _("Total Receivables"),
			"value": sum(flt(row["outstanding"]) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Open Invoices"), "value": len(rows), "datatype": "Int"},
		{"label": _("Customers Owing"), "value": len(customer_totals), "datatype": "Int"},
		{
			"label": _("Overdue"),
			"value": sum(flt(row["outstanding"]) for row in rows if row["overdue_days"] > 0),
			"datatype": "Currency",
		},
		{"label": _("Over 90 Days"), "value": bucket_totals["91+ Days"], "datatype": "Currency"},
		{
			"label": _("Payment Requests"),
			"value": collection_meta["payment_request_count"],
			"datatype": "Int",
		},
		{
			"label": _("Dunning Ready"),
			"value": collection_meta["dunning_ready_count"],
			"datatype": "Int",
		},
	]
	return {
		"title": _("Customer Receivables"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"current_balance_date": str(balance_date),
		"balance_basis": "current_outstanding",
		"collections": collection_meta,
		"scan": {"invoices": len(headers), "invoice_limit": MAX_INVOICE_SCAN_ROWS},
	}


def _get_permitted_invoice_headers(filters: frappe._dict) -> list[frappe._dict]:
	branch_field, branch_condition = _invoice_branch_scope(filters)
	query_filters: dict[str, Any] = {
		"docstatus": 1,
		"company": filters.company,
		"is_return": 0,
	}
	if filters.get("customer"):
		query_filters["customer"] = filters.customer
	if filters.get("customer_group"):
		query_filters["customer_group"] = filters.customer_group
	if branch_field and branch_condition is not None:
		query_filters[branch_field] = branch_condition

	fields = [
		"name",
		"posting_date",
		"due_date",
		"customer",
		"customer_name",
		"customer_group",
		"currency",
		"conversion_rate",
		"outstanding_amount",
		"status",
	]
	if branch_field:
		fields.append(branch_field)

	rows = frappe.get_list(
		"Sales Invoice",
		filters=query_filters,
		fields=fields,
		order_by="posting_date desc, name desc",
		limit=MAX_INVOICE_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_INVOICE_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} submitted Sales Invoices match these filters. "
				"Narrow the scope before loading Customer Receivables."
			).format(MAX_INVOICE_SCAN_ROWS)
		)
	for row in rows:
		row["branch"] = row.get(branch_field) if branch_field else ""
	return rows


def _invoice_branch_scope(filters: frappe._dict) -> tuple[str | None, Any]:
	fieldname = _sales_invoice_branch_field()
	branch = str(filters.get("branch") or "").strip()
	user = frappe.session.user
	scope = get_operational_branch_scope(filters.company, user=user)
	restricted = bool(scope.get("restricted"))
	allowed = _allowed_scope_branches(scope)
	if branch:
		_validate_receivables_branch(
			company=filters.company,
			branch=branch,
			user=user,
			scope=scope,
		)
		if not fieldname:
			frappe.throw(
				_(
					"Sales Invoice branch attribution is unavailable; "
					"this Branch filter cannot be applied safely."
				)
			)
		return fieldname, branch
	if not restricted:
		return fieldname, None
	if not fieldname:
		frappe.throw(
			_(
				"Sales Invoice branch attribution is unavailable; "
				"branch-restricted receivables cannot be applied safely."
			),
			frappe.PermissionError,
		)
	if not allowed:
		return fieldname, NO_BRANCH_SCOPE_SENTINEL
	if len(allowed) == 1:
		return fieldname, allowed[0]
	return fieldname, ["in", allowed]


def _resolve_context_branch(*, company: str, candidate: str, user: str) -> str:
	scope = get_operational_branch_scope(company, user=user)
	allowed = _allowed_scope_branches(scope)
	candidate = str(candidate or "").strip()
	if candidate:
		try:
			_validate_receivables_branch(
				company=company,
				branch=candidate,
				user=user,
				scope=scope,
			)
			return candidate
		except (frappe.PermissionError, frappe.ValidationError):
			pass
	if scope.get("restricted") and len(allowed) == 1:
		return allowed[0]
	return ""


def _validate_receivables_branch(
	*,
	company: str,
	branch: str,
	user: str,
	scope: dict[str, Any] | None = None,
) -> None:
	scope = scope or get_operational_branch_scope(company, user=user)
	if scope.get("restricted") and branch not in _allowed_scope_branches(scope):
		frappe.throw(
			_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
			frappe.PermissionError,
		)
	validate_operating_branch(company=company, branch=branch, user=user, throw=True)


def _allowed_scope_branches(scope: dict[str, Any]) -> list[str]:
	return sorted(
		str(branch).strip()
		for branch in dict.fromkeys(scope.get("allowed_branches") or [])
		if str(branch or "").strip()
	)


def _sales_invoice_branch_field() -> str | None:
	seen: set[str] = set()
	for candidate in ("retailedge_branch", *BRANCH_FIELD_CANDIDATES):
		if candidate in seen:
			continue
		seen.add(candidate)
		if has_field("Sales Invoice", candidate):
			return candidate
	return None


def _assert_report_access(filters: frappe._dict) -> None:
	if not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("You do not have permission to view Sales Invoices."), frappe.PermissionError)
	_assert_named_read("Company", filters.company)
	for doctype, fieldname in (("Customer", "customer"), ("Customer Group", "customer_group")):
		if filters.get(fieldname):
			_assert_named_read(doctype, filters.get(fieldname))
	branch = str(filters.get("branch") or "").strip()
	if branch:
		_validate_receivables_branch(
			company=filters.company,
			branch=branch,
			user=frappe.session.user,
		)


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	if filters.get("as_of_date") and str(filters.get("as_of_date")) != nowdate():
		frappe.throw(
			_(
				"Customer Receivables shows current ERPNext outstanding balances only. "
				"Historical balances require ledger reconstruction and cannot use a past As of Date."
			),
		)
	if str(filters.get("ageing_bucket") or "All") not in {
		"All",
		"Current",
		"1-30 Days",
		"31-60 Days",
		"61-90 Days",
		"91+ Days",
	}:
		frappe.throw(_("Unsupported ageing bucket."))


def _page_response(
	dataset: dict[str, Any],
	*,
	page: int | str,
	page_size: int | str,
) -> dict[str, Any]:
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


def _export_response(dataset: dict[str, Any]) -> dict[str, Any]:
	return {
		"title": dataset.get("title") or "",
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"current_balance_date": dataset.get("current_balance_date") or "",
		"balance_basis": dataset.get("balance_basis") or "",
		"collections": dataset.get("collections") or {},
		"scan": dataset.get("scan") or {},
	}


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer"},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data"},
		{
			"fieldname": "invoice",
			"label": _("Sales Invoice"),
			"fieldtype": "Link",
			"options": "Sales Invoice",
		},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data"},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date"},
		{"fieldname": "due_date", "label": _("Due Date"), "fieldtype": "Date"},
		{
			"fieldname": "outstanding",
			"label": _("Outstanding"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{"fieldname": "overdue_days", "label": _("Days Overdue"), "fieldtype": "Int"},
		{"fieldname": "ageing_bucket", "label": _("Age"), "fieldtype": "Data"},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data"},
		{
			"fieldname": "payment_request",
			"label": _("Payment Request"),
			"fieldtype": "Link",
			"options": "Payment Request",
		},
		{
			"fieldname": "payment_request_status",
			"label": _("Payment Status"),
			"fieldtype": "Data",
		},
		{"fieldname": "dunning", "label": _("Dunning"), "fieldtype": "Link", "options": "Dunning"},
		{
			"fieldname": "collection_status",
			"label": _("Collection Status"),
			"fieldtype": "Data",
		},
	]


def _ageing_bucket(overdue_days: int) -> str:
	if overdue_days <= 0:
		return "Current"
	if overdue_days <= 30:
		return "1-30 Days"
	if overdue_days <= 60:
		return "31-60 Days"
	if overdue_days <= 90:
		return "61-90 Days"
	return "91+ Days"


def _outstanding_is_company_currency() -> bool:
	field = frappe.get_meta("Sales Invoice").get_field("outstanding_amount")
	options = str(getattr(field, "options", "") or "")
	return options.startswith("Company:") or "company:default_currency" in options.lower()


def _company_currency(company: str) -> str:
	return str(frappe.get_cached_value("Company", company, "default_currency") or "") if company else ""


def _search_named(doctype: str, txt: str) -> list[dict[str, str]]:
	rows = frappe.get_list(
		doctype,
		filters={"name": ["like", f"%{txt}%"]},
		fields=["name"],
		order_by="name asc",
		limit=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _assert_named_read(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
