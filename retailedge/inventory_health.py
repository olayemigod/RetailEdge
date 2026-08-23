from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today

from retailedge.inventory_demand import (
	DEFAULT_LOOKBACK_DAYS,
	get_historical_inventory_demand,
)
from retailedge.inventory_intelligence import (
	MovementThresholds,
	classify_movement,
	stock_cover_days,
)
from retailedge.inventory_replenishment import get_inventory_replenishment
from retailedge.reporting_capabilities import require_report_action
from retailedge.stock_position import (
	DEFAULT_PAGE_SIZE,
	_build_stock_position_dataset,
	_coerce_filters,
	_matches_stock_status,
	_page_response,
	_summary as _stock_summary,
)

DEFAULT_SLOW_DAYS = 30
DEFAULT_NON_MOVING_DAYS = 90
MOVEMENT_CLASSES = {
	"All",
	"Fast",
	"Normal",
	"Slow",
	"Non-moving",
	"No demand in window",
}
REPLENISHMENT_STATUSES = {
	"All",
	"Reorder Now",
	"Review warehouse group",
	"Healthy",
	"No reorder rule",
}


@frappe.whitelist()
def get_inventory_health(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	"""Compose current ERPNext Bin, demand, and reorder intelligence."""
	dataset = _build_inventory_health_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_inventory_health_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Return the bounded R10 dataset after reusing Stock Position export entitlement."""
	filters = _normalise_health_filters(filters)
	require_report_action(
		"stock-position",
		action="export",
		company=str(filters.get("company") or ""),
		branch=str(filters.get("branch") or ""),
	)
	return _build_inventory_health_dataset(filters)


def _build_inventory_health_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _normalise_health_filters(filters)
	stock = _build_stock_position_dataset(filters)
	demand = get_historical_inventory_demand(filters)
	replenishment = get_inventory_replenishment(filters)
	thresholds = _movement_thresholds(filters)
	lookback_days = cint(demand.get("scope", {}).get("lookback_days")) or DEFAULT_LOOKBACK_DAYS
	demand_by_item = {
		str(row.get("item_code")): row for row in demand.get("rows") or [] if row.get("item_code")
	}
	replenishment_by_item = {
		str(row.get("item_code")): row
		for row in replenishment.get("items") or []
		if row.get("item_code")
	}
	show_costs = bool(stock.get("show_costs"))
	stock_rows = list(stock.get("rows") or [])
	synthetic_zero_items = 0
	if cint(filters.get("include_zero")):
		stock_rows, synthetic_zero_items = _with_zero_balance_intelligence_rows(
			stock_rows,
			demand_by_item=demand_by_item,
			replenishment_by_item=replenishment_by_item,
			show_costs=show_costs,
			stock_status=filters.get("stock_status"),
		)

	rows = [
		_enrich_stock_row(
			row,
			demand=demand_by_item.get(str(row.get("item_code") or "")),
			replenishment=replenishment_by_item.get(str(row.get("item_code") or "")),
			lookback_days=lookback_days,
			thresholds=thresholds,
		)
		for row in stock_rows
	]
	movement_class = str(filters.get("movement_class") or "All").strip()
	if movement_class not in MOVEMENT_CLASSES:
		frappe.throw(_("Unsupported Movement Class filter."))
	if movement_class != "All":
		rows = [row for row in rows if row.get("movement_class") == movement_class]

	replenishment_status = str(filters.get("replenishment_status") or "All").strip()
	if replenishment_status not in REPLENISHMENT_STATUSES:
		frappe.throw(_("Unsupported Replenishment Status filter."))
	if replenishment_status != "All":
		rows = [row for row in rows if row.get("replenishment_status") == replenishment_status]

	return {
		"columns": _columns(stock.get("columns") or []),
		"rows": rows,
		"summary": _summary(rows, show_costs=show_costs),
		"company_currency": stock.get("company_currency") or "",
		"show_costs": int(show_costs),
		"scope": {
			**dict(stock.get("scope") or {}),
			"lookback_days": lookback_days,
			"from_date": demand.get("scope", {}).get("from_date"),
			"to_date": demand.get("scope", {}).get("to_date"),
			"movement_class": movement_class,
			"replenishment_status": replenishment_status,
			"high_cover_review_threshold_days": lookback_days,
			"include_zero": cint(filters.get("include_zero")),
		},
		"scan": {
			"stock": stock.get("scan") or {},
			"demand": demand.get("scan") or {},
			"replenishment": replenishment.get("scan") or {},
			"synthetic_zero_items": synthetic_zero_items,
		},
		"metadata": {
			"current_stock_truth": "ERPNext Bin",
			"historical_demand_truth": demand.get("metadata") or {},
			"replenishment_truth": replenishment.get("metadata") or {},
			"stock_cover_basis": "current available stock divided by observed average daily demand",
			"stock_cover_is_forecast": False,
			"stock_cover_review_contract": (
				"High Cover Review means demand-backed estimated stock cover exceeds the selected evidence window. It is an advisory review flag, not an overstock assertion or demand forecast."
			),
			"zero_balance_contract": (
				"When zero-stock intelligence is enabled, a permission-visible demand/reorder item with no Bin row in the resolved warehouse scope is represented as current quantity zero. No balance is persisted."
			),
			"movement_thresholds": {
				"slow_days": thresholds.slow_days,
				"non_moving_days": thresholds.non_moving_days,
				"fast_daily_demand": thresholds.fast_daily_demand,
			},
			"read_only": True,
			"persistent_derived_truth": False,
			"export_authorization_scope": "stock-position",
		},
	}


def _normalise_health_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	filters = _coerce_filters(filters)
	if "lookback_days" not in filters or filters.get("lookback_days") in (None, ""):
		filters.lookback_days = DEFAULT_LOOKBACK_DAYS
	requested_as_of = filters.get("as_of_date")
	if requested_as_of and getdate(requested_as_of) != getdate(today()):
		frappe.throw(
			_(
				"Inventory Health uses current ERPNext Bin stock. Historical As Of dates are not supported on this current-position view."
			)
		)
	filters.as_of_date = today()
	if "slow_days" not in filters or filters.get("slow_days") in (None, ""):
		filters.slow_days = DEFAULT_SLOW_DAYS
	if "non_moving_days" not in filters or filters.get("non_moving_days") in (None, ""):
		filters.non_moving_days = DEFAULT_NON_MOVING_DAYS
	if "replenishment_status" not in filters or filters.get("replenishment_status") in (None, ""):
		filters.replenishment_status = "All"
	if "include_zero" not in filters or filters.get("include_zero") in (None, ""):
		filters.include_zero = 1
	return filters


def _movement_thresholds(filters: frappe._dict) -> MovementThresholds:
	fast = filters.get("fast_daily_demand")
	fast = None if fast in (None, "") else flt(fast)
	try:
		return MovementThresholds(
			slow_days=cint(filters.get("slow_days")),
			non_moving_days=cint(filters.get("non_moving_days")),
			fast_daily_demand=fast,
		)
	except ValueError as exc:
		frappe.throw(_("Invalid inventory movement thresholds: {0}").format(str(exc)))


def _with_zero_balance_intelligence_rows(
	stock_rows: list[dict[str, Any]],
	*,
	demand_by_item: dict[str, dict[str, Any]],
	replenishment_by_item: dict[str, dict[str, Any]],
	show_costs: bool,
	stock_status: Any,
) -> tuple[list[dict[str, Any]], int]:
	rows = [dict(row) for row in stock_rows]
	existing = {str(row.get("item_code") or "") for row in rows if row.get("item_code")}
	candidate_codes = sorted((set(demand_by_item) | set(replenishment_by_item)) - existing)
	added = 0
	for item_code in candidate_codes:
		evidence = demand_by_item.get(item_code) or replenishment_by_item.get(item_code) or {}
		row: dict[str, Any] = {
			"item_code": item_code,
			"item_name": evidence.get("item_name") or item_code,
			"item_group": evidence.get("item_group") or "",
			"stock_uom": evidence.get("stock_uom") or "",
			"actual_qty": 0.0,
			"reserved_qty": 0.0,
			"available_qty": 0.0,
			"ordered_qty": 0.0,
			"projected_qty": 0.0,
			"location_count": 0,
			"stock_status": "Out of Stock",
		}
		if show_costs:
			row["valuation_rate"] = 0.0
			row["stock_value"] = 0.0
		if not _matches_stock_status(row, stock_status):
			continue
		rows.append(row)
		added += 1
	rows.sort(key=lambda row: (str(row.get("item_group") or ""), str(row.get("item_code") or "")))
	return rows, added


def _enrich_stock_row(
	stock_row: dict[str, Any],
	*,
	demand: dict[str, Any] | None,
	replenishment: dict[str, Any] | None,
	lookback_days: int,
	thresholds: MovementThresholds,
) -> dict[str, Any]:
	result = dict(stock_row)
	demand = demand or {}
	replenishment = replenishment or {}
	demand_qty = flt(demand.get("demand_qty"))
	daily_demand = flt(demand.get("average_daily_demand"))
	days_since_demand = demand.get("days_since_demand")
	cover_days = stock_cover_days(result.get("available_qty"), daily_demand)
	result.update(
		{
			"observed_demand_qty": demand_qty,
			"average_daily_demand": daily_demand,
			"last_demand_on": demand.get("last_demand_on"),
			"days_since_demand": days_since_demand,
			"stock_cover_days": cover_days,
			"stock_cover_review": _stock_cover_review(
				cover_days=cover_days,
				daily_demand=daily_demand,
				lookback_days=lookback_days,
			),
			"movement_class": classify_movement(
				demand_qty=demand_qty,
				lookback_days=lookback_days,
				days_since_demand=days_since_demand,
				thresholds=thresholds,
			),
			"configured_reorder_locations": cint(replenishment.get("configured_location_count")),
			"reorder_triggered_locations": cint(replenishment.get("triggered_location_count")),
			"reorder_rule_review_count": cint(replenishment.get("unavailable_rule_count")),
			"recommended_reorder_qty": flt(replenishment.get("recommended_reorder_qty")),
			"replenishment_status": replenishment.get("replenishment_status") or "No reorder rule",
		}
	)
	return result


def _stock_cover_review(*, cover_days: float | None, daily_demand: float, lookback_days: int) -> str:
	if daily_demand <= 0 or cover_days is None:
		return "No Demand Evidence"
	if cover_days > lookback_days:
		return "High Cover Review"
	return "Within Evidence Window"


def _columns(stock_columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		*stock_columns,
		{
			"fieldname": "observed_demand_qty",
			"label": _("Observed Demand"),
			"fieldtype": "Float",
		},
		{
			"fieldname": "average_daily_demand",
			"label": _("Avg Daily Demand"),
			"fieldtype": "Float",
		},
		{
			"fieldname": "last_demand_on",
			"label": _("Last Demand"),
			"fieldtype": "Date",
		},
		{
			"fieldname": "days_since_demand",
			"label": _("Days Since Demand"),
			"fieldtype": "Int",
		},
		{
			"fieldname": "stock_cover_days",
			"label": _("Estimated Stock Cover (Days)"),
			"fieldtype": "Float",
		},
		{
			"fieldname": "stock_cover_review",
			"label": _("Stock Cover Review"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "movement_class",
			"label": _("Movement Class"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "replenishment_status",
			"label": _("Replenishment Status"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "reorder_triggered_locations",
			"label": _("Reorder Locations"),
			"fieldtype": "Int",
		},
		{
			"fieldname": "recommended_reorder_qty",
			"label": _("Recommended Reorder Qty"),
			"fieldtype": "Float",
		},
	]


def _summary(rows: list[dict[str, Any]], *, show_costs: bool) -> list[dict[str, Any]]:
	cards = _stock_summary(rows, show_costs=show_costs)
	for movement_class, label in (
		("Fast", _("Fast-moving")),
		("Slow", _("Slow-moving")),
		("Non-moving", _("Non-moving")),
		("No demand in window", _("No Demand in Window")),
	):
		cards.append(
			{
				"label": label,
				"value": sum(1 for row in rows if row.get("movement_class") == movement_class),
				"datatype": "Int",
			}
		)
	cards.extend(
		[
			{
				"label": _("High Cover Review"),
				"value": sum(1 for row in rows if row.get("stock_cover_review") == "High Cover Review"),
				"datatype": "Int",
			},
			{
				"label": _("Items Requiring Reorder"),
				"value": sum(1 for row in rows if row.get("replenishment_status") == "Reorder Now"),
				"datatype": "Int",
			},
			{
				"label": _("Reorder Rules Requiring Review"),
				"value": sum(1 for row in rows if cint(row.get("reorder_rule_review_count")) > 0),
				"datatype": "Int",
			},
		]
	)
	return cards