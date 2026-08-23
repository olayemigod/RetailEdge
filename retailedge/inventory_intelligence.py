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


def classify_movement(
	*,
	demand_qty: Any,
	lookback_days: int,
	days_since_demand: int | None,
	thresholds: MovementThresholds,
) -> str:
	"""Classify observed demand without treating internal transfers as demand.

	The caller supplies demand_qty after applying the agreed voucher semantics.
	Threshold values are explicit inputs so R10 does not hide policy constants.
	"""
	daily_demand = average_daily_demand(demand_qty, lookback_days)
	if days_since_demand is None or days_since_demand >= thresholds.non_moving_days:
		return "Non-moving"
	if days_since_demand >= thresholds.slow_days or daily_demand <= 0:
		return "Slow"
	if thresholds.fast_daily_demand is not None and daily_demand >= flt(thresholds.fast_daily_demand):
		return "Fast"
	return "Normal"


def reorder_signal(*, projected_qty: Any, reorder_level: Any, reorder_qty: Any = 0) -> dict[str, float | bool]:
	"""Compare ERPNext-provided reorder configuration with ERPNext projected quantity.

	This helper does not discover or persist reorder configuration. R10E must first
	resolve the installed ERPNext v16 Item reorder schema safely.
	"""
	projected = flt(projected_qty)
	level = max(flt(reorder_level), 0.0)
	configured_qty = max(flt(reorder_qty), 0.0)
	below_level = projected < level
	shortfall = max(level - projected, 0.0)
	return {
		"below_reorder_level": below_level,
		"projected_qty": projected,
		"reorder_level": level,
		"reorder_qty": configured_qty,
		"shortfall_qty": shortfall,
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
