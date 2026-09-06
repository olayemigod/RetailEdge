from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

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
MAX_SALES_TEAM_ROWS = 5000
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
		"branch": branch,
		"customer": "",
		"item_code": "",
		"item_group": "",
		"salesperson": "",
		"warehouse": "",
		"status": "",
		"invoice_kind": "All",
		"page_size": DEFAULT_PAGE_SIZE,
	}


@frappe.whitelist()
def get_sales_reporting_context() -> dict[str, Any]:
	"""Return compact defaults shared by RetailEdge sales reporting pages."""
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
def search_sales_reporting_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	item_group: str = "",
) -> list[dict[str, str]]:
	"""Permission-aware, bounded Link searches for Sales reporting pages."""
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()
	item_group = str(item_group or "").strip()

	if kind == "branch":
		rows = branch_query("Branch", txt, "name", 0, MAX_LINK_RESULTS, {"company": company})
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "warehouse":
		rows = warehouse_query(
			"Warehouse",
			txt,
			"name",
			0,
			MAX_LINK_RESULTS,
			{"company": company, "branch": branch},
		)
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "company":
		return _search_named("Company", txt)
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
	if kind == "salesperson":
		return _search_named("Sales Person", txt)
	frappe.throw(_("Unsupported Sales reporting search type."))


@frappe.whitelist()
def get_sales_by_item(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_sales_by_item_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_sales_by_item_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_sales_by_item_dataset(filters)
	return _export_response(dataset)


@frappe.whitelist()
def get_sales_invoice_register(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_sales_invoice_register_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_sales_invoice_register_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_sales_invoice_register_dataset(filters)
	return _export_response(dataset)


def _build_sales_by_item_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters)
	headers = _filter_headers_by_salesperson(headers, filters.get("salesperson"))
	header_map = {row.name: row for row in headers}
	items = _get_invoice_items(list(header_map), filters)

	aggregated: dict[str, dict[str, Any]] = {}
	for row in items:
		header = header_map.get(row.parent)
		if not header:
			continue
		item_code = row.item_code
		bucket = aggregated.setdefault(
			item_code,
			{
				"item_code": item_code,
				"item_name": row.item_name or item_code,
				"item_group": row.item_group or "",
				"stock_uom": row.stock_uom or "",
				"sold_qty": 0.0,
				"returned_qty": 0.0,
				"net_qty": 0.0,
				"sales_value": 0.0,
				"returns_value": 0.0,
				"net_sales": 0.0,
				"_invoices": set(),
			},
		)
		qty = flt(row.qty)
		value = flt(row.base_net_amount)
		is_return = cint(header.is_return)
		if is_return:
			bucket["returned_qty"] += abs(qty)
			bucket["returns_value"] += abs(value)
			bucket["net_qty"] -= abs(qty)
			bucket["net_sales"] -= abs(value)
		else:
			bucket["sold_qty"] += max(qty, 0)
			bucket["sales_value"] += value
			bucket["net_qty"] += qty
			bucket["net_sales"] += value
		bucket["_invoices"].add(row.parent)

	rows: list[dict[str, Any]] = []
	for bucket in aggregated.values():
		net_qty = flt(bucket["net_qty"])
		bucket["invoice_count"] = len(bucket.pop("_invoices"))
		bucket["average_selling_price"] = flt(bucket["net_sales"]) / net_qty if net_qty else 0.0
		rows.append(bucket)
	rows.sort(key=lambda row: (-flt(row.get("net_sales")), str(row.get("item_code") or "")))

	currency = _company_currency(filters.company)
	summary = [
		{
			"label": _("Net Sales"),
			"value": sum(flt(row["net_sales"]) for row in rows),
			"datatype": "Currency",
		},
		{
			"label": _("Sold Quantity"),
			"value": sum(flt(row["sold_qty"]) for row in rows),
			"datatype": "Float",
		},
		{
			"label": _("Returned Quantity"),
			"value": sum(flt(row["returned_qty"]) for row in rows),
			"datatype": "Float",
		},
		{"label": _("Net Quantity"), "value": sum(flt(row["net_qty"]) for row in rows), "datatype": "Float"},
		{"label": _("Items"), "value": len(rows), "datatype": "Int"},
	]
	return {
		"columns": _sales_by_item_columns(currency),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"scan": {
			"invoices": len(headers),
			"item_rows": len(items),
			"invoice_limit": MAX_INVOICE_SCAN_ROWS,
			"item_limit": MAX_ITEM_SCAN_ROWS,
		},
	}


def _build_sales_invoice_register_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	headers = _get_permitted_invoice_headers(filters)
	headers = _filter_headers_by_salesperson(headers, filters.get("salesperson"))

	if any(filters.get(field) for field in ("item_code", "item_group", "warehouse")):
		matching_items = _get_invoice_items([row.name for row in headers], filters)
		matching_parents = {row.parent for row in matching_items}
		headers = [row for row in headers if row.name in matching_parents]

	team_map = _salespeople_by_invoice([row.name for row in headers])
	currency = _company_currency(filters.company)
	outstanding_is_base = _outstanding_is_company_currency()
	rows = []
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
				"customer": row.customer,
				"customer_name": row.customer_name or row.customer,
				"branch": row.get("branch") or "",
				"salespeople": ", ".join(team_map.get(row.name, [])),
				"invoice_type": _("Return") if is_return else _("Sale"),
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
			"label": _("Net Invoiced"),
			"value": sum(flt(row["grand_total"]) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Invoices"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Returns"),
			"value": sum(abs(flt(row["grand_total"])) for row in returns),
			"datatype": "Currency",
		},
		{"label": _("Return Count"), "value": len(returns), "datatype": "Int"},
		{
			"label": _("Net Outstanding"),
			"value": sum(flt(row["outstanding"]) for row in rows),
			"datatype": "Currency",
		},
	]
	return {
		"columns": _invoice_register_columns(currency),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"scan": {"invoices": len(headers), "invoice_limit": MAX_INVOICE_SCAN_ROWS},
	}


def _get_permitted_invoice_headers(filters: frappe._dict) -> list[frappe._dict]:
	branch_field, branch_condition = _invoice_branch_scope(filters)
	query_filters: dict[str, Any] = {
		"docstatus": 1,
		"company": filters.company,
		"posting_date": ["between", [filters.from_date, filters.to_date]],
	}
	if filters.get("customer"):
		query_filters["customer"] = filters.customer
	if filters.get("status"):
		query_filters["status"] = filters.status
	invoice_kind = str(filters.get("invoice_kind") or "All").strip()
	if invoice_kind == "Sales":
		query_filters["is_return"] = 0
	elif invoice_kind == "Returns":
		query_filters["is_return"] = 1
	if branch_field and branch_condition is not None:
		query_filters[branch_field] = branch_condition

	fields = [
		"name",
		"posting_date",
		"customer",
		"customer_name",
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
		"Sales Invoice",
		filters=query_filters,
		fields=fields,
		order_by="posting_date desc, name desc",
		limit=MAX_INVOICE_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_INVOICE_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} submitted Sales Invoices match these filters. Narrow the date range or add filters before loading this report."
			).format(MAX_INVOICE_SCAN_ROWS)
		)
	for row in rows:
		row["branch"] = row.get(branch_field) if branch_field else ""
	return rows


def _get_invoice_items(invoice_names: list[str], filters: frappe._dict) -> list[frappe._dict]:
	if not invoice_names:
		return []
	query_filters: dict[str, Any] = {
		"parenttype": "Sales Invoice",
		"parent": ["in", invoice_names],
	}
	if filters.get("item_code"):
		query_filters["item_code"] = filters.item_code
	if filters.get("item_group"):
		query_filters["item_group"] = filters.item_group
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters.warehouse
	rows = frappe.get_all(
		"Sales Invoice Item",
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
				"More than {0} Sales Invoice item rows match these filters. Narrow the date range, Item, Item Group, Branch, or Warehouse before loading this report."
			).format(MAX_ITEM_SCAN_ROWS)
		)
	return rows


def _filter_headers_by_salesperson(
	headers: list[frappe._dict], salesperson: str | None
) -> list[frappe._dict]:
	salesperson = str(salesperson or "").strip()
	if not salesperson or not headers:
		return headers
	rows = frappe.get_all(
		"Sales Team",
		filters={
			"parenttype": "Sales Invoice",
			"parent": ["in", [row.name for row in headers]],
			"sales_person": salesperson,
		},
		fields=["parent"],
		limit=MAX_SALES_TEAM_ROWS + 1,
	)
	if len(rows) > MAX_SALES_TEAM_ROWS:
		frappe.throw(_("Salesperson filter matched too many Sales Team rows. Narrow the date range."))
	parents = {row.parent for row in rows}
	return [row for row in headers if row.name in parents]


def _salespeople_by_invoice(invoice_names: list[str]) -> dict[str, list[str]]:
	if not invoice_names:
		return {}
	rows = frappe.get_all(
		"Sales Team",
		filters={"parenttype": "Sales Invoice", "parent": ["in", invoice_names]},
		fields=["parent", "sales_person", "idx"],
		order_by="parent asc, idx asc",
		limit=MAX_SALES_TEAM_ROWS + 1,
	)
	if len(rows) > MAX_SALES_TEAM_ROWS:
		frappe.throw(_("Too many Sales Team rows match this report. Narrow the date range."))
	result: dict[str, list[str]] = defaultdict(list)
	for row in rows:
		if row.sales_person and row.sales_person not in result[row.parent]:
			result[row.parent].append(row.sales_person)
	return dict(result)


def _invoice_branch_scope(filters: frappe._dict) -> tuple[str | None, Any]:
	fieldname = _sales_invoice_branch_field()
	branch = str(filters.get("branch") or "").strip()
	user = frappe.session.user
	scope = get_operational_branch_scope(filters.company, user=user)
	restricted = bool(scope.get("restricted"))
	allowed = _allowed_scope_branches(scope)
	if branch:
		_validate_sales_branch(
			company=filters.company,
			branch=branch,
			user=user,
			scope=scope,
		)
		if not fieldname:
			frappe.throw(
				_(
					"Sales Invoice branch attribution is unavailable; this Branch filter cannot be applied safely."
				)
			)
		return fieldname, branch
	if not restricted:
		return fieldname, None
	if not fieldname:
		frappe.throw(
			_(
				"Sales Invoice branch attribution is unavailable; branch-restricted reporting cannot be applied safely."
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
			_validate_sales_branch(
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


def _validate_sales_branch(
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
	for doctype, fieldname in (
		("Customer", "customer"),
		("Item", "item_code"),
		("Item Group", "item_group"),
		("Sales Person", "salesperson"),
		("Warehouse", "warehouse"),
	):
		if filters.get(fieldname):
			_assert_named_read(doctype, filters.get(fieldname))
	branch = str(filters.get("branch") or "").strip()
	if branch:
		_validate_sales_branch(
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
			_validate_sales_branch(
				company=filters.company,
				branch=resolved_branch,
				user=frappe.session.user,
			)
			if branch and resolved_branch != branch:
				frappe.throw(_("Warehouse {0} does not belong to Branch {1}.").format(warehouse, branch))
		elif branch:
			rows = warehouse_query(
				"Warehouse",
				warehouse,
				"name",
				0,
				MAX_LINK_RESULTS,
				{"company": filters.company, "branch": branch},
			)
			if not any(row and row[0] == warehouse for row in rows):
				frappe.throw(
					_("Warehouse {0} is outside Branch {1} scope.").format(warehouse, branch),
					frappe.PermissionError,
				)


def _assert_named_read(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError
		)


def _validate_filters(filters: frappe._dict) -> None:
	for fieldname, label in (
		("company", _("Company")),
		("from_date", _("From Date")),
		("to_date", _("To Date")),
	):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is required.").format(label))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))
	invoice_kind = str(filters.get("invoice_kind") or "All").strip()
	if invoice_kind not in {"All", "Sales", "Returns"}:
		frappe.throw(_("Invoice Type must be All, Sales, or Returns."))


def _page_response(dataset: dict[str, Any], *, page: int | str, page_size: int | str) -> dict[str, Any]:
	rows = list(dataset.get("rows") or [])
	resolved_page_size = _page_size(page_size)
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


def _export_response(dataset: dict[str, Any]) -> dict[str, Any]:
	return {
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"scan": dataset.get("scan") or {},
	}


def _sales_by_item_columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item"},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data"},
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group"},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM"},
		{"fieldname": "sold_qty", "label": _("Sold Qty"), "fieldtype": "Float"},
		{"fieldname": "returned_qty", "label": _("Returned Qty"), "fieldtype": "Float"},
		{"fieldname": "net_qty", "label": _("Net Qty"), "fieldtype": "Float"},
		{"fieldname": "sales_value", "label": _("Sales Value"), "fieldtype": "Currency", "options": currency},
		{
			"fieldname": "returns_value",
			"label": _("Returns Value"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{"fieldname": "net_sales", "label": _("Net Sales"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "invoice_count", "label": _("Invoices"), "fieldtype": "Int"},
		{
			"fieldname": "average_selling_price",
			"label": _("Avg Selling Price"),
			"fieldtype": "Currency",
			"options": currency,
		},
	]


def _invoice_register_columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "invoice", "label": _("Invoice"), "fieldtype": "Link", "options": "Sales Invoice"},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date"},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer"},
		{"fieldname": "customer_name", "label": _("Customer Name"), "fieldtype": "Data"},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data"},
		{"fieldname": "salespeople", "label": _("Salespeople"), "fieldtype": "Data"},
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
			"options": "Sales Invoice",
		},
	]


def _signed_for_return(value: Any, is_return: int | bool) -> float:
	amount = flt(value)
	return -abs(amount) if is_return else amount


def _outstanding_is_company_currency() -> bool:
	field = frappe.get_meta("Sales Invoice").get_field("outstanding_amount")
	options = str(getattr(field, "options", "") or "")
	return options.startswith("Company:") or "company:default_currency" in options.lower()


def _company_currency(company: str) -> str:
	if not company:
		return ""
	return str(frappe.get_cached_value("Company", company, "default_currency") or "")


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


def _page_size(value: Any) -> int:
	resolved = cint(value) or DEFAULT_PAGE_SIZE
	return max(25, min(resolved, MAX_PAGE_SIZE))
