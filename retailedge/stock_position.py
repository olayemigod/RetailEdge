from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.branch_context import (
	get_user_allowed_branches,
	resolve_branch_from_warehouse,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.cost_visibility import should_hide_cost_price
from retailedge.retailedge.report.retailedge_stock_movement_history.retailedge_stock_movement_history import (
	get_branch_warehouses,
)
from retailedge.stock_movement_filters import branch_query, warehouse_query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_LINK_RESULTS = 20
MAX_WAREHOUSE_SCOPE = 500
MAX_BIN_SCAN_ROWS = 10000
MAX_ITEM_SCOPE = 5000

_BASE_BIN_FIELDS = (
	"item_code",
	"warehouse",
	"actual_qty",
	"reserved_qty",
	"ordered_qty",
	"projected_qty",
	"stock_uom",
)
_COST_BIN_FIELDS = ("valuation_rate", "stock_value")


@frappe.whitelist()
def get_stock_position_context() -> dict[str, Any]:
	"""Return compact defaults and cost-visibility metadata for Stock Position."""
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = ""
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

	show_costs = not should_hide_cost_price(user=user)
	return {
		"default_filters": {
			"company": company,
			"branch": branch,
			"warehouse": "",
			"item_group": "",
			"item_code": "",
			"stock_status": "All",
			"include_zero": 0,
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"company_currency": _company_currency(company) if company and show_costs else "",
		"show_costs": int(show_costs),
		"limits": {
			"warehouse_scope": MAX_WAREHOUSE_SCOPE,
			"bin_scan": MAX_BIN_SCAN_ROWS,
			"item_scope": MAX_ITEM_SCOPE,
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
		},
	}


@frappe.whitelist()
def search_stock_position_options(
	kind: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	item_group: str = "",
) -> list[dict[str, str]]:
	"""Permission-aware, bounded Link searches for Stock Position filters."""
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
			"Warehouse",
			txt,
			"name",
			0,
			MAX_LINK_RESULTS,
			{"company": company, "branch": branch},
		)
		return [{"value": row[0], "label": row[0]} for row in rows]
	if kind == "item_group":
		return _search_named("Item Group", txt)
	if kind == "item":
		filters: dict[str, Any] = {"disabled": 0, "is_stock_item": 1}
		if item_group:
			filters["item_group"] = item_group
		rows = frappe.get_list(
			"Item",
			filters=filters,
			or_filters={"name": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]},
			fields=["name", "item_name", "item_group", "stock_uom"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.item_name or row.name,
				"description": " · ".join(value for value in (row.name, row.item_group, row.stock_uom) if value),
				"item_group": row.item_group or "",
			}
			for row in rows
		]
	frappe.throw(_("Unsupported Stock Position search type."))


@frappe.whitelist()
def get_stock_position(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_stock_position_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_stock_position_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_stock_position_dataset(filters)
	return {
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"show_costs": dataset.get("show_costs") or 0,
		"scope": dataset.get("scope") or {},
		"scan": dataset.get("scan") or {},
	}


def _build_stock_position_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	warehouses = _resolve_warehouse_scope(filters)
	item_scope = _resolve_item_scope(filters)
	show_costs = not should_hide_cost_price()

	bin_filters: dict[str, Any] = {"warehouse": ["in", warehouses]}
	if filters.get("item_code"):
		bin_filters["item_code"] = filters.item_code
	elif item_scope is not None:
		if not item_scope:
			return _empty_dataset(filters, warehouses, show_costs)
		bin_filters["item_code"] = ["in", item_scope]

	fields = list(_BASE_BIN_FIELDS)
	if show_costs:
		fields.extend(_COST_BIN_FIELDS)
	bin_rows = frappe.get_list(
		"Bin",
		filters=bin_filters,
		fields=fields,
		order_by="item_code asc, warehouse asc",
		limit=MAX_BIN_SCAN_ROWS + 1,
	)
	if len(bin_rows) > MAX_BIN_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} stock position rows match this scope. Narrow the Branch, Warehouse, Item Group, or Item before loading Stock Position."
			).format(MAX_BIN_SCAN_ROWS)
		)

	item_codes = sorted({str(row.item_code) for row in bin_rows if row.item_code})
	item_map = _get_item_metadata(item_codes)
	aggregated: dict[str, dict[str, Any]] = {}
	locations: dict[str, set[str]] = defaultdict(set)
	for row in bin_rows:
		item = item_map.get(row.item_code)
		if not item:
			continue
		bucket = aggregated.setdefault(
			row.item_code,
			{
				"item_code": row.item_code,
				"item_name": item.item_name or row.item_code,
				"item_group": item.item_group or "",
				"stock_uom": row.stock_uom or item.stock_uom or "",
				"actual_qty": 0.0,
				"reserved_qty": 0.0,
				"available_qty": 0.0,
				"ordered_qty": 0.0,
				"projected_qty": 0.0,
			},
		)
		bucket["actual_qty"] += flt(row.actual_qty)
		bucket["reserved_qty"] += flt(row.reserved_qty)
		bucket["ordered_qty"] += flt(row.ordered_qty)
		bucket["projected_qty"] += flt(row.projected_qty)
		if show_costs:
			bucket["stock_value"] = flt(bucket.get("stock_value")) + flt(row.stock_value)
		locations[row.item_code].add(row.warehouse)

	rows: list[dict[str, Any]] = []
	for item_code, bucket in aggregated.items():
		bucket["available_qty"] = flt(bucket["actual_qty"]) - flt(bucket["reserved_qty"])
		bucket["location_count"] = len(locations.get(item_code) or ())
		bucket["stock_status"] = _row_stock_status(bucket)
		if show_costs:
			actual = flt(bucket["actual_qty"])
			bucket["valuation_rate"] = flt(bucket.get("stock_value")) / actual if actual else 0.0
		if not cint(filters.get("include_zero")) and not _row_has_stock_signal(bucket, show_costs=show_costs):
			continue
		if not _matches_stock_status(bucket, filters.get("stock_status")):
			continue
		rows.append(bucket)

	rows.sort(key=lambda row: (str(row.get("item_group") or ""), str(row.get("item_code") or "")))
	currency = _company_currency(filters.company) if show_costs else ""
	return {
		"columns": _columns(currency, show_costs=show_costs),
		"rows": rows,
		"summary": _summary(rows, show_costs=show_costs),
		"company_currency": currency,
		"show_costs": int(show_costs),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
		},
		"scan": {
			"bin_rows": len(bin_rows),
			"bin_limit": MAX_BIN_SCAN_ROWS,
			"warehouse_count": len(warehouses),
			"warehouse_limit": MAX_WAREHOUSE_SCOPE,
		},
	}


def _empty_dataset(filters: frappe._dict, warehouses: list[str], show_costs: bool) -> dict[str, Any]:
	currency = _company_currency(filters.company) if show_costs else ""
	return {
		"columns": _columns(currency, show_costs=show_costs),
		"rows": [],
		"summary": _summary([], show_costs=show_costs),
		"company_currency": currency,
		"show_costs": int(show_costs),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
		},
		"scan": {"bin_rows": 0, "bin_limit": MAX_BIN_SCAN_ROWS, "warehouse_count": len(warehouses)},
	}


def _resolve_warehouse_scope(filters: frappe._dict) -> list[str]:
	company = filters.company
	branch = str(filters.get("branch") or "").strip()
	warehouse = str(filters.get("warehouse") or "").strip()
	user = frappe.session.user

	if warehouse:
		_assert_named_read("Warehouse", warehouse)
		warehouse_company, is_group = frappe.db.get_value("Warehouse", warehouse, ["company", "is_group"]) or (None, None)
		if warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))
		if is_group:
			frappe.throw(_("Select a non-group Warehouse."))
		resolved_branch = resolve_branch_from_warehouse(warehouse, company=company)
		if resolved_branch:
			validate_user_branch_access(resolved_branch, user=user, company=company, throw=True)
			if branch and resolved_branch != branch:
				frappe.throw(_("Warehouse {0} does not belong to Branch {1}.").format(warehouse, branch))
		elif not user_has_global_branch_access(user=user):
			allowed_scope = _allowed_branch_warehouses(company, user=user)
			if warehouse not in allowed_scope:
				frappe.throw(_("Warehouse {0} is outside your permitted Branch scope.").format(warehouse), frappe.PermissionError)
		if branch:
			validate_user_branch_access(branch, user=user, company=company, throw=True)
			if warehouse not in get_branch_warehouses(company, branch):
				frappe.throw(_("Warehouse {0} is outside Branch {1} scope.").format(warehouse, branch), frappe.PermissionError)
		return [warehouse]

	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)
		candidate_scope = set(get_branch_warehouses(company, branch))
	else:
		candidate_scope = (
			set(_all_company_warehouses(company))
			if user_has_global_branch_access(user=user)
			else _allowed_branch_warehouses(company, user=user)
		)
	if not candidate_scope:
		frappe.throw(_("No permitted Warehouse scope could be resolved for Stock Position."), frappe.PermissionError)

	permitted = frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 0, "name": ["in", sorted(candidate_scope)]},
		pluck="name",
		order_by="name asc",
		limit=MAX_WAREHOUSE_SCOPE + 1,
	)
	if len(permitted) > MAX_WAREHOUSE_SCOPE:
		frappe.throw(_("More than {0} Warehouses are in scope. Select a Branch or Warehouse first.").format(MAX_WAREHOUSE_SCOPE))
	if not permitted:
		frappe.throw(_("You do not have permission to view any Warehouse in this scope."), frappe.PermissionError)
	return list(permitted)


def _allowed_branch_warehouses(company: str, *, user: str) -> set[str]:
	branches = list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
	if not branches:
		return set()
	warehouses: set[str] = set()
	for branch in branches:
		warehouses.update(get_branch_warehouses(company, branch))
	if len(warehouses) > MAX_WAREHOUSE_SCOPE:
		frappe.throw(_("Your permitted Branch scope contains more than {0} Warehouses. Select a Branch first.").format(MAX_WAREHOUSE_SCOPE))
	return warehouses


def _all_company_warehouses(company: str) -> list[str]:
	rows = frappe.get_list(
		"Warehouse",
		filters={"company": company, "is_group": 0},
		pluck="name",
		order_by="name asc",
		limit=MAX_WAREHOUSE_SCOPE + 1,
	)
	if len(rows) > MAX_WAREHOUSE_SCOPE:
		frappe.throw(_("Company {0} has more than {1} Warehouses. Select a Branch or Warehouse first.").format(company, MAX_WAREHOUSE_SCOPE))
	return list(rows)


def _resolve_item_scope(filters: frappe._dict) -> list[str] | None:
	if filters.get("item_code"):
		return [filters.item_code]
	item_group = str(filters.get("item_group") or "").strip()
	if not item_group:
		return None
	items = frappe.get_list(
		"Item",
		filters={"disabled": 0, "is_stock_item": 1, "item_group": item_group},
		pluck="name",
		order_by="name asc",
		limit=MAX_ITEM_SCOPE + 1,
	)
	if len(items) > MAX_ITEM_SCOPE:
		frappe.throw(_("Item Group {0} contains more than {1} stock items. Select an Item or narrower group.").format(item_group, MAX_ITEM_SCOPE))
	return list(items)


def _get_item_metadata(item_codes: list[str]) -> dict[str, frappe._dict]:
	if not item_codes:
		return {}
	rows = frappe.get_list(
		"Item",
		filters={"name": ["in", item_codes], "disabled": 0, "is_stock_item": 1},
		fields=["name", "item_name", "item_group", "stock_uom"],
		order_by="name asc",
		limit=MAX_ITEM_SCOPE + 1,
	)
	return {row.name: row for row in rows}


def _row_stock_status(row: dict[str, Any]) -> str:
	actual = flt(row.get("actual_qty"))
	available = flt(row.get("available_qty"))
	if actual < 0:
		return "Negative"
	if actual == 0:
		return "Out of Stock"
	if available <= 0:
		return "Fully Reserved"
	return "Available"


def _matches_stock_status(row: dict[str, Any], requested: Any) -> bool:
	requested = str(requested or "All").strip()
	if requested in {"", "All"}:
		return True
	if requested == "In Stock":
		return flt(row.get("actual_qty")) > 0
	return row.get("stock_status") == requested


def _row_has_stock_signal(row: dict[str, Any], *, show_costs: bool) -> bool:
	fields = ("actual_qty", "reserved_qty", "ordered_qty", "projected_qty")
	if any(flt(row.get(field)) for field in fields):
		return True
	return bool(show_costs and flt(row.get("stock_value")))


def _summary(rows: list[dict[str, Any]], *, show_costs: bool) -> list[dict[str, Any]]:
	cards = [
		{"label": _("Items in Scope"), "value": len(rows), "datatype": "Int"},
		{"label": _("Available Items"), "value": sum(1 for row in rows if flt(row.get("available_qty")) > 0), "datatype": "Int"},
		{"label": _("Out of Stock"), "value": sum(1 for row in rows if flt(row.get("actual_qty")) == 0), "datatype": "Int"},
		{"label": _("Negative Stock"), "value": sum(1 for row in rows if flt(row.get("actual_qty")) < 0), "datatype": "Int"},
		{"label": _("Fully Reserved"), "value": sum(1 for row in rows if flt(row.get("actual_qty")) > 0 and flt(row.get("available_qty")) <= 0), "datatype": "Int"},
	]
	if show_costs:
		cards.append({"label": _("Stock Value"), "value": sum(flt(row.get("stock_value")) for row in rows), "datatype": "Currency"})
	return cards


def _columns(currency: str, *, show_costs: bool) -> list[dict[str, Any]]:
	columns = [
		{"fieldname": "item_code", "label": _("Item Code"), "fieldtype": "Link", "options": "Item"},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data"},
		{"fieldname": "item_group", "label": _("Item Group"), "fieldtype": "Link", "options": "Item Group"},
		{"fieldname": "stock_uom", "label": _("UOM"), "fieldtype": "Link", "options": "UOM"},
		{"fieldname": "actual_qty", "label": _("On Hand"), "fieldtype": "Float"},
		{"fieldname": "reserved_qty", "label": _("Reserved for Sale"), "fieldtype": "Float"},
		{"fieldname": "available_qty", "label": _("Available to Sell"), "fieldtype": "Float"},
		{"fieldname": "ordered_qty", "label": _("Ordered Qty"), "fieldtype": "Float"},
		{"fieldname": "projected_qty", "label": _("Projected Qty"), "fieldtype": "Float"},
		{"fieldname": "stock_status", "label": _("Stock Status"), "fieldtype": "Data"},
	]
	if show_costs:
		columns.extend(
			[
				{"fieldname": "valuation_rate", "label": _("Valuation Rate"), "fieldtype": "Currency", "options": currency},
				{"fieldname": "stock_value", "label": _("Stock Value"), "fieldtype": "Currency", "options": currency},
			]
		)
	return columns


def _assert_report_access(filters: frappe._dict) -> None:
	_assert_named_read("Company", filters.company)
	if not frappe.has_permission("Bin", "read"):
		frappe.throw(_("You do not have permission to view current stock quantities."), frappe.PermissionError)
	for doctype, fieldname in (("Item Group", "item_group"), ("Item", "item_code")):
		if filters.get(fieldname):
			_assert_named_read(doctype, filters.get(fieldname))
	if filters.get("branch"):
		validate_user_branch_access(filters.branch, user=frappe.session.user, company=filters.company, throw=True)


def _assert_named_read(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is required."))
	status = str(filters.get("stock_status") or "All").strip()
	if status not in {"All", "In Stock", "Available", "Out of Stock", "Negative", "Fully Reserved"}:
		frappe.throw(_("Unsupported Stock Status filter."))


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


def _search_named(doctype: str, txt: str) -> list[dict[str, str]]:
	rows = frappe.get_list(
		doctype,
		filters={"name": ["like", f"%{txt}%"]},
		fields=["name"],
		order_by="name asc",
		limit=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _company_currency(company: str) -> str:
	return str(frappe.get_cached_value("Company", company, "default_currency") or "") if company else ""


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})


def _page_size(value: Any) -> int:
	resolved = cint(value) or DEFAULT_PAGE_SIZE
	return max(25, min(resolved, MAX_PAGE_SIZE))
