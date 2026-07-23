from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, strip_html

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	get_user_allowed_branches,
	has_field,
	user_has_global_branch_access,
	validate_user_branch_access,
)

REPORT_NAME = "RetailEdge Stock Movement History"
MAX_UNSCOPED_DAYS = 366
BRANCH_PROFILE_WAREHOUSE_FIELDS = (
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	warehouse_scope = resolve_warehouse_scope(filters)
	stock_ledger_rows = get_stock_ledger_rows(filters, warehouse_scope)
	data = build_movement_rows(stock_ledger_rows, filters)
	if filters.get("movement_type"):
		data = [row for row in data if row.get("movement_type") == filters.movement_type]
	return get_columns(filters), data, None, None, get_report_summary(data)


def validate_filters(filters):
	for fieldname, label in (("company", _("Company")), ("from_date", _("From Date")), ("to_date", _("To Date"))):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is required.").format(label))

	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date."))

	if not any(filters.get(fieldname) for fieldname in ("item_code", "warehouse", "branch")):
		if (to_date - from_date).days + 1 > MAX_UNSCOPED_DAYS:
			frappe.throw(
				_("Select an Item, Warehouse or Branch for date ranges longer than {0} days.").format(
					MAX_UNSCOPED_DAYS
				)
			)


def get_columns(filters):
	compare_uom = filters.get("compare_uom")
	return [
		{"label": _("Date and Time"), "fieldname": "posting_datetime", "fieldtype": "Datetime", "width": 150},
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 135},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 190},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 95},
		{"label": _("In Quantity"), "fieldname": "in_quantity", "fieldtype": "Float", "width": 110},
		{"label": _("Out Quantity"), "fieldname": "out_quantity", "fieldtype": "Float", "width": 110},
		{
			"label": _("Compare UOM"),
			"fieldname": "compare_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 105,
			"hidden": 0 if compare_uom else 1,
		},
		{
			"label": _("Compare In Quantity"),
			"fieldname": "compare_in_quantity",
			"fieldtype": "Float",
			"width": 135,
			"hidden": 0 if compare_uom else 1,
		},
		{
			"label": _("Compare Out Quantity"),
			"fieldname": "compare_out_quantity",
			"fieldtype": "Float",
			"width": 140,
			"hidden": 0 if compare_uom else 1,
		},
		{"label": _("Source Warehouse"), "fieldname": "source_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 165},
		{"label": _("Destination Warehouse"), "fieldname": "destination_warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 165},
		{
			"label": _("Balance in Destination Warehouse"),
			"fieldname": "destination_balance",
			"fieldtype": "Float",
			"width": 190,
		},
		{
			"label": _("Destination Balance (Compare UOM)"),
			"fieldname": "destination_balance_compare",
			"fieldtype": "Float",
			"width": 190,
			"hidden": 0 if compare_uom else 1,
		},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 125},
		{
			"label": _("Voucher Number"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 155,
		},
		{"label": _("Purpose / Reference"), "fieldname": "purpose", "fieldtype": "Data", "width": 150},
		{"label": _("Batch Number"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 125},
		{"label": _("Remarks / Comment"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
	]


def resolve_warehouse_scope(filters):
	company = filters.company
	branch = filters.get("branch")
	warehouse = filters.get("warehouse")
	user = frappe.session.user
	global_access = user_has_global_branch_access(user=user)
	allowed_branches = [] if global_access else list(get_user_allowed_branches(user=user, company=company).get("branches") or [])

	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)
		branches = [branch]
	elif allowed_branches:
		branches = allowed_branches
	else:
		branches = []

	branch_warehouses = set()
	for branch_name in branches:
		branch_warehouses.update(get_branch_warehouses(company, branch_name))

	if branches and not branch_warehouses:
		frappe.throw(
			_("No warehouse scope could be resolved for the selected or permitted branch."),
			frappe.PermissionError,
		)

	if warehouse:
		warehouse_company, is_group = frappe.db.get_value("Warehouse", warehouse, ["company", "is_group"]) or (None, None)
		if warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))
		if is_group:
			frappe.throw(_("Select a non-group Warehouse."))
		if branch_warehouses and warehouse not in branch_warehouses:
			frappe.throw(
				_("Warehouse {0} is outside the selected or permitted Branch scope.").format(warehouse),
				frappe.PermissionError,
			)
		return [warehouse]

	return sorted(branch_warehouses) if branch_warehouses else None


def get_branch_warehouses(company: str, branch: str) -> set[str]:
	warehouses: set[str] = set()
	warehouse_branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	if warehouse_branch_field:
		warehouses.update(
			frappe.get_all(
				"Warehouse",
				filters={"company": company, warehouse_branch_field: branch},
				pluck="name",
				limit_page_length=0,
			)
		)

	if frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		fields = ["name"] + [
			fieldname
			for fieldname in BRANCH_PROFILE_WAREHOUSE_FIELDS
			if has_field("RetailEdge Branch Profile", fieldname)
		]
		profiles = frappe.get_all(
			"RetailEdge Branch Profile",
			filters={"company": company, "branch": branch, "enabled": 1},
			fields=fields,
			limit_page_length=0,
		)
		for profile in profiles:
			for fieldname in BRANCH_PROFILE_WAREHOUSE_FIELDS:
				if profile.get(fieldname):
					warehouses.add(profile.get(fieldname))

	return expand_group_warehouses(company, warehouses)


def expand_group_warehouses(company: str, warehouse_names: set[str]) -> set[str]:
	if not warehouse_names:
		return set()
	rows = frappe.get_all(
		"Warehouse",
		filters={"company": company, "name": ["in", sorted(warehouse_names)]},
		fields=["name", "is_group", "lft", "rgt"],
		limit_page_length=0,
	)
	resolved = {row.name for row in rows if not row.is_group}
	for row in rows:
		if not row.is_group:
			continue
		resolved.update(
			frappe.get_all(
				"Warehouse",
				filters={"company": company, "is_group": 0, "lft": [">", row.lft], "rgt": ["<", row.rgt]},
				pluck="name",
				limit_page_length=0,
			)
		)
	return resolved


def get_stock_ledger_rows(filters, warehouse_scope=None):
	query_filters: dict[str, Any] = {
		"company": filters.company,
		"posting_datetime": ["between", [f"{filters.from_date} 00:00:00", f"{filters.to_date} 23:59:59.999999"]],
		"is_cancelled": 0,
		"actual_qty": ["!=", 0],
	}
	if warehouse_scope:
		query_filters["warehouse"] = ["in", warehouse_scope]
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters.warehouse
	if filters.get("item_code"):
		query_filters["item_code"] = filters.item_code
	if filters.get("voucher_type"):
		query_filters["voucher_type"] = filters.voucher_type
	if filters.get("voucher_no"):
		query_filters["voucher_no"] = filters.voucher_no
	if filters.get("batch_no"):
		query_filters["batch_no"] = filters.batch_no

	if filters.get("item_group") and not filters.get("item_code"):
		item_codes = get_item_codes_for_group(filters.item_group)
		if not item_codes:
			return []
		query_filters["item_code"] = ["in", item_codes]

	return frappe.get_list(
		"Stock Ledger Entry",
		filters=query_filters,
		fields=[
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
		],
		order_by="posting_datetime asc, creation asc, name asc",
		limit_page_length=0,
	)


def get_item_codes_for_group(item_group: str) -> list[str]:
	bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"])
	if not bounds:
		return []
	lft, rgt = bounds
	groups = frappe.get_all(
		"Item Group",
		filters={"lft": [">=", lft], "rgt": ["<=", rgt]},
		pluck="name",
		limit_page_length=0,
	)
	return frappe.get_all(
		"Item",
		filters={"disabled": 0, "is_stock_item": 1, "item_group": ["in", groups]},
		pluck="name",
		limit_page_length=0,
	)


def build_movement_rows(stock_ledger_rows, filters):
	if not stock_ledger_rows:
		return []

	item_codes = sorted({row.item_code for row in stock_ledger_rows if row.item_code})
	item_map = {
		row.name: row
		for row in frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes]},
			fields=["name", "item_name", "stock_uom"],
			limit_page_length=0,
		)
	}
	conversion_map = get_conversion_map(item_codes, filters.get("compare_uom"))
	stock_entry_detail_map = get_stock_entry_detail_map(stock_ledger_rows)
	voucher_headers = get_voucher_headers(stock_ledger_rows)

	grouped_stock_entries = defaultdict(list)
	other_rows = []
	for sle in stock_ledger_rows:
		if sle.voucher_type == "Stock Entry" and sle.voucher_detail_no:
			grouped_stock_entries[(sle.voucher_no, sle.voucher_detail_no, sle.item_code)].append(sle)
		else:
			other_rows.append(sle)

	data = []
	for group_rows in grouped_stock_entries.values():
		data.append(
			build_stock_entry_row(
				group_rows,
				stock_entry_detail_map,
				voucher_headers.get("Stock Entry", {}),
				item_map,
				conversion_map,
				filters.get("compare_uom"),
			)
		)

	for sle in other_rows:
		data.append(
			build_single_ledger_row(
				sle,
				voucher_headers.get(sle.voucher_type, {}).get(sle.voucher_no, {}),
				item_map,
				conversion_map,
				filters.get("compare_uom"),
			)
		)

	return sorted(
		[row for row in data if row],
		key=lambda row: (
			get_datetime(row.get("posting_datetime")) if row.get("posting_datetime") else datetime.min,
			row.get("voucher_no") or "",
			row.get("item_code") or "",
		),
	)


def get_conversion_map(item_codes, compare_uom):
	if not compare_uom or not item_codes:
		return {}
	rows = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": ["in", item_codes], "parenttype": "Item", "uom": compare_uom},
		fields=["parent", "uom", "conversion_factor"],
		limit_page_length=0,
	)
	return {(row.parent, row.uom): flt(row.conversion_factor) for row in rows if flt(row.conversion_factor) > 0}


def get_stock_entry_detail_map(stock_ledger_rows):
	detail_names = sorted(
		{
			row.voucher_detail_no
			for row in stock_ledger_rows
			if row.voucher_type == "Stock Entry" and row.voucher_detail_no
		}
	)
	if not detail_names:
		return {}
	fields = [
		"name",
		"parent",
		"item_code",
		"item_name",
		"s_warehouse",
		"t_warehouse",
		"qty",
		"transfer_qty",
		"stock_uom",
		"uom",
		"conversion_factor",
	]
	for optional in ("batch_no", "serial_and_batch_bundle"):
		if has_field("Stock Entry Detail", optional):
			fields.append(optional)
	return {
		row.name: row
		for row in frappe.get_all(
			"Stock Entry Detail",
			filters={"name": ["in", detail_names]},
			fields=fields,
			limit_page_length=0,
		)
	}


def get_voucher_headers(stock_ledger_rows):
	voucher_names = defaultdict(set)
	for row in stock_ledger_rows:
		if row.voucher_type and row.voucher_no:
			voucher_names[row.voucher_type].add(row.voucher_no)

	result = {}
	for voucher_type, names in voucher_names.items():
		if not frappe.db.exists("DocType", voucher_type):
			continue
		meta = frappe.get_meta(voucher_type)
		fields = ["name"]
		for fieldname in ("purpose", "remarks", "remark", "is_return", "return_against", "title", "project"):
			if meta.has_field(fieldname):
				fields.append(fieldname)
		try:
			rows = frappe.get_list(
				voucher_type,
				filters={"name": ["in", sorted(names)]},
				fields=fields,
				limit_page_length=0,
			)
		except frappe.PermissionError:
			rows = []
		result[voucher_type] = {row.name: row for row in rows}
	return result


def build_stock_entry_row(group_rows, detail_map, header_map, item_map, conversion_map, compare_uom):
	first = group_rows[0]
	detail = detail_map.get(first.voucher_detail_no)
	header = header_map.get(first.voucher_no, {})
	item = item_map.get(first.item_code, {})
	positive = next((row for row in group_rows if flt(row.actual_qty) > 0), None)
	negative = next((row for row in group_rows if flt(row.actual_qty) < 0), None)

	source_warehouse = (detail and detail.get("s_warehouse")) or (negative and negative.warehouse)
	destination_warehouse = (detail and detail.get("t_warehouse")) or (positive and positive.warehouse)
	stock_uom = (detail and detail.get("stock_uom")) or first.get("stock_uom") or item.get("stock_uom")
	base_quantity = flt(detail.get("transfer_qty")) if detail else 0
	if not base_quantity and detail:
		base_quantity = flt(detail.get("qty")) * flt(detail.get("conversion_factor") or 1)
	if not base_quantity:
		base_quantity = max(abs(flt(row.actual_qty)) for row in group_rows)
	in_quantity, out_quantity = split_movement_quantity(
		base_quantity,
		source_warehouse=source_warehouse,
		destination_warehouse=destination_warehouse,
	)
	destination_balance = flt(positive.qty_after_transaction) if positive else None
	movement_type = classify_stock_entry_movement(header.get("purpose"), source_warehouse, destination_warehouse)
	batch_no = (detail and detail.get("batch_no")) or next((row.batch_no for row in group_rows if row.batch_no), None)
	remarks = clean_text(header.get("remarks") or header.get("remark"))
	purpose = clean_text(header.get("purpose") or header.get("title"))

	return make_output_row(
		posting_datetime=first.posting_datetime,
		movement_type=movement_type,
		item_code=first.item_code,
		item_name=(detail and detail.get("item_name")) or item.get("item_name"),
		stock_uom=stock_uom,
		in_quantity=in_quantity,
		out_quantity=out_quantity,
		compare_uom=compare_uom,
		conversion_factor=resolve_conversion_factor(first.item_code, stock_uom, compare_uom, conversion_map),
		source_warehouse=source_warehouse,
		destination_warehouse=destination_warehouse,
		destination_balance=destination_balance,
		voucher_type=first.voucher_type,
		voucher_no=first.voucher_no,
		purpose=purpose,
		batch_no=batch_no,
		remarks=remarks,
	)


def build_single_ledger_row(sle, header, item_map, conversion_map, compare_uom):
	item = item_map.get(sle.item_code, {})
	actual_qty = flt(sle.actual_qty)
	incoming = actual_qty > 0
	stock_uom = sle.get("stock_uom") or item.get("stock_uom")
	source_warehouse = None if incoming else sle.warehouse
	destination_warehouse = sle.warehouse if incoming else None
	in_quantity, out_quantity = split_movement_quantity(
		abs(actual_qty),
		source_warehouse=source_warehouse,
		destination_warehouse=destination_warehouse,
	)
	return make_output_row(
		posting_datetime=sle.posting_datetime,
		movement_type=classify_ledger_movement(sle.voucher_type, incoming, header),
		item_code=sle.item_code,
		item_name=item.get("item_name"),
		stock_uom=stock_uom,
		in_quantity=in_quantity,
		out_quantity=out_quantity,
		compare_uom=compare_uom,
		conversion_factor=resolve_conversion_factor(sle.item_code, stock_uom, compare_uom, conversion_map),
		source_warehouse=source_warehouse,
		destination_warehouse=destination_warehouse,
		destination_balance=flt(sle.qty_after_transaction) if incoming else None,
		voucher_type=sle.voucher_type,
		voucher_no=sle.voucher_no,
		purpose=clean_text(header.get("purpose") or header.get("return_against") or header.get("project")),
		batch_no=sle.batch_no,
		remarks=clean_text(header.get("remarks") or header.get("remark") or header.get("title")),
	)


def split_movement_quantity(quantity, source_warehouse=None, destination_warehouse=None):
	quantity = abs(flt(quantity))
	return (
		quantity if destination_warehouse else None,
		quantity if source_warehouse else None,
	)


def make_output_row(**values):
	factor = values.pop("conversion_factor", None)
	in_quantity = values.pop("in_quantity", None)
	out_quantity = values.pop("out_quantity", None)
	compare_uom = values.get("compare_uom")
	destination_balance = values.pop("destination_balance", None)

	compare_in_quantity = convert_quantity(in_quantity, factor) if compare_uom else None
	compare_out_quantity = convert_quantity(out_quantity, factor) if compare_uom else None
	destination_balance_compare = convert_quantity(destination_balance, factor) if compare_uom else None
	conversion_status = "Configured" if compare_uom and factor else ("Not Configured" if compare_uom else "")

	return {
		**values,
		"in_quantity": in_quantity,
		"out_quantity": out_quantity,
		"compare_in_quantity": compare_in_quantity,
		"compare_out_quantity": compare_out_quantity,
		"destination_balance": destination_balance,
		"destination_balance_compare": destination_balance_compare,
		"conversion_status": conversion_status,
	}


def resolve_conversion_factor(item_code, stock_uom, compare_uom, conversion_map):
	if not compare_uom:
		return None
	if compare_uom == stock_uom:
		return 1.0
	return conversion_map.get((item_code, compare_uom))


def convert_quantity(quantity, conversion_factor):
	if quantity is None or not conversion_factor or flt(conversion_factor) <= 0:
		return None
	return flt(quantity) / flt(conversion_factor)


def classify_stock_entry_movement(purpose, source_warehouse, destination_warehouse):
	purpose = clean_text(purpose)
	if source_warehouse and destination_warehouse:
		return "Internal Transfer"
	mapping = {
		"Material Issue": "Material Issue",
		"Material Receipt": "Material Receipt",
		"Manufacture": "Manufacture",
		"Repack": "Repack",
		"Send to Subcontractor": "Subcontract Transfer",
	}
	return mapping.get(purpose, purpose or ("Incoming" if destination_warehouse else "Outgoing"))


def classify_ledger_movement(voucher_type, incoming, header=None):
	header = header or {}
	is_return = bool(header.get("is_return"))
	if voucher_type in {"Delivery Note", "Sales Invoice"}:
		return "Sales Return" if is_return or incoming else "Sale"
	if voucher_type in {"Purchase Receipt", "Purchase Invoice"}:
		return "Purchase Return" if is_return or not incoming else "Purchase Receipt"
	if voucher_type == "Stock Reconciliation":
		return "Adjustment In" if incoming else "Adjustment Out"
	return "Incoming" if incoming else "Outgoing"


def clean_text(value):
	if not value:
		return ""
	return " ".join(strip_html(str(value)).split())


def get_report_summary(rows):
	warehouses = {
		warehouse
		for row in rows
		for warehouse in (row.get("source_warehouse"), row.get("destination_warehouse"))
		if warehouse
	}
	missing_conversions = sum(1 for row in rows if row.get("conversion_status") == "Not Configured")
	internal_transfers = sum(1 for row in rows if row.get("movement_type") == "Internal Transfer")
	return [
		{"value": len(rows), "label": _("Movement Rows"), "datatype": "Int", "indicator": "Blue"},
		{"value": len({row.get("item_code") for row in rows if row.get("item_code")}), "label": _("Distinct Items"), "datatype": "Int", "indicator": "Blue"},
		{"value": len(warehouses), "label": _("Distinct Warehouses"), "datatype": "Int", "indicator": "Blue"},
		{"value": internal_transfers, "label": _("Internal Transfers"), "datatype": "Int", "indicator": "Green"},
		{
			"value": missing_conversions,
			"label": _("Missing UOM Conversions"),
			"datatype": "Int",
			"indicator": "Orange" if missing_conversions else "Green",
		},
	]
