from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.stock_position import (
	MAX_BIN_SCAN_ROWS,
	_assert_report_access,
	_coerce_filters,
	_resolve_warehouse_scope,
	_validate_filters,
)


def get_hidden_inventory_location_exceptions(
	filters: dict[str, Any] | str | None,
	*,
	aggregate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
	"""Find warehouse exceptions hidden by permitted-scope item aggregation.

	Stock Position remains the item-level truth presented to users. This helper only
	looks for unambiguous location states that can be offset when multiple permitted
	warehouses are summed: negative stock and fully reserved positive stock. It does
	not classify zero Bin rows as stockouts because dormant zero rows are not sufficient
	business evidence on their own.
	"""
	filters = _coerce_filters(filters)
	_validate_filters(filters)
	_assert_report_access(filters)

	aggregate_by_item = {
		str(row.get("item_code")): row
		for row in aggregate_rows
		if row.get("item_code")
	}
	item_codes = sorted(aggregate_by_item)
	if not item_codes:
		return _empty_payload()

	warehouses = _resolve_warehouse_scope(filters)
	if len(warehouses) <= 1:
		return _empty_payload(warehouse_count=len(warehouses))

	rows = frappe.get_list(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses]},
		fields=["item_code", "warehouse", "actual_qty", "reserved_qty"],
		order_by="item_code asc, warehouse asc",
		limit=MAX_BIN_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_BIN_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} Bin rows are in warehouse exception scope. Narrow the Branch, Warehouse, Item Group, or Item first."
			).format(MAX_BIN_SCAN_ROWS)
		)

	classified = _classify_hidden_location_exceptions(
		aggregate_by_item=aggregate_by_item,
		location_rows=[dict(row) for row in rows],
	)
	return {
		**classified,
		"scan": {
			"bin_rows": len(rows),
			"bin_limit": MAX_BIN_SCAN_ROWS,
			"warehouse_count": len(warehouses),
		},
		"metadata": {
			"stock_truth": "ERPNext Bin",
			"aggregate_truth": "RetailEdge Stock Position",
			"zero_bin_stockout_inference": False,
			"read_only": True,
			"persistent_derived_truth": False,
		},
	}


def _classify_hidden_location_exceptions(
	*,
	aggregate_by_item: dict[str, dict[str, Any]],
	location_rows: list[dict[str, Any]],
) -> dict[str, Any]:
	hidden_negative: list[dict[str, Any]] = []
	hidden_fully_reserved: list[dict[str, Any]] = []

	for row in location_rows:
		item_code = str(row.get("item_code") or "")
		warehouse = str(row.get("warehouse") or "")
		aggregate = aggregate_by_item.get(item_code)
		if not aggregate or not warehouse:
			continue
		actual = flt(row.get("actual_qty"))
		reserved = flt(row.get("reserved_qty"))
		available = actual - reserved
		aggregate_status = str(aggregate.get("stock_status") or "")

		if actual < 0 and aggregate_status != "Negative":
			hidden_negative.append(
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"actual_qty": actual,
					"reserved_qty": reserved,
					"available_qty": available,
				}
			)
		elif actual > 0 and available <= 0 and aggregate_status != "Fully Reserved":
			hidden_fully_reserved.append(
				{
					"item_code": item_code,
					"warehouse": warehouse,
					"actual_qty": actual,
					"reserved_qty": reserved,
					"available_qty": available,
				}
			)

	return {
		"hidden_negative_locations": hidden_negative,
		"hidden_fully_reserved_locations": hidden_fully_reserved,
		"summary": {
			"hidden_negative_location_count": len(hidden_negative),
			"hidden_fully_reserved_location_count": len(hidden_fully_reserved),
		},
	}


def _empty_payload(*, warehouse_count: int = 0) -> dict[str, Any]:
	return {
		"hidden_negative_locations": [],
		"hidden_fully_reserved_locations": [],
		"summary": {
			"hidden_negative_location_count": 0,
			"hidden_fully_reserved_location_count": 0,
		},
		"scan": {
			"bin_rows": 0,
			"bin_limit": MAX_BIN_SCAN_ROWS,
			"warehouse_count": warehouse_count,
		},
		"metadata": {
			"stock_truth": "ERPNext Bin",
			"aggregate_truth": "RetailEdge Stock Position",
			"zero_bin_stockout_inference": False,
			"read_only": True,
			"persistent_derived_truth": False,
		},
	}
