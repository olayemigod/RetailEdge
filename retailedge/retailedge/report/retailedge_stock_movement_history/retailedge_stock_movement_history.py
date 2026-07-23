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
	data = build_movement_rows(stock_ledger_rows, filters, warehouse_scope)
	data = apply_display_filters(data, filters)
	return get_columns(filters), data, None, None, get_report_summary(data)


def validate_filters(filters):
	for fieldname, label in (
		("company", _("Company")),
		("from_date", _("From Date")),
		("to_date", _("To Date")),
		("item_code", _("Item")),
		("warehouse", _("Warehouse")),
	):
		if not filters.get(fieldname):
			frappe.throw(_("{0} is required.").format(label))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


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
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Float", "width": 110},
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
		{
			"label": _("Compare Balance"),
			"fieldname": "compare_balance",
			"fieldtype": "Float",
			"width": 125,
			"hidden": 0 if compare_uom else 1,
		},
		{
			"label": _("Source Warehouse"),
			"fieldname": "source_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 165,
		},
		{
			"label": _("Destination Warehouse"),
			"fieldname": "destination_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 165,
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
	"""Validate the required warehouse and return its exact authoritative scope."""
	company = filters.company
	branch = filters.get("branch")
	warehouse = filters.warehouse
	user = frappe.session.user
	global_access = user_has_global_branch_access(user=user)
	allowed_branches = (
		[]
		if global_access
		else list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
	)

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

	warehouse_company, is_group = frappe.db.get_value(
		"Warehouse",
		warehouse,
		["company", "is_group"],
	) or (None, None)
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
				filters={
					"company": company,
					"is_group": 0,
					"lft": [">", row.lft],
					"rgt": ["<", row.rgt],
				},
				pluck="name",
				limit_page_length=0,
			)
		)
	return resolved


def get_stock_ledger_rows(filters, warehouse_scope=None):
	"""Fetch every selected-item movement for the required warehouse."""
	query_filters: dict[str, Any] = {
		"company": filters.company,
		"item_code": filters.item_code,
		"warehouse": filters.warehouse,
		"posting_datetime": [
			"between",
			[f"{filters.from_date} 00:00:00", f"{filters.to_date} 23:59:59.999999"],
		],
		"is_cancelled": 0,
		"actual_qty": ["!=", 0],
	}

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


def build_movement_rows(stock_ledger_rows, filters, warehouse_scope=None):
	if not stock_ledger_rows:
		return []

	item_code = filters.item_code
	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_name", "stock_uom"],
		as_dict=True,
	) or frappe._dict()
	conversion_map = get_conversion_map([item_code], filters.get("compare_uom"))
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
		row = build_stock_entry_movement_row(
			group_rows,
			detail_map=stock_entry_detail_map,
			header_map=voucher_headers.get("Stock Entry", {}),
			item=item,
			conversion_map=conversion_map,
			compare_uom=filters.get("compare_uom"),
		)
		if row:
			data.append(row)

	for sle in other_rows:
		data.append(
			build_single_movement_row(
				sle,
				header=voucher_headers.get(sle.voucher_type, {}).get(sle.voucher_no, {}),
				item=item,
				conversion_map=conversion_map,
				compare_uom=filters.get("compare_uom"),
			)
		)

	data = sorted(
		[row for row in data if row],
		key=lambda row: (
			get_datetime(row.get("posting_datetime")) if row.get("posting_datetime") else datetime.min,
			get_datetime(row.get("creation")) if row.get("creation") else datetime.min,
			row.get("sort_key") or "",
		),
	)
	opening_balance = get_opening_balance(filters, warehouse_scope)
	return apply_running_balances(data, opening_balance)


def get_conversion_map(item_codes, compare_uom):
	if not compare_uom or not item_codes:
		return {}

	rows = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": ["in", item_codes], "parenttype": "Item", "uom": compare_uom},
		fields=["parent", "uom", "conversion_factor"],
		limit_page_length=0,
	)
	return {
		(row.parent, row.uom): flt(row.conversion_factor)
		for row in rows
		if flt(row.conversion_factor) > 0
	}


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
		for fieldname in (
			"purpose",
			"remarks",
			"remark",
			"is_return",
			"return_against",
			"title",
			"project",
		):
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


def build_stock_entry_movement_row(
	group_rows,
	detail_map,
	header_map,
	item,
	conversion_map,
	compare_uom,
):
	first = min(
		group_rows,
		key=lambda row: (
			get_datetime(row.posting_datetime),
			get_datetime(row.creation),
			row.name,
		),
	)
	detail = detail_map.get(first.voucher_detail_no)
	header = header_map.get(first.voucher_no, {})
	positive_qty = sum(flt(row.actual_qty) for row in group_rows if flt(row.actual_qty) > 0)
	negative_qty = abs(sum(flt(row.actual_qty) for row in group_rows if flt(row.actual_qty) < 0))

	source_warehouse = (detail and detail.get("s_warehouse")) or next(
		(row.warehouse for row in group_rows if flt(row.actual_qty) < 0),
		None,
	)
	destination_warehouse = (detail and detail.get("t_warehouse")) or next(
		(row.warehouse for row in group_rows if flt(row.actual_qty) > 0),
		None,
	)
	stock_uom = (detail and detail.get("stock_uom")) or first.get("stock_uom") or item.get("stock_uom")
	factor = resolve_conversion_factor(first.item_code, stock_uom, compare_uom, conversion_map)
	batch_numbers = sorted({row.get("batch_no") for row in group_rows if row.get("batch_no")})

	return make_output_row(
		sort_key="|".join(sorted(row.name for row in group_rows)),
		creation=min(row.creation for row in group_rows),
		posting_datetime=first.posting_datetime,
		movement_type=classify_stock_entry_movement(
			header.get("purpose"),
			source_warehouse,
			destination_warehouse,
		),
		item_code=first.item_code,
		item_name=(detail and detail.get("item_name")) or item.get("item_name"),
		stock_uom=stock_uom,
		in_quantity=positive_qty or None,
		out_quantity=negative_qty or None,
		balance=None,
		compare_uom=compare_uom,
		conversion_factor=factor,
		source_warehouse=source_warehouse,
		destination_warehouse=destination_warehouse,
		voucher_type=first.voucher_type,
		voucher_no=first.voucher_no,
		voucher_detail_no=first.voucher_detail_no,
		purpose=clean_text(header.get("purpose") or header.get("title")),
		batch_no=batch_numbers[0] if len(batch_numbers) == 1 else "",
		batch_numbers=batch_numbers,
		remarks=clean_text(header.get("remarks") or header.get("remark")),
	)


def build_single_movement_row(sle, header, item, conversion_map, compare_uom):
	actual_qty = flt(sle.actual_qty)
	incoming = actual_qty > 0
	stock_uom = sle.get("stock_uom") or item.get("stock_uom")
	factor = resolve_conversion_factor(sle.item_code, stock_uom, compare_uom, conversion_map)

	return make_output_row(
		sort_key=sle.name,
		creation=sle.creation,
		posting_datetime=sle.posting_datetime,
		movement_type=classify_ledger_movement(sle.voucher_type, incoming, header),
		item_code=sle.item_code,
		item_name=item.get("item_name"),
		stock_uom=stock_uom,
		in_quantity=actual_qty if incoming else None,
		out_quantity=abs(actual_qty) if not incoming else None,
		balance=None,
		compare_uom=compare_uom,
		conversion_factor=factor,
		source_warehouse=None if incoming else sle.warehouse,
		destination_warehouse=sle.warehouse if incoming else None,
		voucher_type=sle.voucher_type,
		voucher_no=sle.voucher_no,
		voucher_detail_no=sle.voucher_detail_no,
		purpose=clean_text(
			header.get("purpose")
			or header.get("return_against")
			or header.get("project")
			or header.get("title")
		),
		batch_no=sle.get("batch_no"),
		batch_numbers=[sle.get("batch_no")] if sle.get("batch_no") else [],
		remarks=clean_text(header.get("remarks") or header.get("remark")),
	)


def get_opening_balance(filters, warehouse_scope=None):
	"""Return stock immediately before From Date for one Item and Warehouse."""
	rows = frappe.get_list(
		"Stock Ledger Entry",
		filters={
			"company": filters.company,
			"item_code": filters.item_code,
			"warehouse": filters.warehouse,
			"posting_datetime": ["<", f"{filters.from_date} 00:00:00"],
			"is_cancelled": 0,
		},
		fields=[{"SUM": "actual_qty", "as": "opening_balance"}],
		limit_page_length=1,
	)
	return flt(rows[0].opening_balance) if rows else 0.0


def apply_running_balances(rows, opening_balance=0):
	balance = flt(opening_balance)
	for row in rows:
		balance = balance - flt(row.get("out_quantity")) + flt(row.get("in_quantity"))
		row["balance"] = balance
		row["compare_balance"] = (
			convert_quantity(balance, row.get("_conversion_factor"))
			if row.get("compare_uom")
			else None
		)
	return rows


def apply_display_filters(rows, filters):
	filtered = rows
	for fieldname in ("voucher_type", "voucher_no", "movement_type"):
		if filters.get(fieldname):
			filtered = [row for row in filtered if row.get(fieldname) == filters.get(fieldname)]

	if filters.get("batch_no"):
		filtered = [
			row
			for row in filtered
			if filters.batch_no in (row.get("batch_numbers") or [])
			or row.get("batch_no") == filters.batch_no
		]
	return filtered


def make_output_row(**values):
	factor = values.pop("conversion_factor", None)
	in_quantity = values.pop("in_quantity", None)
	out_quantity = values.pop("out_quantity", None)
	balance = values.pop("balance", None)
	compare_uom = values.get("compare_uom")

	compare_in_quantity = convert_quantity(in_quantity, factor) if compare_uom else None
	compare_out_quantity = convert_quantity(out_quantity, factor) if compare_uom else None
	compare_balance = convert_quantity(balance, factor) if compare_uom else None
	conversion_status = "Configured" if compare_uom and factor else ("Not Configured" if compare_uom else "")

	return {
		**values,
		"in_quantity": in_quantity,
		"out_quantity": out_quantity,
		"balance": balance,
		"compare_in_quantity": compare_in_quantity,
		"compare_out_quantity": compare_out_quantity,
		"compare_balance": compare_balance,
		"conversion_status": conversion_status,
		"_conversion_factor": factor,
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
	sales = {
		(row.get("voucher_type"), row.get("voucher_no"))
		for row in rows
		if row.get("movement_type") == "Sale" and row.get("voucher_no")
	}
	missing_conversions = sum(
		1 for row in rows if row.get("conversion_status") == "Not Configured"
	)
	internal_transfers = {
		(row.get("voucher_no"), row.get("voucher_detail_no"), row.get("item_code"))
		for row in rows
		if row.get("movement_type") == "Internal Transfer"
	}

	return [
		{"value": len(rows), "label": _("Movement Rows"), "datatype": "Int", "indicator": "Blue"},
		{
			"value": len({row.get("item_code") for row in rows if row.get("item_code")}),
			"label": _("Distinct Items"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": len(warehouses),
			"label": _("Distinct Warehouses"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{"value": len(sales), "label": _("Sales"), "datatype": "Int", "indicator": "Green"},
		{
			"value": len(internal_transfers),
			"label": _("Internal Transfers"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"value": missing_conversions,
			"label": _("Missing UOM Conversions"),
			"datatype": "Int",
			"indicator": "Orange" if missing_conversions else "Green",
		},
	]
