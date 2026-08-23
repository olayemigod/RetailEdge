from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from frappe.utils import flt


@dataclass(frozen=True)
class MovementThresholds:
	"""Explicit R10 movement thresholds; callers own the business configuration."""

	slow_days: int
	non_moving_days: int
	fast_daily_demand: float | None = None

	def __post_init__(self) -> None:
		if self.slow_days < 0:
			raise ValueError("slow_days cannot be negative")
		if self.non_moving_days < self.slow_days:
			raise ValueError("non_moving_days must be greater than or equal to slow_days")
		if self.fast_daily_demand is not None and flt(self.fast_daily_demand) <= 0:
			raise ValueError("fast_daily_demand must be greater than zero when supplied")


def average_daily_demand(demand_qty: Any, lookback_days: int) -> float:
	"""Return observed daily demand for an explicit historical window."""
	if int(lookback_days or 0) <= 0:
		raise ValueError("lookback_days must be greater than zero")
	return max(flt(demand_qty), 0.0) / int(lookback_days)


def stock_cover_days(available_qty: Any, daily_demand: Any) -> float | None:
	"""Estimate cover from available stock and observed demand; this is not a forecast."""
	demand = flt(daily_demand)
	if demand <= 0:
		return None
	available = max(flt(available_qty), 0.0)
	return available / demand


def classify_stock_cover_review(
	*,
	cover_days: float | None,
	daily_demand: Any,
	evidence_window_days: int,
) -> str:
	"""Classify demand-backed stock cover without asserting that stock is overstocked.

	A high-cover review is raised only when the calculated cover is longer than
	the same historical evidence window used to derive observed daily demand.
	The result remains advisory and is not a demand forecast or maximum-stock rule.
	"""
	if int(evidence_window_days or 0) <= 0:
		raise ValueError("evidence_window_days must be greater than zero")
	if flt(daily_demand) <= 0 or cover_days is None:
		return "No Demand Evidence"
	if flt(cover_days) > int(evidence_window_days):
		return "High Cover Review"
	return "Within Evidence Window"


def classify_movement(
	*,
	demand_qty: Any,
	lookback_days: int,
	days_since_demand: int | None,
	thresholds: MovementThresholds,
) -> str:
	"""Classify observed demand without overstating what the history window proves.

	The caller supplies demand_qty after applying the agreed voucher semantics.
	A missing demand event is only "Non-moving" when the observed window is at
	least as long as the configured non-moving threshold; otherwise the evidence is
	labelled "No demand in window" rather than making a stronger claim.
	"""
	daily_demand = average_daily_demand(demand_qty, lookback_days)
	if days_since_demand is None:
		return (
			"Non-moving"
			if lookback_days >= thresholds.non_moving_days
			else "No demand in window"
		)
	if days_since_demand >= thresholds.non_moving_days:
		return "Non-moving"
	if days_since_demand >= thresholds.slow_days or daily_demand <= 0:
		return "Slow"
	if thresholds.fast_daily_demand is not None and daily_demand >= flt(thresholds.fast_daily_demand):
		return "Fast"
	return "Normal"


def reorder_signal(*, projected_qty: Any, reorder_level: Any, reorder_qty: Any = 0) -> dict[str, float | bool]:
	"""Mirror ERPNext v16 direct-warehouse reorder threshold semantics.

	ERPNext considers an Item Reorder row active when either the reorder level or
	configured reorder quantity is non-zero, and it triggers when projected stock is
	at or below the reorder level. The eventual requested quantity is at least the
	configured reorder quantity, but rises to the full deficiency when that is larger.

	This helper does not discover configuration, create Material Requests, or evaluate
	warehouse-group projected stock. Those concerns remain in the permission-aware
	R10E adapter.
	"""
	projected = flt(projected_qty)
	level = max(flt(reorder_level), 0.0)
	configured_qty = max(flt(reorder_qty), 0.0)
	configured = bool(level or configured_qty)
	at_or_below = projected <= level
	triggered = configured and at_or_below
	shortfall = max(level - projected, 0.0)
	recommended_qty = max(configured_qty, shortfall) if triggered else 0.0
	return {
		"configured": configured,
		"below_reorder_level": projected < level,
		"at_or_below_reorder_level": at_or_below,
		"reorder_triggered": triggered,
		"projected_qty": projected,
		"reorder_level": level,
		"reorder_qty": configured_qty,
		"shortfall_qty": shortfall,
		"recommended_reorder_qty": recommended_qty,
	}


def transfer_opportunity_quantity(
	*,
	source_available_qty: Any,
	target_available_qty: Any,
	source_protected_qty: Any,
	target_required_qty: Any,
) -> float:
	"""Return a safe advisory transfer quantity without creating any stock document."""
	source_surplus = max(flt(source_available_qty) - max(flt(source_protected_qty), 0.0), 0.0)
	target_shortfall = max(max(flt(target_required_qty), 0.0) - flt(target_available_qty), 0.0)
	return min(source_surplus, target_shortfall)