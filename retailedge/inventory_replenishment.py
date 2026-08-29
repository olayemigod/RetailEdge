from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from retailedge.inventory_intelligence import reorder_signal
from retailedge.stock_position import (
	MAX_BIN_SCAN_ROWS,
	MAX_ITEM_SCOPE,
	_assert_report_access,
	_coerce_filters,
	_resolve_item_scope,
	_resolve_warehouse_scope,
	_validate_filters,
)

MAX_REORDER_RULES = 20000
REORDER_CHILD_DOCTYPE = "Item Reorder"
REORDER_TABLE_FIELD = "reorder_levels"
REQUIRED_REORDER_FIELDS = (
	"warehouse",
	"warehouse_group",
	"warehouse_reorder_level",
	"warehouse_reorder_qty",
	"material_request_type",
)


@frappe.whitelist()
def get_inventory_replenishment(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return read-only ERPNext Item Reorder intelligence for the permitted stock scope.

	ERPNext remains the configuration and projected-quantity source of truth. This
	service does not create Material Requests, persist recommendations, or mutate Item
	reorder configuration.
	"""
	filters = _coerce_filters(filters)
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	_validate_filters(filters)
	_assert_report_access(filters)
	_assert_reorder_runtime_contract()

	warehouses = _resolve_warehouse_scope(filters)
	items = _get_permitted_items(filters)
	if not items:
		return _empty_payload(filters, warehouses)

	item_map = {str(row.name): row for row in items}
	template_names = sorted({str(row.variant_of) for row in items if row.variant_of})
	template_map = _get_permitted_templates(template_names)
	rule_parents = sorted(set(item_map) | set(template_map))
	rules_by_parent = _get_reorder_rules(rule_parents)
	projected = _get_projected_qty(item_codes=sorted(item_map), warehouses=warehouses)
	warehouse_set = set(warehouses)

	rows: list[dict[str, Any]] = []
	for item_code, item in item_map.items():
		if _is_expired(item) or item.has_variants:
			continue
		direct_rules = rules_by_parent.get(item_code) or []
		inherited_from = ""
		rules = direct_rules
		if not rules and item.variant_of and str(item.variant_of) in template_map:
			inherited_from = str(item.variant_of)
			rules = rules_by_parent.get(inherited_from) or []

		for rule in rules:
			warehouse = str(rule.get("warehouse") or "").strip()
			if not warehouse or warehouse not in warehouse_set:
				continue
			rows.append(
				_evaluate_rule(
					item_code=item_code,
					item=item,
					rule=rule,
					projected_qty=projected.get((item_code, warehouse), 0.0),
					inherited_from=inherited_from,
				)
			)

	rows.sort(key=lambda row: (row["item_code"], row["warehouse"], row["material_request_type"]))
	item_rows = _aggregate_items(rows, item_map=item_map)
	return {
		"rows": rows,
		"items": item_rows,
		"summary": _summary(rows, item_rows),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
			"item_group": filters.get("item_group") or "",
			"item_code": filters.get("item_code") or "",
		},
		"scan": {
			"permitted_items": len(items),
			"reorder_rules": sum(len(value) for value in rules_by_parent.values()),
			"evaluated_rows": len(rows),
			"item_limit": MAX_ITEM_SCOPE,
			"rule_limit": MAX_REORDER_RULES,
			"bin_limit": MAX_BIN_SCAN_ROWS,
		},
		"metadata": {
			"configuration_truth": "ERPNext Item.reorder_levels / Item Reorder",
			"projected_quantity_truth": "ERPNext Bin.projected_qty",
			"runtime_contract_validated": True,
			"threshold_semantics": "ERPNext v16: configured rule triggers when projected quantity is at or below reorder level",
			"quantity_semantics": "Recommended quantity mirrors ERPNext v16: the greater of configured reorder quantity or projected deficiency",
			"variant_semantics": "Variant inherits template reorder rows only when the variant has no direct reorder rows",
			"warehouse_group_semantics": (
				"Warehouse-group rules are surfaced but not scored in R10E until full group visibility can be proven permission-safely."
			),
			"read_only": True,
			"creates_material_request": False,
			"persistent_derived_truth": False,
		},
	}


def _assert_reorder_runtime_contract() -> None:
	cache_key = "retailedge_r10_reorder_runtime_contract"
	if getattr(frappe.local, cache_key, False):
		return
	try:
		item_meta = frappe.get_meta("Item")
		reorder_meta = frappe.get_meta(REORDER_CHILD_DOCTYPE)
		table_field = item_meta.get_field(REORDER_TABLE_FIELD)
		missing = [fieldname for fieldname in REQUIRED_REORDER_FIELDS if not reorder_meta.has_field(fieldname)]
		compatible = bool(
			table_field
			and str(getattr(table_field, "fieldtype", "")) == "Table"
			and str(getattr(table_field, "options", "")) == REORDER_CHILD_DOCTYPE
			and not missing
		)
	except Exception:
		compatible = False
		missing = list(REQUIRED_REORDER_FIELDS)
	if not compatible:
		detail = ", ".join(missing) if missing else REORDER_TABLE_FIELD
		frappe.throw(
			_(
				"The installed ERPNext Item Reorder schema is not compatible with RetailEdge Inventory Intelligence. Expected Item.reorder_levels → Item Reorder with fields: {0}. Update ERPNext or review the installed stock schema before using replenishment intelligence."
			).format(detail)
		)
	setattr(frappe.local, cache_key, True)


def _get_permitted_items(filters: frappe._dict) -> list[frappe._dict]:
	item_scope = _resolve_item_scope(filters)
	item_filters: dict[str, Any] = {"disabled": 0, "is_stock_item": 1}
	if filters.get("item_code"):
		item_filters["name"] = filters.item_code
	elif item_scope is not None:
		if not item_scope:
			return []
		item_filters["name"] = ["in", item_scope]
	rows = frappe.get_list(
		"Item",
		filters=item_filters,
		fields=["name", "item_name", "item_group", "stock_uom", "variant_of", "has_variants", "end_of_life"],
		order_by="name asc",
		limit=MAX_ITEM_SCOPE + 1,
	)
	if len(rows) > MAX_ITEM_SCOPE:
		frappe.throw(_("More than {0} permitted Items are in replenishment scope. Narrow the Item Group or Item first.").format(MAX_ITEM_SCOPE))
	return list(rows)


def _get_permitted_templates(template_names: list[str]) -> dict[str, frappe._dict]:
	if not template_names:
		return {}
	rows = frappe.get_list(
		"Item",
		filters={"name": ["in", template_names], "disabled": 0, "is_stock_item": 1},
		fields=["name", "item_name", "item_group", "stock_uom", "variant_of", "has_variants", "end_of_life"],
		order_by="name asc",
		limit=min(len(template_names), MAX_ITEM_SCOPE) + 1,
	)
	return {str(row.name): row for row in rows}


def _get_reorder_rules(parent_names: list[str]) -> dict[str, list[frappe._dict]]:
	"""Read child rows only for permission-filtered Item parents.

	Item Reorder is a child table without an independent user-facing permission
	model. Parent names reaching this query come exclusively from permission-aware
	Item `get_list` calls above; rows are never queried for an unapproved parent.
	"""
	if not parent_names:
		return {}
	reorder = frappe.qb.DocType(REORDER_CHILD_DOCTYPE)
	query = (
		frappe.qb.from_(reorder)
		.select(
			reorder.parent,
			reorder.warehouse,
			reorder.warehouse_group,
			reorder.warehouse_reorder_level,
			reorder.warehouse_reorder_qty,
			reorder.material_request_type,
		)
		.where(reorder.parent.isin(parent_names))
		.where(reorder.parenttype == "Item")
		.where(reorder.parentfield == REORDER_TABLE_FIELD)
		.orderby(reorder.parent)
		.orderby(reorder.idx)
		.limit(MAX_REORDER_RULES + 1)
	)
	rows = query.run(as_dict=True)
	if len(rows) > MAX_REORDER_RULES:
		frappe.throw(_("More than {0} ERPNext reorder rules are in scope. Narrow the Item Group or Item first.").format(MAX_REORDER_RULES))
	grouped: dict[str, list[frappe._dict]] = defaultdict(list)
	for row in rows:
		grouped[str(row.parent)].append(frappe._dict(row))
	return dict(grouped)


def _get_projected_qty(*, item_codes: list[str], warehouses: list[str]) -> dict[tuple[str, str], float]:
	if not item_codes or not warehouses:
		return {}
	rows = frappe.get_list(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses]},
		fields=["item_code", "warehouse", "projected_qty"],
		order_by="item_code asc, warehouse asc",
		limit=MAX_BIN_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_BIN_SCAN_ROWS:
		frappe.throw(_("More than {0} Bin rows are in replenishment scope. Narrow the Branch, Warehouse, Item Group, or Item first.").format(MAX_BIN_SCAN_ROWS))
	return {
		(str(row.item_code), str(row.warehouse)): flt(row.projected_qty)
		for row in rows
		if row.item_code and row.warehouse
	}


def _evaluate_rule(
	*,
	item_code: str,
	item: frappe._dict,
	rule: frappe._dict,
	projected_qty: float,
	inherited_from: str,
) -> dict[str, Any]:
	warehouse_group = str(rule.get("warehouse_group") or "").strip()
	base = {
		"item_code": item_code,
		"item_name": item.get("item_name") or item_code,
		"item_group": item.get("item_group") or "",
		"stock_uom": item.get("stock_uom") or "",
		"warehouse": str(rule.get("warehouse") or ""),
		"warehouse_group": warehouse_group,
		"material_request_type": str(rule.get("material_request_type") or ""),
		"reorder_level": max(flt(rule.get("warehouse_reorder_level")), 0.0),
		"configured_reorder_qty": max(flt(rule.get("warehouse_reorder_qty")), 0.0),
		"inherited_from_template": inherited_from,
	}
	if warehouse_group:
		return {
			**base,
			"projected_qty": None,
			"shortfall_qty": None,
			"recommended_reorder_qty": None,
			"reorder_triggered": False,
			"evaluation_status": "Unavailable",
			"evaluation_reason": "Warehouse-group projected quantity requires full group visibility before it can be scored safely.",
		}

	signal = reorder_signal(
		projected_qty=projected_qty,
		reorder_level=base["reorder_level"],
		reorder_qty=base["configured_reorder_qty"],
	)
	return {
		**base,
		"projected_qty": signal["projected_qty"],
		"shortfall_qty": signal["shortfall_qty"],
		"recommended_reorder_qty": signal["recommended_reorder_qty"],
		"reorder_triggered": bool(signal["reorder_triggered"]),
		"evaluation_status": "Reorder Now" if signal["reorder_triggered"] else "Healthy",
		"evaluation_reason": (
			"Projected quantity is at or below the ERPNext reorder level."
			if signal["reorder_triggered"]
			else "Projected quantity is above the ERPNext reorder threshold, or this zero rule is inactive."
		),
	}


def _aggregate_items(rows: list[dict[str, Any]], *, item_map: dict[str, frappe._dict]) -> list[dict[str, Any]]:
	buckets: dict[str, dict[str, Any]] = {}
	for row in rows:
		item_code = str(row.get("item_code") or "")
		item = item_map.get(item_code)
		if not item:
			continue
		bucket = buckets.setdefault(
			item_code,
			{
				"item_code": item_code,
				"item_name": item.get("item_name") or item_code,
				"item_group": item.get("item_group") or "",
				"stock_uom": item.get("stock_uom") or "",
				"configured_location_count": 0,
				"triggered_location_count": 0,
				"unavailable_rule_count": 0,
				"recommended_reorder_qty": 0.0,
			},
		)
		bucket["configured_location_count"] += 1
		if row.get("evaluation_status") == "Unavailable":
			bucket["unavailable_rule_count"] += 1
		if row.get("reorder_triggered"):
			bucket["triggered_location_count"] += 1
			bucket["recommended_reorder_qty"] += flt(row.get("recommended_reorder_qty"))

	result: list[dict[str, Any]] = []
	for bucket in buckets.values():
		if bucket["triggered_location_count"]:
			status = "Reorder Now"
		elif bucket["unavailable_rule_count"]:
			status = "Review warehouse group"
		else:
			status = "Healthy"
		result.append({**bucket, "replenishment_status": status})
	result.sort(key=lambda row: (-int(row["triggered_location_count"]), row["item_code"]))
	return result


def _summary(rows: list[dict[str, Any]], item_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Configured Reorder Rules"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Items Requiring Reorder"),
			"value": sum(1 for row in item_rows if row.get("replenishment_status") == "Reorder Now"),
			"datatype": "Int",
		},
		{
			"label": _("Triggered Warehouse Rules"),
			"value": sum(1 for row in rows if row.get("reorder_triggered")),
			"datatype": "Int",
		},
		{
			"label": _("Warehouse-group Rules Pending Safe Evaluation"),
			"value": sum(1 for row in rows if row.get("evaluation_status") == "Unavailable"),
			"datatype": "Int",
		},
	]


def _is_expired(item: frappe._dict) -> bool:
	end_of_life = str(item.get("end_of_life") or "").strip()
	if not end_of_life or end_of_life == "0000-00-00":
		return False
	return getdate(end_of_life) < getdate(today())


def _empty_payload(filters: frappe._dict, warehouses: list[str]) -> dict[str, Any]:
	return {
		"rows": [],
		"items": [],
		"summary": _summary([], []),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
		},
		"scan": {"permitted_items": 0, "reorder_rules": 0, "evaluated_rows": 0},
		"metadata": {
			"configuration_truth": "ERPNext Item.reorder_levels / Item Reorder",
			"projected_quantity_truth": "ERPNext Bin.projected_qty",
			"runtime_contract_validated": True,
			"read_only": True,
			"creates_material_request": False,
		},
	}