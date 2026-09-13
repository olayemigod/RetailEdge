from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from retailedge.stock_position import (
	_assert_report_access,
	_coerce_filters,
	_evaluate_direct_reorder_rules,
	_load_direct_reorder_rules,
	_resolve_warehouse_scope,
	_validate_filters,
)

MAX_REPLENISHMENT_HANDOFF_RULES = 20
_SUPPORTED_REORDER_REQUEST_TYPES = {"Purchase", "Transfer", "Material Issue", "Manufacture"}


def get_replenishment_handoff_context() -> dict[str, int]:
	"""Return native Material Request create capability for Stock Position UX gating."""
	return {"can_create_material_request": int(frappe.has_permission("Material Request", "create"))}


def get_replenishment_material_request_handoff(
	item_code: str,
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	"""Revalidate one Stock Position item and return an unsaved native Material Request payload."""
	item_code = str(item_code or "").strip()
	if not item_code:
		frappe.throw(_("Item is required for the replenishment handoff."))

	resolved_filters = _coerce_filters(filters)
	resolved_filters.item_code = item_code
	_validate_filters(resolved_filters)
	_assert_report_access(resolved_filters)
	if not frappe.has_permission("Material Request", "create"):
		frappe.throw(_("You do not have permission to create Material Requests."), frappe.PermissionError)

	warehouses = _resolve_warehouse_scope(resolved_filters)
	item = _get_handoff_item(item_code)
	if not item:
		frappe.throw(_("Item {0} is not an active stock Item.").format(item_code))
	if resolved_filters.get("item_group") and item.item_group != resolved_filters.item_group:
		frappe.throw(_("Item {0} is outside the selected Item Group.").format(item_code))

	rules = _load_direct_reorder_rules(warehouses, filters=resolved_filters, item_scope=[item_code])
	projected_by_warehouse = _get_projected_by_warehouse(item_code, warehouses)
	due_rules = _due_rule_payloads(rules, projected_by_warehouse)
	if not due_rules:
		frappe.throw(_("Replenishment is no longer due for this Item in the current Warehouse scope. Refresh Stock Position and try again."))
	if len(due_rules) > MAX_REPLENISHMENT_HANDOFF_RULES:
		frappe.throw(
			_("More than {0} due reorder rules match this Item. Select a narrower Warehouse scope before starting a Material Request.").format(
				MAX_REPLENISHMENT_HANDOFF_RULES
			)
		)

	request_types = sorted({str(rule.get("material_request_type") or "").strip() for rule in due_rules})
	if "" in request_types or any(request_type not in _SUPPORTED_REORDER_REQUEST_TYPES for request_type in request_types):
		frappe.throw(_("One or more due reorder rules do not have a supported Material Request Type."))
	if len(request_types) != 1:
		frappe.throw(
			_("Due locations use multiple Material Request Types. Select one Warehouse and retry so incompatible request types are not merged."))

	reorder_request_type = request_types[0]
	items = [_material_request_item_payload(item, rule, reorder_request_type) for rule in due_rules]
	schedule_dates = [row["schedule_date"] for row in items if row.get("schedule_date")]
	return {
		"handoff_mode": "unsaved_native_form",
		"doctype": "Material Request",
		"docstatus": 0,
		"company": resolved_filters.company,
		"branch": str(resolved_filters.get("branch") or ""),
		"material_request_type": _native_material_request_type(reorder_request_type),
		"transaction_date": nowdate(),
		"schedule_date": max(schedule_dates or [nowdate()]),
		"items": items,
		"source": {
			"item_code": item_code,
			"due_warehouses": sorted({str(rule.get("warehouse") or "") for rule in due_rules}),
			"revalidated": 1,
		},
	}


def _due_rule_payloads(rules: list[Any], projected_by_warehouse: dict[str, float]) -> list[dict[str, Any]]:
	"""Reuse the Stock Position evaluator per direct rule so handoff math cannot drift."""
	due_rules: list[dict[str, Any]] = []
	for rule in rules:
		warehouse = str(rule.get("warehouse") or "").strip()
		if not warehouse or rule.get("warehouse_group"):
			continue
		projected_qty = flt(projected_by_warehouse.get(warehouse))
		evaluation = _evaluate_direct_reorder_rules([rule], {warehouse: projected_qty})
		if not cint(evaluation.get("reorder_due")):
			continue
		due_rules.append(
			{
				"warehouse": warehouse,
				"projected_qty": projected_qty,
				"reorder_level": flt(rule.get("warehouse_reorder_level")),
				"reorder_qty": flt(rule.get("warehouse_reorder_qty")),
				"suggested_qty": flt(evaluation.get("suggested_reorder_qty")),
				"material_request_type": str(rule.get("material_request_type") or "").strip(),
			}
		)
	return due_rules


def _get_projected_by_warehouse(item_code: str, warehouses: list[str]) -> dict[str, float]:
	rows = frappe.get_list(
		"Bin",
		filters={"item_code": item_code, "warehouse": ["in", warehouses]},
		fields=["warehouse", "projected_qty"],
		order_by="warehouse asc",
		limit=len(warehouses) + 1,
	)
	return {str(row.warehouse): flt(row.projected_qty) for row in rows if row.warehouse}


def _get_handoff_item(item_code: str) -> frappe._dict | None:
	rows = frappe.get_list(
		"Item",
		filters={"name": item_code, "disabled": 0, "is_stock_item": 1},
		fields=[
			"name",
			"item_name",
			"item_group",
			"description",
			"brand",
			"stock_uom",
			"purchase_uom",
			"lead_time_days",
		],
		limit=1,
	)
	return rows[0] if rows else None


def _native_material_request_type(request_type: str) -> str:
	request_type = str(request_type or "").strip()
	return "Material Transfer" if request_type == "Transfer" else request_type


def _material_request_item_payload(
	item: frappe._dict,
	due_rule: dict[str, Any],
	reorder_request_type: str,
) -> dict[str, Any]:
	stock_uom = str(item.stock_uom or "").strip()
	if not stock_uom:
		frappe.throw(_("Item {0} does not have a Stock UOM.").format(item.name))

	uom = stock_uom
	conversion_factor = 1.0
	if reorder_request_type == "Purchase":
		uom = str(item.purchase_uom or stock_uom).strip()
		if uom != stock_uom:
			conversion_factor = (
				flt(
					frappe.db.get_value(
						"UOM Conversion Detail",
						{"parent": item.name, "uom": uom},
						"conversion_factor",
					)
				)
				or 1.0
			)

	qty = flt(due_rule.get("suggested_qty")) / conversion_factor
	if cint(frappe.db.get_value("UOM", uom, "must_be_whole_number", cache=True)):
		qty = ceil(qty)

	return {
		"item_code": item.name,
		"schedule_date": add_days(nowdate(), cint(item.lead_time_days)),
		"qty": qty,
		"conversion_factor": conversion_factor,
		"uom": uom,
		"stock_uom": stock_uom,
		"warehouse": str(due_rule.get("warehouse") or ""),
		"item_name": item.item_name or item.name,
		"description": item.description or "",
		"item_group": item.item_group or "",
		"brand": item.brand or "",
		"reorder_qty": flt(due_rule.get("reorder_qty")),
		"projected_on_hand": flt(due_rule.get("projected_qty")),
		"reorder_level": flt(due_rule.get("reorder_level")),
	}
