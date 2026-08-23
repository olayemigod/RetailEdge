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
from retailedge.stock_position import (
	DEFAULT_PAGE_SIZE,
	_build_stock_position_dataset,
	_coerce_filters,
	_page_response,
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


@frappe.whitelist()
def get_inventory_health(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	"""Compose current ERPNext Bin position with bounded observed demand evidence."""
	filters = _normalise_health_filters(filters)
	stock = _build_stock_position_dataset(filters)
	demand = get_historical_inventory_demand(filters)
	thresholds = _movement_thresholds(filters)
	lookback_days = cint(demand.get("scope", {}).get("lookback_days")) or DEFAULT_LOOKBACK_DAYS
	demand_by_item = {
		str(row.get("item_code")): row for row in demand.get("rows") or [] if row.get("item_code")
	}

	rows = [
		_enrich_stock_row(
			row,
			demand=demand_by_item.get(str(row.get("item_code") or "")),
			lookback_days=lookback_days,
			thresholds=thresholds,
		)
		for row in stock.get("rows") or []
	]
	movement_class = str(filters.get("movement_class") or "All").strip()
	if movement_class not in MOVEMENT_CLASSES:
		frappe.throw(_("Unsupported Movement Class filter."))
	if movement_class != "All":
		rows = [row for row in rows if row.get("movement_class") == movement_class]

	dataset = {
		"columns": _columns(stock.get("columns") or []),
		"rows": rows,
		"summary": _summary(rows, stock_summary=stock.get("summary") or []),
		"company_currency": stock.get("company_currency") or "",
		"show_costs": stock.get("show_costs") or 0,
		"scope": {
			**dict(stock.get("scope") or {}),
			"lookback_days": lookback_days,
			"from_date": demand.get("scope", {}).get("from_date"),
			"to_date": demand.get("scope", {}).get("to_date"),
			"movement_class": movement_class,
		},
		"scan": {
			"stock": stock.get("scan") or {},
			"demand": demand.get("scan") or {},
		},
		"metadata": {
			"current_stock_truth": "ERPNext Bin",
			"historical_demand_truth": demand.get("metadata") or {},
			"stock_cover_basis": "current available stock divided by observed average daily demand",
			"stock_cover_is_forecast": False,
			"movement_thresholds": {
				"slow_days": thresholds.slow_days,
				"non_moving_days": thresholds.non_moving_days,
				"fast_daily_demand": thresholds.fast_daily_demand,
			},
			"read_only": True,
			"persistent_derived_truth": False,
		},
	}
	return _page_response(dataset, page=page, page_size=page_size)


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


def _enrich_stock_row(
	stock_row: dict[str, Any],
	*,
	demand: dict[str, Any] | None,
	lookback_days: int,
	thresholds: MovementThresholds,
) -> dict[str, Any]:
	result = dict(stock_row)
	demand = demand or {}
	demand_qty = flt(demand.get("demand_qty"))
	daily_demand = flt(demand.get("average_daily_demand"))
	days_since_demand = demand.get("days_since_demand")
	result.update(
		{
			"observed_demand_qty": demand_qty,
			"average_daily_demand": daily_demand,
			"last_demand_on": demand.get("last_demand_on"),
			"days_since_demand": days_since_demand,
			"stock_cover_days": stock_cover_days(result.get("available_qty"), daily_demand),
			"movement_class": classify_movement(
				demand_qty=demand_qty,
				lookback_days=lookback_days,
				days_since_demand=days_since_demand,
				thresholds=thresholds,
			),
		}
	)
	return result


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
			"fieldname": "movement_class",
			"label": _("Movement Class"),
			"fieldtype": "Data",
		},
	]


def _summary(
	rows: list[dict[str, Any]],
	*,
	stock_summary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
	stock_labels = {
		"Items in Scope",
		"Available Items",
		"Out of Stock",
		"Negative Stock",
		"Fully Reserved",
		"Stock Value",
	}
	cards = [dict(card) for card in stock_summary if card.get("label") in stock_labels]
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
	return cards
