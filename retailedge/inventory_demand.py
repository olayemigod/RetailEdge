from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from retailedge.inventory_intelligence import average_daily_demand
from retailedge.stock_position import (
	MAX_ITEM_SCOPE,
	_assert_report_access,
	_coerce_filters,
	_get_item_metadata,
	_resolve_item_scope,
	_resolve_warehouse_scope,
	_validate_filters,
)

DEFAULT_LOOKBACK_DAYS = 90
MAX_LOOKBACK_DAYS = 365
MAX_SLE_SCAN_ROWS = 20000
DIRECT_DEMAND_VOUCHER_TYPES = {"Sales Invoice", "Delivery Note"}
DEMAND_STOCK_ENTRY_PURPOSES = {"Material Issue"}


@frappe.whitelist()
def get_historical_inventory_demand(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return bounded observed outward demand for a permission-safe inventory scope.

	This service is deliberately historical and descriptive. It does not forecast,
	persist inventory truth, or treat internal transfers and manufacturing movements
	as customer/operational demand.
	"""
	filters = _coerce_filters(filters)
	_normalise_filters(filters)
	_validate_filters(filters)
	_assert_report_access(filters)
	_assert_sle_read_permission()

	warehouses = _resolve_warehouse_scope(filters)
	item_scope = _resolve_item_scope(filters)
	from_date, to_date, lookback_days = _resolve_window(filters)

	if item_scope == []:
		return _empty_payload(filters, warehouses, from_date, to_date, lookback_days)

	sle_filters: dict[str, Any] = {
		"company": filters.company,
		"warehouse": ["in", warehouses],
		"posting_date": ["between", [str(from_date), str(to_date)]],
		"actual_qty": ["<", 0],
		"is_cancelled": 0,
	}
	if filters.get("item_code"):
		sle_filters["item_code"] = filters.item_code
	elif item_scope is not None:
		sle_filters["item_code"] = ["in", item_scope]

	sle_rows = frappe.get_list(
		"Stock Ledger Entry",
		filters=sle_filters,
		fields=[
			"name",
			"posting_date",
			"item_code",
			"warehouse",
			"actual_qty",
			"voucher_type",
			"voucher_no",
		],
		order_by="posting_date asc, creation asc, name asc",
		limit=MAX_SLE_SCAN_ROWS + 1,
	)
	if len(sle_rows) > MAX_SLE_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} outward stock ledger rows match this demand window. Narrow the Branch, Warehouse, Item Group, Item, or lookback period before loading inventory demand."
			).format(MAX_SLE_SCAN_ROWS)
		)

	stock_entry_purposes = _get_stock_entry_purposes(sle_rows)
	demand_rows = [
		row for row in sle_rows if _is_demand_row(row, stock_entry_purposes=stock_entry_purposes)
	]
	item_codes = sorted({str(row.item_code) for row in demand_rows if row.item_code})
	item_map = _get_item_metadata(item_codes)
	permitted_demand_rows = [
		row for row in demand_rows if str(row.get("item_code") or "") in item_map
	]
	location_rows, item_rows = _aggregate_demand(
		permitted_demand_rows,
		item_map=item_map,
		to_date=to_date,
		lookback_days=lookback_days,
	)

	return {
		"rows": item_rows,
		"locations": location_rows,
		"summary": _summary(item_rows),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
			"item_group": filters.get("item_group") or "",
			"item_code": filters.get("item_code") or "",
			"from_date": str(from_date),
			"to_date": str(to_date),
			"lookback_days": lookback_days,
		},
		"scan": {
			"outward_sle_rows": len(sle_rows),
			"demand_sle_rows": len(permitted_demand_rows),
			"sle_limit": MAX_SLE_SCAN_ROWS,
			"item_limit": MAX_ITEM_SCOPE,
		},
		"metadata": {
			"basis": "observed outward Stock Ledger Entry quantity",
			"direct_demand_voucher_types": sorted(DIRECT_DEMAND_VOUCHER_TYPES),
			"stock_entry_purposes_included": sorted(DEMAND_STOCK_ENTRY_PURPOSES),
			"excluded_semantics": (
				"Internal transfers, manufacture/repack movements, Stock Reconciliation, "
				"purchase returns and other non-demand outward movements are excluded."
			),
			"permission_contract": "Demand rows are returned only for Items visible through permission-aware Item queries.",
			"forecast": False,
			"persistent_derived_truth": False,
		},
	}


def _normalise_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if "lookback_days" not in filters or filters.get("lookback_days") in (None, ""):
		filters.lookback_days = DEFAULT_LOOKBACK_DAYS
	else:
		filters.lookback_days = cint(filters.get("lookback_days"))
	filters.as_of_date = str(filters.get("as_of_date") or today())


def _resolve_window(filters: frappe._dict):
	raw_lookback = filters.get("lookback_days")
	lookback_days = DEFAULT_LOOKBACK_DAYS if raw_lookback in (None, "") else cint(raw_lookback)
	if lookback_days < 1 or lookback_days > MAX_LOOKBACK_DAYS:
		frappe.throw(
			_("Inventory demand lookback must be between 1 and {0} days.").format(MAX_LOOKBACK_DAYS)
		)
	to_date = getdate(filters.get("as_of_date") or today())
	from_date = getdate(add_days(to_date, -(lookback_days - 1)))
	return from_date, to_date, lookback_days


def _assert_sle_read_permission() -> None:
	if not frappe.has_permission("Stock Ledger Entry", "read"):
		frappe.throw(
			_("You do not have permission to view historical stock movements."),
			frappe.PermissionError,
		)


def _get_stock_entry_purposes(sle_rows: list[frappe._dict]) -> dict[str, str]:
	names = sorted(
		{
			str(row.voucher_no)
			for row in sle_rows
			if row.voucher_type == "Stock Entry" and row.voucher_no
		}
	)
	if not names or not frappe.has_permission("Stock Entry", "read"):
		return {}
	rows = frappe.get_list(
		"Stock Entry",
		filters={"name": ["in", names], "docstatus": 1},
		fields=["name", "purpose"],
		order_by="name asc",
		limit=max(len(names), 1),
	)
	return {str(row.name): str(row.purpose or "") for row in rows}


def _is_demand_row(row: frappe._dict, *, stock_entry_purposes: dict[str, str]) -> bool:
	if flt(row.get("actual_qty")) >= 0:
		return False
	voucher_type = str(row.get("voucher_type") or "")
	if voucher_type in DIRECT_DEMAND_VOUCHER_TYPES:
		return True
	if voucher_type == "Stock Entry":
		return stock_entry_purposes.get(str(row.get("voucher_no") or "")) in DEMAND_STOCK_ENTRY_PURPOSES
	return False


def _aggregate_demand(
	rows: list[frappe._dict],
	*,
	item_map: dict[str, frappe._dict],
	to_date,
	lookback_days: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	location_buckets: dict[tuple[str, str], dict[str, Any]] = {}
	item_buckets: dict[str, dict[str, Any]] = {}
	for row in rows:
		item_code = str(row.get("item_code") or "").strip()
		warehouse = str(row.get("warehouse") or "").strip()
		item = item_map.get(item_code)
		if not item_code or not warehouse or not item:
			continue
		qty = abs(flt(row.get("actual_qty")))
		posting_date = getdate(row.posting_date)

		location = location_buckets.setdefault(
			(item_code, warehouse),
			_new_bucket(item_code, item=item, warehouse=warehouse),
		)
		_add_demand(location, qty, posting_date)

		item_bucket = item_buckets.setdefault(
			item_code,
			_new_bucket(item_code, item=item, warehouse=""),
		)
		_add_demand(item_bucket, qty, posting_date)

	location_rows = [
		_finalise_bucket(bucket, to_date=to_date, lookback_days=lookback_days)
		for bucket in location_buckets.values()
	]
	item_rows = [
		_finalise_bucket(bucket, to_date=to_date, lookback_days=lookback_days)
		for bucket in item_buckets.values()
	]
	location_rows.sort(key=lambda row: (row["item_code"], row["warehouse"]))
	item_rows.sort(key=lambda row: (-flt(row["demand_qty"]), row["item_code"]))
	return location_rows, item_rows


def _new_bucket(item_code: str, *, item: frappe._dict, warehouse: str) -> dict[str, Any]:
	return {
		"item_code": item_code,
		"item_name": item.get("item_name") or item_code,
		"item_group": item.get("item_group") or "",
		"stock_uom": item.get("stock_uom") or "",
		"warehouse": warehouse,
		"demand_qty": 0.0,
		"movement_count": 0,
		"last_demand_on": None,
	}


def _add_demand(bucket: dict[str, Any], qty: float, posting_date) -> None:
	bucket["demand_qty"] = flt(bucket.get("demand_qty")) + max(flt(qty), 0.0)
	bucket["movement_count"] = cint(bucket.get("movement_count")) + 1
	last = bucket.get("last_demand_on")
	if not last or getdate(last) < posting_date:
		bucket["last_demand_on"] = posting_date


def _finalise_bucket(bucket: dict[str, Any], *, to_date, lookback_days: int) -> dict[str, Any]:
	result = dict(bucket)
	last = result.get("last_demand_on")
	result["last_demand_on"] = str(last) if last else None
	result["days_since_demand"] = date_diff(to_date, last) if last else None
	result["average_daily_demand"] = average_daily_demand(result.get("demand_qty"), lookback_days)
	return result


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Items with Observed Demand"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Observed Demand Quantity"),
			"value": sum(flt(row.get("demand_qty")) for row in rows),
			"datatype": "Float",
		},
	]


def _empty_payload(filters, warehouses, from_date, to_date, lookback_days: int) -> dict[str, Any]:
	return {
		"rows": [],
		"locations": [],
		"summary": _summary([]),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"warehouse": filters.get("warehouse") or "",
			"warehouse_count": len(warehouses),
			"item_group": filters.get("item_group") or "",
			"item_code": filters.get("item_code") or "",
			"from_date": str(from_date),
			"to_date": str(to_date),
			"lookback_days": lookback_days,
		},
		"scan": {"outward_sle_rows": 0, "demand_sle_rows": 0, "sle_limit": MAX_SLE_SCAN_ROWS},
		"metadata": {"basis": "observed outward Stock Ledger Entry quantity", "forecast": False},
	}
