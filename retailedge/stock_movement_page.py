from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from retailedge.branch_context import (
	get_user_allowed_branches,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.guided_entry_context import resolve_branch_warehouse_selection
from retailedge.retailedge.report.retailedge_stock_movement_history.retailedge_stock_movement_history import (
	apply_display_filters,
	build_movement_rows,
	build_opening_balance_row,
	get_columns,
	get_conversion_map,
	get_item_details,
	get_opening_balance,
	get_report_summary,
	resolve_warehouse_scope,
	split_opening_stock_reconciliations,
	validate_filters,
)
from retailedge.stock_movement_filters import branch_query, warehouse_query

MAX_SCAN_ROWS = 1000
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_LINK_RESULTS = 20

_STOCK_LEDGER_FIELDS = (
	"name",
	"posting_datetime",
	"posting_date",
	"posting_time",
	"item_code",
	"warehouse",
	"actual_qty",
	"qty_after_transaction",
	"voucher_type",
	"voucher_no",
	"voucher_detail_no",
	"batch_no",
	"serial_no",
	"stock_uom",
	"creation",
)

_PUBLIC_ROW_FIELDS = (
	"posting_datetime",
	"movement_type",
	"item_code",
	"item_name",
	"stock_uom",
	"in_quantity",
	"out_quantity",
	"balance",
	"compare_uom",
	"compare_in_quantity",
	"compare_out_quantity",
	"compare_balance",
	"conversion_status",
	"source_warehouse",
	"destination_warehouse",
	"voucher_type",
	"voucher_no",
	"voucher_detail_no",
	"purpose",
	"batch_no",
	"remarks",
	"is_opening_row",
)


@frappe.whitelist()
def get_stock_movement_page_context() -> dict[str, Any]:
	"""Return compact defaults for the EdgeSuite Stock Movement page."""
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = ""
	warehouse = ""

	if company and frappe.has_permission("Company", "read", doc=company):
		candidate = str(
			frappe.defaults.get_user_default("RetailEdge Branch")
			or frappe.defaults.get_user_default("Branch")
			or ""
		).strip()
		if candidate:
			try:
				validate_user_branch_access(candidate, user=user, company=company, throw=True)
				branch = candidate
			except (frappe.PermissionError, frappe.ValidationError):
				branch = ""

		if not branch and not user_has_global_branch_access(user=user):
			allowed = list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
			if len(allowed) == 1:
				branch = allowed[0]

		if branch:
			resolved = resolve_branch_warehouse_selection(
				company=company,
				branch=branch,
				warehouse="",
				preference="default",
			)
			warehouse = str(resolved.get("warehouse") or "").strip()

	user_name = frappe.db.get_value("User", user, "full_name") or user
	today = nowdate()
	return {
		"default_filters": {
			"company": company,
			"from_date": f"{today[:7]}-01",
			"to_date": today,
			"item_code": "",
			"branch": branch,
			"warehouse": warehouse,
			"compare_uom": "",
			"movement_type": "",
			"voucher_type": "",
			"voucher_no": "",
			"batch_no": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": user_name,
		"scan_limit": MAX_SCAN_ROWS,
		"max_page_size": MAX_PAGE_SIZE,
	}


@frappe.whitelist()
def get_stock_movement_page(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	"""Return an accounting-safe, bounded and paginated stock movement slice.

	The established RetailEdge report functions remain the calculation source of
	truth. This API only bounds the Stock Ledger scan and slices the final payload.
	If the selected period exceeds the safe scan cap, the user must narrow filters;
	we never return a silently incomplete stock history.
	"""
	filters = _coerce_filters(filters)
	validate_filters(filters)
	_assert_report_access(filters)
	warehouse_scope = resolve_warehouse_scope(filters)

	item = get_item_details(filters.item_code)
	conversion_map = get_conversion_map([filters.item_code], filters.get("compare_uom"))
	opening_balance = get_opening_balance(filters, warehouse_scope)
	stock_ledger_rows = _get_bounded_stock_ledger_rows(filters)

	opening_balance, stock_ledger_rows, opening_context = split_opening_stock_reconciliations(
		filters,
		stock_ledger_rows,
		opening_balance,
	)
	movement_rows = build_movement_rows(
		stock_ledger_rows,
		filters,
		warehouse_scope,
		item=item,
		conversion_map=conversion_map,
		opening_balance=opening_balance,
	)
	movement_rows = apply_display_filters(movement_rows, filters)
	data = [
		build_opening_balance_row(
			filters,
			item=item,
			conversion_map=conversion_map,
			opening_balance=opening_balance,
			opening_context=opening_context,
		),
		*movement_rows,
	]

	resolved_page_size = _page_size(page_size)
	resolved_page = max(cint(page), 1)
	total_rows = len(data)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	resolved_page = min(resolved_page, total_pages)
	start = (resolved_page - 1) * resolved_page_size
	end = start + resolved_page_size

	return {
		"columns": get_columns(filters),
		"rows": [_public_row(row) for row in data[start:end]],
		"summary": get_report_summary(data),
		"pagination": {
			"page": resolved_page,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": resolved_page > 1,
			"has_next": resolved_page < total_pages,
		},
		"scan": {
			"ledger_rows": len(stock_ledger_rows),
			"limit": MAX_SCAN_ROWS,
		},
	}


@frappe.whitelist()
def search_stock_movement_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	item_code: str = "",
) -> list[dict[str, str]]:
	"""Permission-aware, bounded searches for EdgeSuite Link fields."""
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(branch or "").strip()
	item_code = str(item_code or "").strip()

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
		return _search_named_doctype("Company", txt)
	if kind == "uom":
		return _search_named_doctype("UOM", txt)
	if kind == "item":
		rows = frappe.get_list(
			"Item",
			filters={"disabled": 0, "is_stock_item": 1},
			or_filters={"name": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]},
			fields=["name", "item_name", "stock_uom"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.item_name or row.name,
				"description": " · ".join(value for value in (row.name, row.stock_uom) if value),
			}
			for row in rows
		]
	if kind == "batch":
		query_filters: dict[str, Any] = {"name": ["like", f"%{txt}%"]}
		if item_code:
			query_filters["item"] = item_code
		rows = frappe.get_list(
			"Batch",
			filters=query_filters,
			fields=["name", "item"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{"value": row.name, "label": row.name, "description": row.item or ""}
			for row in rows
		]
	frappe.throw(_("Unsupported Stock Movement search type."))


def _get_bounded_stock_ledger_rows(filters: frappe._dict) -> list[frappe._dict]:
	raw_rows = frappe.get_list(
		"Stock Ledger Entry",
		filters={
			"company": filters.company,
			"item_code": filters.item_code,
			"warehouse": filters.warehouse,
			"posting_datetime": [
				"between",
				[f"{filters.from_date} 00:00:00", f"{filters.to_date} 23:59:59.999999"],
			],
			"is_cancelled": 0,
		},
		fields=list(_STOCK_LEDGER_FIELDS),
		order_by="posting_datetime asc, creation asc, name asc",
		limit=MAX_SCAN_ROWS + 1,
	)
	if len(raw_rows) > MAX_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} stock ledger rows match these filters. "
				"Narrow the date range before loading Stock Movement History."
			).format(MAX_SCAN_ROWS)
		)
	return [
		row
		for row in raw_rows
		if flt(row.actual_qty) or row.voucher_type == "Stock Reconciliation"
	]


def _assert_report_access(filters: frappe._dict) -> None:
	for doctype, name in (
		("Company", filters.company),
		("Item", filters.item_code),
		("Warehouse", filters.warehouse),
	):
		if not frappe.db.exists(doctype, name):
			frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
		if not frappe.has_permission(doctype, "read", doc=name):
			frappe.throw(
				_("You do not have permission to use {0} {1}.").format(doctype, name),
				frappe.PermissionError,
			)
	if not frappe.has_permission("Stock Ledger Entry", "read"):
		frappe.throw(
			_("You do not have permission to view stock ledger movements."),
			frappe.PermissionError,
		)


def _search_named_doctype(doctype: str, txt: str) -> list[dict[str, str]]:
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
	return max(10, min(resolved, MAX_PAGE_SIZE))


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
	return {fieldname: row.get(fieldname) for fieldname in _PUBLIC_ROW_FIELDS}
