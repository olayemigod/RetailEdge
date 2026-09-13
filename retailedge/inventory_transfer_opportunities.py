from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.guided_stock_transfer import ACTION_KEY as GUIDED_TRANSFER_ACTION_KEY
from retailedge.inventory_replenishment import get_inventory_replenishment
from retailedge.stock_position import (
	MAX_BIN_SCAN_ROWS,
	MAX_ITEM_SCOPE,
	_assert_report_access,
	_coerce_filters,
	_resolve_warehouse_scope,
	_validate_filters,
)

MAX_TRANSFER_OPPORTUNITIES = 200


@frappe.whitelist()
def get_inventory_transfer_opportunities(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Suggest read-only same-company warehouse transfers from ERPNext reorder truth.

	A target must have a directly evaluable ERPNext reorder rule in Reorder Now state.
	A source must have an active directly evaluable ERPNext reorder rule that is Healthy.
	Source capacity is limited by both available stock and projected stock above that
	source's own reorder level. Allocation is consumed as suggestions are built so the
	same source stock is never promised more than once in one response.
	"""
	filters = _coerce_filters(filters)
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	_validate_filters(filters)
	_assert_report_access(filters)

	warehouses = _active_warehouse_scope(filters)
	if len(warehouses) < 2:
		return _empty_payload(filters, warehouses, reason="At least two active permitted warehouses are required.")

	replenishment = get_inventory_replenishment(filters)
	direct_rules = [
		row
		for row in replenishment.get("rows") or []
		if row.get("warehouse") in set(warehouses)
		and not row.get("warehouse_group")
		and row.get("evaluation_status") in {"Reorder Now", "Healthy"}
	]
	if not direct_rules:
		return _empty_payload(
			filters,
			warehouses,
			replenishment=replenishment,
			reason="No directly evaluable ERPNext warehouse reorder rules are in scope.",
		)

	item_codes = sorted({str(row.get("item_code")) for row in direct_rules if row.get("item_code")})
	bin_map = _get_available_stock(item_codes=item_codes, warehouses=warehouses)
	item_map = _get_item_transfer_metadata(item_codes)
	rows = _allocate_transfer_opportunities(
		rules=direct_rules,
		bin_map=bin_map,
		item_map=item_map,
		can_create_stock_entry=bool(frappe.has_permission("Stock Entry", "create")),
	)

	return {
		"rows": rows,
		"summary": _summary(rows),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
			"item_group": filters.get("item_group") or "",
			"item_code": filters.get("item_code") or "",
		},
		"scan": {
			"reorder_rules": len(direct_rules),
			"bin_rows": len(bin_map),
			"opportunities": len(rows),
			"bin_limit": MAX_BIN_SCAN_ROWS,
			"item_limit": MAX_ITEM_SCOPE,
			"opportunity_limit": MAX_TRANSFER_OPPORTUNITIES,
		},
		"metadata": {
			"stock_truth": "ERPNext Bin",
			"reorder_truth": "ERPNext Item.reorder_levels / Item Reorder",
			"target_semantics": "Target must have a directly evaluable ERPNext reorder rule in Reorder Now state.",
			"source_semantics": "Source must have an active healthy direct reorder rule and retain its reorder level after the proposed allocation.",
			"quantity_semantics": "Suggested quantity is bounded by target ERPNext reorder need, source available stock, and source projected excess above its reorder level.",
			"allocation_semantics": "Source capacity is consumed across suggestions in this response to prevent duplicate over-allocation.",
			"same_company_only": True,
			"read_only": True,
			"creates_stock_entry": False,
			"guided_action_key": GUIDED_TRANSFER_ACTION_KEY,
			"persistent_derived_truth": False,
		},
	}


def _active_warehouse_scope(filters: frappe._dict) -> list[str]:
	warehouses = _resolve_warehouse_scope(filters)
	rows = frappe.get_list(
		"Warehouse",
		filters={
			"company": filters.company,
			"is_group": 0,
			"disabled": 0,
			"name": ["in", warehouses],
		},
		pluck="name",
		order_by="name asc",
		limit=len(warehouses) + 1,
	)
	return list(rows)


def _get_available_stock(*, item_codes: list[str], warehouses: list[str]) -> dict[tuple[str, str], dict[str, float]]:
	if not item_codes or not warehouses:
		return {}
	rows = frappe.get_list(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses]},
		fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"],
		order_by="item_code asc, warehouse asc",
		limit=MAX_BIN_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_BIN_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} Bin rows are in transfer-opportunity scope. Narrow the Branch, Warehouse, Item Group, or Item first."
			).format(MAX_BIN_SCAN_ROWS)
		)
	return {
		(str(row.item_code), str(row.warehouse)): {
			"actual_qty": flt(row.actual_qty),
			"reserved_qty": flt(row.reserved_qty),
			"available_qty": max(flt(row.actual_qty) - flt(row.reserved_qty), 0.0),
			"projected_qty": flt(row.projected_qty),
		}
		for row in rows
		if row.item_code and row.warehouse
	}


def _get_item_transfer_metadata(item_codes: list[str]) -> dict[str, frappe._dict]:
	if not item_codes:
		return {}
	rows = frappe.get_list(
		"Item",
		filters={"name": ["in", item_codes], "disabled": 0, "is_stock_item": 1},
		fields=["name", "item_name", "item_group", "stock_uom", "has_serial_no", "has_batch_no"],
		order_by="name asc",
		limit=MAX_ITEM_SCOPE + 1,
	)
	return {str(row.name): row for row in rows}


def _allocate_transfer_opportunities(
	*,
	rules: list[dict[str, Any]],
	bin_map: dict[tuple[str, str], dict[str, float]],
	item_map: dict[str, frappe._dict],
	can_create_stock_entry: bool,
) -> list[dict[str, Any]]:
	rules_by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for row in rules:
		item_code = str(row.get("item_code") or "")
		if item_code and item_code in item_map:
			rules_by_item[item_code].append(row)

	result: list[dict[str, Any]] = []
	for item_code in sorted(rules_by_item):
		item_rules = rules_by_item[item_code]
		targets = sorted(
			(row for row in item_rules if row.get("evaluation_status") == "Reorder Now"),
			key=lambda row: (flt(row.get("projected_qty")), str(row.get("warehouse") or "")),
		)
		sources = []
		for row in item_rules:
			if row.get("evaluation_status") != "Healthy":
				continue
			if flt(row.get("reorder_level")) <= 0 and flt(row.get("configured_reorder_qty")) <= 0:
				continue
			warehouse = str(row.get("warehouse") or "")
			stock = bin_map.get((item_code, warehouse)) or {}
			projected_excess = max(flt(row.get("projected_qty")) - flt(row.get("reorder_level")), 0.0)
			capacity = min(max(flt(stock.get("available_qty")), 0.0), projected_excess)
			if capacity <= 0:
				continue
			sources.append({"rule": row, "capacity": capacity, "stock": stock})
		sources.sort(key=lambda entry: (-flt(entry["capacity"]), str(entry["rule"].get("warehouse") or "")))

		for target in targets:
			target_warehouse = str(target.get("warehouse") or "")
			remaining = max(flt(target.get("recommended_reorder_qty")), 0.0)
			if remaining <= 0:
				continue
			for source in sources:
				if remaining <= 0 or len(result) >= MAX_TRANSFER_OPPORTUNITIES:
					break
				source_warehouse = str(source["rule"].get("warehouse") or "")
				if not source_warehouse or source_warehouse == target_warehouse:
					continue
				capacity = max(flt(source.get("capacity")), 0.0)
				if capacity <= 0:
					continue
				qty = min(remaining, capacity)
				if qty <= 0:
					continue

				item = item_map[item_code]
				serial_or_batch = bool(cint(item.get("has_serial_no")) or cint(item.get("has_batch_no")))
				result.append(
					{
						"item_code": item_code,
						"item_name": item.get("item_name") or item_code,
						"item_group": item.get("item_group") or "",
						"stock_uom": item.get("stock_uom") or "",
						"source_warehouse": source_warehouse,
						"target_warehouse": target_warehouse,
						"suggested_transfer_qty": qty,
						"source_available_qty": flt(source["stock"].get("available_qty")),
						"source_projected_qty": flt(source["rule"].get("projected_qty")),
						"source_reorder_level": flt(source["rule"].get("reorder_level")),
						"source_projected_excess_before_allocation": capacity,
						"target_projected_qty": flt(target.get("projected_qty")),
						"target_reorder_level": flt(target.get("reorder_level")),
						"target_reorder_need": flt(target.get("recommended_reorder_qty")),
						"target_remaining_need_after_allocation": max(remaining - qty, 0.0),
						"can_create_transfer": bool(can_create_stock_entry),
						"guided_transfer_available": bool(can_create_stock_entry and not serial_or_batch),
						"requires_full_stock_entry": serial_or_batch,
						"guided_action_key": GUIDED_TRANSFER_ACTION_KEY,
					}
				)
				source["capacity"] = capacity - qty
				remaining -= qty
			if len(result) >= MAX_TRANSFER_OPPORTUNITIES:
				break
		if len(result) >= MAX_TRANSFER_OPPORTUNITIES:
			break
	return result


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Transfer Opportunities"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Items with Transfer Opportunities"),
			"value": len({str(row.get("item_code")) for row in rows if row.get("item_code")}),
			"datatype": "Int",
		},
		{
			"label": _("Suggested Transfer Qty"),
			"value": sum(flt(row.get("suggested_transfer_qty")) for row in rows),
			"datatype": "Float",
		},
	]


def _empty_payload(
	filters: frappe._dict,
	warehouses: list[str],
	*,
	replenishment: dict[str, Any] | None = None,
	reason: str = "",
) -> dict[str, Any]:
	return {
		"rows": [],
		"summary": _summary([]),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
		},
		"scan": {
			"reorder_rules": len((replenishment or {}).get("rows") or []),
			"bin_rows": 0,
			"opportunities": 0,
			"opportunity_limit": MAX_TRANSFER_OPPORTUNITIES,
		},
		"metadata": {
			"stock_truth": "ERPNext Bin",
			"reorder_truth": "ERPNext Item.reorder_levels / Item Reorder",
			"same_company_only": True,
			"read_only": True,
			"creates_stock_entry": False,
			"guided_action_key": GUIDED_TRANSFER_ACTION_KEY,
			"reason": reason,
			"persistent_derived_truth": False,
		},
	}
