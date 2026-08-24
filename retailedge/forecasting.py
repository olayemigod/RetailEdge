from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from math import isfinite
from typing import Any

DEFAULT_TREND_WINDOW = 3
MAX_FORECAST_HORIZON = 12
MAX_HISTORY_PERIODS = 36
MIN_TREND_HISTORY_PERIODS = 3

PERIOD_MONTHLY = "Monthly"
PERIOD_WEEKLY = "Weekly"
SUPPORTED_PERIODS = {PERIOD_MONTHLY, PERIOD_WEEKLY}

METHOD_LAST_ACTUAL = "Last Actual"
METHOD_MOVING_AVERAGE_TREND = "Moving Average + Trend"


class ForecastValidationError(ValueError):
	"""Raised when a forecast request is ambiguous or unsafe to calculate."""


def build_baseline_forecast(
	history: list[dict[str, Any]],
	*,
	horizon: int,
	period: str = PERIOD_MONTHLY,
	as_of_date: str | date | None = None,
	trend_window: int = DEFAULT_TREND_WINDOW,
	floor: float | None = None,
) -> dict[str, Any]:
	"""Build an explainable deterministic forecast from already-authorised actuals.

	The caller owns business-source truth and permission scoping. This foundation
	only operates on explicit, contiguous historical periods. Missing periods are
	rejected rather than silently interpreted as zero.
	"""
	resolved_period = _validate_period(period)
	resolved_horizon = _validate_horizon(horizon)
	resolved_trend_window = _validate_trend_window(trend_window)
	resolved_as_of = _coerce_date(as_of_date) if as_of_date else None
	series = normalise_history(history, period=resolved_period, as_of_date=resolved_as_of)

	if not series:
		raise ForecastValidationError("At least one historical period is required.")

	values = [row["actual"] for row in series]
	last_period = series[-1]["period_start"]
	forecast_periods = _next_periods(last_period, resolved_horizon, resolved_period)

	if len(values) < MIN_TREND_HISTORY_PERIODS:
		method = METHOD_LAST_ACTUAL
		baseline = values[-1]
		trend = 0.0
		forecast_values = [baseline for _ in forecast_periods]
		fallback_reason = (
			f"Fewer than {MIN_TREND_HISTORY_PERIODS} historical periods; "
			"using the latest actual without inferred trend."
		)
	else:
		method = METHOD_MOVING_AVERAGE_TREND
		window = min(resolved_trend_window, len(values))
		baseline_values = values[-window:]
		baseline = sum(baseline_values) / len(baseline_values)

		diff_window = min(resolved_trend_window, len(values) - 1)
		diffs = [values[index] - values[index - 1] for index in range(len(values) - diff_window, len(values))]
		trend = sum(diffs) / len(diffs) if diffs else 0.0
		forecast_values = [baseline + (trend * step) for step in range(1, resolved_horizon + 1)]
		fallback_reason = None

	if floor is not None:
		resolved_floor = _finite_float(floor, "Forecast floor")
		forecast_values = [max(resolved_floor, value) for value in forecast_values]

	rows = [
		{
			"period_start": period_start.isoformat(),
			"forecast": float(value),
		}
		for period_start, value in zip(forecast_periods, forecast_values, strict=True)
	]

	return {
		"rows": rows,
		"metadata": {
			"method": method,
			"period": resolved_period,
			"history_periods": len(series),
			"history_start": series[0]["period_start"].isoformat(),
			"history_end": series[-1]["period_start"].isoformat(),
			"horizon": resolved_horizon,
			"trend_window": min(resolved_trend_window, len(values)),
			"baseline": float(baseline),
			"trend_per_period": float(trend),
			"fallback_reason": fallback_reason,
			"as_of_date": resolved_as_of.isoformat() if resolved_as_of else None,
			"missing_period_policy": "Reject; caller must supply explicit zero actuals where zero is business truth.",
			"actual_forecast_plan_separation": True,
		},
	}


def apply_plan_adjustment(
	forecast_rows: list[dict[str, Any]],
	*,
	adjustment_percent: float = 0.0,
	floor: float | None = None,
) -> list[dict[str, Any]]:
	"""Create plan values from forecast values without mutating the forecast."""
	adjustment = _finite_float(adjustment_percent, "Plan adjustment")
	if adjustment < -100 or adjustment > 1000:
		raise ForecastValidationError("Plan adjustment must be between -100% and 1000%.")
	resolved_floor = _finite_float(floor, "Plan floor") if floor is not None else None

	factor = 1 + (adjustment / 100)
	planned: list[dict[str, Any]] = []
	for row in forecast_rows:
		if "period_start" not in row or "forecast" not in row:
			raise ForecastValidationError("Each forecast row must contain period_start and forecast.")
		forecast_value = _finite_float(row["forecast"], f"Forecast for {row['period_start']}")
		value = forecast_value * factor
		if resolved_floor is not None:
			value = max(resolved_floor, value)
		# Suppress binary floating-point residue at the API contract boundary while
		# retaining substantially more precision than downstream currency rendering.
		value = round(value, 10)
		planned.append(
			{
				"period_start": str(row["period_start"]),
				"forecast": forecast_value,
				"plan": float(value),
				"plan_adjustment_percent": adjustment,
			}
		)
	return planned


def normalise_history(
	history: list[dict[str, Any]],
	*,
	period: str = PERIOD_MONTHLY,
	as_of_date: str | date | None = None,
) -> list[dict[str, Any]]:
	resolved_period = _validate_period(period)
	resolved_as_of = _coerce_date(as_of_date) if as_of_date else None
	if len(history) > MAX_HISTORY_PERIODS:
		raise ForecastValidationError(f"History is limited to {MAX_HISTORY_PERIODS} periods.")

	rows: list[dict[str, Any]] = []
	seen: set[date] = set()
	for raw in history:
		if "period_start" not in raw or "actual" not in raw:
			raise ForecastValidationError("Each history row must contain period_start and actual.")
		period_start = _coerce_date(raw["period_start"])
		_validate_period_boundary(period_start, resolved_period)
		if period_start in seen:
			raise ForecastValidationError(f"Duplicate historical period: {period_start.isoformat()}.")
		if resolved_as_of and period_start > resolved_as_of:
			raise ForecastValidationError(
				f"Historical period {period_start.isoformat()} is after the as-of date {resolved_as_of.isoformat()}."
			)
		seen.add(period_start)
		actual = _finite_float(raw["actual"], f"Actual for {period_start.isoformat()}")
		rows.append({"period_start": period_start, "actual": actual})

	rows.sort(key=lambda row: row["period_start"])
	for previous, current in zip(rows, rows[1:]):
		expected = _advance_period(previous["period_start"], resolved_period)
		if current["period_start"] != expected:
			raise ForecastValidationError(
				"Historical periods must be contiguous. "
				f"Expected {expected.isoformat()} after {previous['period_start'].isoformat()}, "
				f"got {current['period_start'].isoformat()}."
			)
	return rows


def _finite_float(value: Any, label: str) -> float:
	try:
		resolved = float(value)
	except (TypeError, ValueError) as exc:
		raise ForecastValidationError(f"{label} must be numeric.") from exc
	if not isfinite(resolved):
		raise ForecastValidationError(f"{label} must be finite.")
	return resolved


def _validate_period(period: str) -> str:
	resolved = str(period or "").strip().title()
	if resolved not in SUPPORTED_PERIODS:
		raise ForecastValidationError(f"Period must be one of: {', '.join(sorted(SUPPORTED_PERIODS))}.")
	return resolved


def _validate_horizon(horizon: int) -> int:
	try:
		resolved = int(horizon)
	except (TypeError, ValueError) as exc:
		raise ForecastValidationError("Forecast horizon must be a whole number.") from exc
	if resolved < 1 or resolved > MAX_FORECAST_HORIZON:
		raise ForecastValidationError(f"Forecast horizon must be between 1 and {MAX_FORECAST_HORIZON} periods.")
	return resolved


def _validate_trend_window(trend_window: int) -> int:
	try:
		resolved = int(trend_window)
	except (TypeError, ValueError) as exc:
		raise ForecastValidationError("Trend window must be a whole number.") from exc
	if resolved < 2 or resolved > 12:
		raise ForecastValidationError("Trend window must be between 2 and 12 periods.")
	return resolved


def _coerce_date(value: str | date | Any) -> date:
	if isinstance(value, date):
		return value
	try:
		return date.fromisoformat(str(value))
	except (TypeError, ValueError) as exc:
		raise ForecastValidationError(f"Invalid date: {value}.") from exc


def _validate_period_boundary(period_start: date, period: str) -> None:
	if period == PERIOD_MONTHLY and period_start.day != 1:
		raise ForecastValidationError("Monthly period_start values must use the first day of the month.")
	if period == PERIOD_WEEKLY and period_start.weekday() != 0:
		raise ForecastValidationError("Weekly period_start values must use Monday.")


def _next_periods(last_period: date, horizon: int, period: str) -> list[date]:
	result: list[date] = []
	current = last_period
	for _ in range(horizon):
		current = _advance_period(current, period)
		result.append(current)
	return result


def _advance_period(period_start: date, period: str) -> date:
	if period == PERIOD_WEEKLY:
		return period_start + timedelta(days=7)
	if period == PERIOD_MONTHLY:
		year = period_start.year + (1 if period_start.month == 12 else 0)
		month = 1 if period_start.month == 12 else period_start.month + 1
		return date(year, month, min(period_start.day, monthrange(year, month)[1]))
	raise ForecastValidationError(f"Unsupported period: {period}")
