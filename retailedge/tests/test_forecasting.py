from __future__ import annotations

import unittest

from retailedge.forecasting import (
	METHOD_LAST_ACTUAL,
	METHOD_MOVING_AVERAGE_TREND,
	ForecastValidationError,
	apply_plan_adjustment,
	build_baseline_forecast,
	normalise_history,
)


class TestForecastingFoundation(unittest.TestCase):
	def test_insufficient_history_uses_latest_actual_without_inferred_trend(self):
		result = build_baseline_forecast(
			[
				{"period_start": "2026-06-01", "actual": 100},
				{"period_start": "2026-07-01", "actual": 140},
			],
			horizon=2,
			as_of_date="2026-07-31",
		)
		self.assertEqual(result["metadata"]["method"], METHOD_LAST_ACTUAL)
		self.assertEqual(result["metadata"]["trend_per_period"], 0)
		self.assertEqual(
			result["rows"],
			[
				{"period_start": "2026-08-01", "forecast": 140.0},
				{"period_start": "2026-09-01", "forecast": 140.0},
			],
		)

	def test_three_or_more_periods_use_explainable_moving_average_and_trend(self):
		result = build_baseline_forecast(
			[
				{"period_start": "2026-05-01", "actual": 100},
				{"period_start": "2026-06-01", "actual": 120},
				{"period_start": "2026-07-01", "actual": 140},
			],
			horizon=2,
			as_of_date="2026-07-31",
		)
		self.assertEqual(result["metadata"]["method"], METHOD_MOVING_AVERAGE_TREND)
		self.assertEqual(result["metadata"]["baseline"], 120)
		self.assertEqual(result["metadata"]["trend_per_period"], 20)
		self.assertEqual(result["rows"][0]["forecast"], 140)
		self.assertEqual(result["rows"][1]["forecast"], 160)

	def test_future_history_is_rejected_by_as_of_date(self):
		with self.assertRaisesRegex(ForecastValidationError, "after the as-of date"):
			build_baseline_forecast(
				[
					{"period_start": "2026-07-01", "actual": 100},
					{"period_start": "2026-08-01", "actual": 120},
				],
				horizon=1,
				as_of_date="2026-07-31",
			)

	def test_missing_period_is_not_silently_treated_as_zero(self):
		with self.assertRaisesRegex(ForecastValidationError, "must be contiguous"):
			normalise_history(
				[
					{"period_start": "2026-05-01", "actual": 100},
					{"period_start": "2026-07-01", "actual": 140},
				]
			)

	def test_explicit_zero_period_is_valid_business_truth(self):
		rows = normalise_history(
			[
				{"period_start": "2026-05-01", "actual": 100},
				{"period_start": "2026-06-01", "actual": 0},
				{"period_start": "2026-07-01", "actual": 140},
			]
		)
		self.assertEqual(rows[1]["actual"], 0)

	def test_plan_adjustment_preserves_forecast_and_returns_separate_plan(self):
		forecast_rows = [{"period_start": "2026-08-01", "forecast": 100.0}]
		planned = apply_plan_adjustment(forecast_rows, adjustment_percent=15)
		self.assertEqual(forecast_rows, [{"period_start": "2026-08-01", "forecast": 100.0}])
		self.assertEqual(planned[0]["forecast"], 100)
		self.assertEqual(planned[0]["plan"], 115)
		self.assertEqual(planned[0]["plan_adjustment_percent"], 15)

	def test_floor_is_opt_in_so_profit_forecasts_can_remain_negative(self):
		history = [
			{"period_start": "2026-05-01", "actual": 20},
			{"period_start": "2026-06-01", "actual": 0},
			{"period_start": "2026-07-01", "actual": -20},
		]
		unfloored = build_baseline_forecast(history, horizon=1)
		floored = build_baseline_forecast(history, horizon=1, floor=0)
		self.assertLess(unfloored["rows"][0]["forecast"], 0)
		self.assertEqual(floored["rows"][0]["forecast"], 0)

	def test_weekly_periods_must_start_on_monday(self):
		with self.assertRaisesRegex(ForecastValidationError, "must use Monday"):
			normalise_history(
				[{"period_start": "2026-08-04", "actual": 100}],
				period="Weekly",
			)

	def test_horizon_is_bounded(self):
		with self.assertRaisesRegex(ForecastValidationError, "between 1 and 12"):
			build_baseline_forecast(
				[{"period_start": "2026-07-01", "actual": 100}],
				horizon=13,
			)

	def test_duplicate_period_is_rejected(self):
		with self.assertRaisesRegex(ForecastValidationError, "Duplicate historical period"):
			normalise_history(
				[
					{"period_start": "2026-07-01", "actual": 100},
					{"period_start": "2026-07-01", "actual": 120},
				]
			)


if __name__ == "__main__":
	unittest.main()
