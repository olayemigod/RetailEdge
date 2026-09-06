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
	resolve_branch_from_warehouse,
)
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.stock_movement_filters import branch_query, warehouse_query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_LINK_RESULTS = 20
MAX_INVOICE_SCAN_ROWS = 2000
MAX_ITEM_SCAN_ROWS = 10000
NO_BRANCH_SCOPE_SENTINEL = "__never__"


def _report_context_defaults() -> dict[str, Any]:
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
		"company": company,
		"from_date": f"{today[:7]}-01",
		"to_date": today,
		"as_of_date": today,
		"branch": branch,
		"supplier": "",
		"supplier_group": "",
		"item_code": "",
		"item_group": "",
		"warehouse": "",
		"status": "",
		"invoice_kind": "All",
		"ageing_bucket": "All",
		"page_size": DEFAULT_PAGE_SIZE,
	}


@frappe.whitelist()
def get_purchase_reporting_context() -> dict[str, Any]:
	defaults = _report_context_defaults()
	user = frappe.session.user
	company = defaults.get("company")
	return {
		"default_filters": defaults,
		"tenant_name": company,
		"branch_name": defaults.get("branch"),
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"company_currency": _company_currency(company) if company else "",
		"limits": {
			"invoice_scan": MAX_INVOICE_SCAN_ROWS,
			"item_scan": MAX_ITEM_SCAN_ROWS,
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
		},
	}


@frappe.whitelist()
def search_purchase_reporting_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	item_group: str = "",
) -> list[dict[str, str]]:
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()
	item_group = str(item_group or "").strip()

	if kind == "company":
		return _search_named("Company", txt)
	if kind == "branch":
		rows = branch_query("Branch", txt, "name", 0, MAX_LINK_RESULTS, {"company": company})
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "warehouse":
		rows = warehouse_query(
			"Warehouse", txt, "name", 0, MAX_LINK_RESULTS, {"company": company, "branch": branch}
		)
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "supplier_group":
		return _search_named("Supplier Group", txt)
	if kind == "supplier":
		rows = frappe.get_list(
			"Supplier",
			or_filters={"name": ["like", f"%{txt}%"], "supplier_name": ["like", f"%{txt}%"]},
			fields=["name", "supplier_name", "supplier_group"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.supplier_name or row.name,
				"description": " · ".join(value for value in (row.name, row.supplier_group) if value),
			}
			for row in rows
		]
	if kind == "item_group":
		return _search_named("Item Group", txt)
	if kind == "item":
		item_filters: dict[str, Any] = {"disabled": 0}
		if item_group:
			item_filters["item_group"] = item_group
		rows = frappe.get_list(
			"Item",
			filters=item_filters,
			or_filters={"name": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]},
			fields=["name", "item_name", "item_group", "stock_uom"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.item_name or row.name,
				"description": " · ".join(
					value for value in (row.name, row.item_group, row.stock_uom) if value
				),
				"item_group": row.item_group or "",
			}
			for row in rows
		]
	frappe.throw(_("Unsupported Purchase reporting search type."))


@frappe.whitelist()
def get_purchase_register(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_purchase_register_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_purchase_register_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	return _export_response(_build_purchase_register_dataset(_coerce_filters(filters)))


@frappe.whitelist()
def get_supplier_payables(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_supplier_payables_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_supplier_payables_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	return _export_response(_build_supplier_payables_dataset(_coerce_filters(filters)))


def _build_purchase_register_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_purchase_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters, as_of=False)
	if any(filters.get(field) for field in ("item_code", "item_group", "warehouse")):
		matching_items = _get_invoice_items([row.name for row in headers], filters)
		matching_parents = {row.parent for row in matching_items}
		headers = [row for row in headers if row.name in matching_parents]

	currency = _company_currency(filters.company)
	outstanding_is_base = _outstanding_is_company_currency()
	rows: list[dict[str, Any]] = []
	for row in headers:
		is_return = cint(row.is_return)
		outstanding = flt(row.outstanding_amount)
		if not outstanding_is_base:
			outstanding *= flt(row.conversion_rate) or 1.0
		if is_return and outstanding > 0:
			outstanding = -abs(outstanding)
		rows.append(
			{
				"invoice": row.name,
				"posting_date": row.posting_date,
				"due_date": row.due_date,
				"supplier": row.supplier,
				"supplier_name": row.supplier_name or row.supplier,
				"branch": row.get("branch") or "",
				"invoice_type": _("Return") if is_return else _("Purchase"),
				"transaction_currency": row.currency,
				"net_amount": _signed_for_return(row.base_net_total, is_return),
				"tax_amount": _signed_for_return(row.base_total_taxes_and_charges, is_return),
				"grand_total": _signed_for_return(row.base_grand_total, is_return),
				"outstanding": outstanding,
				"status": row.status or "",
				"return_against": row.return_against or "",
			}
		)
	rows.sort(
		key=lambda row: (str(row.get("posting_date") or ""), str(row.get("invoice") or "")), reverse=True
	)
	returns = [row for row in rows if row.get("invoice_type") == _("Return")]
	summary = [
		{
			"label": _("Net Purchased"),
			"value": sum(flt(row["grand_total"]) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Invoices"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Returns"),
			"value": sum(abs(flt(row["grand_total"])) for row in returns),
			"datatype": "Currency",
		},
		{
			"label": _("Outstanding"),
			"value": sum(flt(row["outstanding"]) for row in rows),
			"datatype": "Currency",
		},
	]
	return {
		"title": _("Purchase Register"),
		"columns": _purchase_register_columns(currency),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"scan": {"invoices": len(headers), "invoice_limit": MAX_INVOICE_SCAN_ROWS},
	}


def _build_supplier_payables_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_payables_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters, as_of=True)
	currency = _company_currency(filters.company)
	outstanding_is_base = _outstanding_is_company_currency()
	as_of_date = getdate(filters.as_of_date)
	rows: list[dict[str, Any]] = []
	for row in headers:
		outstanding = flt(row.outstanding_amount)
		if not outstanding_is_base:
			outstanding *= flt(row.conversion_rate) or 1.0
		if cint(row.is_return) and outstanding > 0:
			outstanding = -abs(outstanding)
		if outstanding <= 0:
			continue
		due_date = getdate(row.due_date or row.posting_date)
		overdue_days = max(0, date_diff(as_of_date, due_date))
		bucket = _ageing_bucket(overdue_days)
		if filters.get("ageing_bucket") not in (None, "", "All", bucket):
			continue
		rows.append(
			{
				"invoice": row.name,
				"supplier": row.supplier,
				"supplier_name": row.supplier_name or row.supplier,
				"branch": row.get("branch") or "",
				"posting_date": row.posting_date,
				"due_date": row.due_date,
				"outstanding": outstanding,
				"overdue_days": overdue_days,
				"ageing_bucket": bucket,
				"status": row.status or "",
			}
		)
	rows.sort(key=lambda row: (row["overdue_days"], str(row["due_date"] or ""), row["invoice"]), reverse=True)
	bucket_totals = defaultdict(float)
	for row in rows:
		bucket_totals[row["ageing_bucket"]] += flt(row["outstanding"])
	summary = [
		{
			"label": _("Total Payables"),
			"value": sum(flt(row["outstanding"]) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Open Bills"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Overdue"),
			"value": sum(flt(row["outstanding"]) for row in rows if row["overdue_days"] > 0),
			"datatype": "Currency",
		},
		{"label": _("Over 90 Days"), "value": bucket_totals["91+ Days"], "datatype": "Currency"},
	]
	return {
		"title": _("Supplier Payables"),
		"columns": _supplier_payables_columns(currency),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"scan": {"invoices": len(headers), "invoice_limit": MAX_INVOICE_SCAN_ROWS},
	}


def _get_permitted_invoice_headers(filters: frappe._dict, *, as_of: bool) -> list[frappe._dict]:
	branch_field, branch_condition = _invoice_branch_scope(filters)
	query_filters: dict[str, Any] = {"docstatus": 1, "company": filters.company}
	if as_of:
		query_filters["posting_date"] = ["<=", filters.as_of_date]
	else:
		query_filters["posting_date"] = ["between", [filters.from_date, filters.to_date]]
	if filters.get("supplier"):
		query_filters["supplier"] = filters.supplier
	if filters.get("supplier_group"):
		query_filters["supplier_group"] = filters.supplier_group
	if filters.get("status"):
		query_filters["status"] = filters.status
	invoice_kind = str(filters.get("invoice_kind") or "All").strip()
	if invoice_kind == "Purchases":
		query_filters["is_return"] = 0
	elif invoice_kind == "Returns":
		query_filters["is_return"] = 1
	if branch_field and branch_condition is not None:
		query_filters[branch_field] = branch_condition

	fields = [
		"name",
		"posting_date",
		"due_date",
		"supplier",
		"supplier_name",
		"supplier_group",
		"currency",
		"conversion_rate",
		"base_net_total",
		"base_total_taxes_and_charges",
		"base_grand_total",
		"outstanding_amount",
		"status",
		"is_return",
		"return_against",
	]
	if branch_field:
		fields.append(branch_field)
	rows = frappe.get_list(
		"Purchase Invoice",
		filters=query_filters,
		fields=fields,
		order_by="posting_date desc, name desc",
		limit=MAX_INVOICE_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_INVOICE_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} submitted Purchase Invoices match these filters. Narrow the scope before loading this report."
			).format(MAX_INVOICE_SCAN_ROWS)
		)
	for row in rows:
		row["branch"] = row.get(branch_field) if branch_field else ""
	return rows


def _get_invoice_items(invoice_names: list[str], filters: frappe._dict) -> list[frappe._dict]:
	if not invoice_names:
		return []
	query_filters: dict[str, Any] = {"parenttype": "Purchase Invoice", "parent": ["in", invoice_names]}
	if filters.get("item_code"):
		query_filters["item_code"] = filters.item_code
	if filters.get("item_group"):
		query_filters["item_group"] = filters.item_group
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters.warehouse
	rows = frappe.get_all(
		"Purchase Invoice Item",
		filters=query_filters,
		fields=[
			"parent",
			"item_code",
			"item_name",
			"item_group",
			"stock_uom",
			"qty",
			"base_net_amount",
			"warehouse",
		],
		order_by="parent asc, idx asc",
		limit=MAX_ITEM_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_ITEM_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} Purchase Invoice item rows match these filters. Narrow the scope before loading this report."
			).format(MAX_ITEM_SCAN_ROWS)
		)
	return rows


def _invoice_branch_scope(filters: frappe._dict) -> tuple[str | None, Any]:
	fieldname = _purchase_invoice_branch_field()
	branch = str(filters.get("branch") or "").strip()
	user = frappe.session.user
	scope = get_operational_branch_scope(filters.company, user=user)
	restricted = bool(scope.get("restricted"))
	allowed = _allowed_scope_branches(scope)
	if branch:
		_validate_purchase_branch(
			company=filters.company,
			branch=branch,
			user=user,
			scope=scope,
		)
		if not fieldname:
			frappe.throw(
				_(
					"Purchase Invoice branch attribution is unavailable; this Branch filter cannot be applied safely."
				)
			)
		return fieldname, branch
	if not restricted:
		return fieldname, None
	if not fieldname:
		frappe.throw(
			_(
				"Purchase Invoice branch attribution is unavailable; branch-restricted reporting cannot be applied safely."
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
			_validate_purchase_branch(
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


def _validate_purchase_branch(
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


def _purchase_invoice_branch_field() -> str | None:
	seen: set[str] = set()
	for candidate in ("retailedge_branch", *BRANCH_FIELD_CANDIDATES):
		if candidate in seen:
			continue
		seen.add(candidate)
		if has_field("Purchase Invoice", candidate):
			return candidate
	return None


def _assert_report_access(filters: frappe._dict) -> None:
	if not frappe.has_permission("Purchase Invoice", "read"):
		frappe.throw(_("You do not have permission to view Purchase Invoices."), frappe.PermissionError)
	_assert_named_read("Company", filters.company)
	for doctype, fieldname in (
		("Supplier", "supplier"),
		("Supplier Group", "supplier_group"),
		("Item", "item_code"),
		("Item Group", "item_group"),
		("Warehouse", "warehouse"),
	):
		if filters.get(fieldname):
			_assert_named_read(doctype, filters.get(fieldname))
	branch = str(filters.get("branch") or "").strip()
	if branch:
		_validate_purchase_branch(
			company=filters.company,
			branch=branch,
			user=frappe.session.user,
		)
	warehouse = str(filters.get("warehouse") or "").strip()
	if warehouse:
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company != filters.company:
			frappe.throw(
				_("Warehouse {0} does not belong to Company {1}.").format(warehouse, filters.company)
			)
		resolved_branch = resolve_branch_from_warehouse(warehouse, company=filters.company)
		if resolved_branch:
			_validate_purchase_branch(
				company=filters.company,
				branch=resolved_branch,
				user=frappe.session.user,
			)
			if branch and resolved_branch != branch:
				frappe.throw(_("Warehouse {0} does not belong to Branch {1}.").format(warehouse, branch))


def _validate_purchase_filters(filters: frappe._dict) -> None:
	for fieldname, label in (
		("company", _("Company")),
		("from_date", _("From Date")),
		("to_date", _("To Date")),
	):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is required.").format(label))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))
	if str(filters.get("invoice_kind") or "All") not in {"All", "Purchases", "Returns"}:
		frappe.throw(_("Invoice Type must be All, Purchases, or Returns."))


def _validate_payables_filters(filters: frappe._dict) -> None:
	for fieldname, label in (("company", _("Company")), ("as_of_date", _("As of Date"))):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is required.").format(label))
	if str(filters.get("ageing_bucket") or "All") not in {
		"All",
		"Current",
		"1-30 Days",
		"31-60 Days",
		"61-90 Days",
		"91+ Days",
	}:
		frappe.throw(_("Unsupported ageing bucket."))


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


def _export_response(dataset: dict[str, Any]) -> dict[str, Any]:
	return {
		"title": dataset.get("title") or "",
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"scan": dataset.get("scan") or {},
	}


def _purchase_register_columns(currency: str) -> list[dict[str, Any]]:
	return [
		{
			"fieldname": "invoice",
			"label": _("Purchase Invoice"),
			"fieldtype": "Link",
			"options": "Purchase Invoice",
		},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date"},
		{"fieldname": "due_date", "label": _("Due Date"), "fieldtype": "Date"},
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier"},
		{"fieldname": "supplier_name", "label": _("Supplier Name"), "fieldtype": "Data"},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data"},
		{"fieldname": "invoice_type", "label": _("Type"), "fieldtype": "Data"},
		{
			"fieldname": "transaction_currency",
			"label": _("Invoice Currency"),
			"fieldtype": "Link",
			"options": "Currency",
		},
		{"fieldname": "net_amount", "label": _("Net Amount"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "tax_amount", "label": _("Tax"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "grand_total", "label": _("Grand Total"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data"},
		{
			"fieldname": "return_against",
			"label": _("Return Against"),
			"fieldtype": "Link",
			"options": "Purchase Invoice",
		},
	]


def _supplier_payables_columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "supplier", "label": _("Supplier"), "fieldtype": "Link", "options": "Supplier"},
		{"fieldname": "supplier_name", "label": _("Supplier Name"), "fieldtype": "Data"},
		{
			"fieldname": "invoice",
			"label": _("Purchase Invoice"),
			"fieldtype": "Link",
			"options": "Purchase Invoice",
		},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data"},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date"},
		{"fieldname": "due_date", "label": _("Due Date"), "fieldtype": "Date"},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "overdue_days", "label": _("Days Overdue"), "fieldtype": "Int"},
		{"fieldname": "ageing_bucket", "label": _("Age"), "fieldtype": "Data"},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data"},
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


def _signed_for_return(value: Any, is_return: int | bool) -> float:
	amount = flt(value)
	return -abs(amount) if is_return else amount


def _outstanding_is_company_currency() -> bool:
	field = frappe.get_meta("Purchase Invoice").get_field("outstanding_amount")
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
			_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError
		)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
