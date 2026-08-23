from __future__ import annotations

import unittest

from retailedge.inventory_intelligence import (
	MovementThresholds,
	average_daily_demand,
	classify_movement,
	reorder_signal,
	stock_cover_days,
	transfer_opportunity_quantity,
)


class TestInventoryIntelligenceMetrics(unittest.TestCase):
	def test_average_daily_demand_uses_explicit_positive_lookback(self):
		self.assertEqual(average_daily_demand(90, 30), 3)
		self.assertEqual(average_daily_demand(-5, 30), 0)
		with self.assertRaises(ValueError):
			average_daily_demand(10, 0)

	def test_stock_cover_is_historical_estimate_and_zero_demand_is_unavailable(self):
		self.assertEqual(stock_cover_days(15, 3), 5)
		self.assertEqual(stock_cover_days(0, 3), 0)
		self.assertEqual(stock_cover_days(-4, 3), 0)
		self.assertIsNone(stock_cover_days(15, 0))
		self.assertIsNone(stock_cover_days(15, -1))

	def test_movement_thresholds_are_explicit_and_validated(self):
		thresholds = MovementThresholds(slow_days=30, non_moving_days=90, fast_daily_demand=5)
		self.assertEqual(thresholds.slow_days, 30)
		with self.assertRaises(ValueError):
			MovementThresholds(slow_days=-1, non_moving_days=90)
		with self.assertRaises(ValueError):
			MovementThresholds(slow_days=90, non_moving_days=30)
		with self.assertRaises(ValueError):
			MovementThresholds(slow_days=30, non_moving_days=90, fast_daily_demand=0)

	def test_movement_classification_uses_demand_recency_not_generic_transfer_activity(self):
		thresholds = MovementThresholds(slow_days=30, non_moving_days=90, fast_daily_demand=5)
		self.assertEqual(
			classify_movement(
				demand_qty=180,
				lookback_days=30,
				days_since_demand=2,
				thresholds=thresholds,
			),
			"Fast",
		)
		self.assertEqual(
			classify_movement(
				demand_qty=30,
				lookback_days=30,
				days_since_demand=10,
				thresholds=thresholds,
			),
			"Normal",
		)
		self.assertEqual(
			classify_movement(
				demand_qty=30,
				lookback_days=30,
				days_since_demand=45,
				thresholds=thresholds,
			),
			"Slow",
		)
		self.assertEqual(
			classify_movement(
				demand_qty=0,
				lookback_days=30,
				days_since_demand=100,
				thresholds=thresholds,
			),
			"Non-moving",
		)

	def test_missing_demand_requires_long_enough_history_before_non_moving_label(self):
		thresholds = MovementThresholds(slow_days=30, non_moving_days=90, fast_daily_demand=5)
		self.assertEqual(
			classify_movement(
				demand_qty=0,
				lookback_days=30,
				days_since_demand=None,
				thresholds=thresholds,
			),
			"No demand in window",
		)
		self.assertEqual(
			classify_movement(
				demand_qty=0,
				lookback_days=90,
				days_since_demand=None,
				thresholds=thresholds,
			),
			"Non-moving",
		)

	def test_reorder_signal_matches_erpnext_v16_threshold_and_quantity_rules(self):
		below = reorder_signal(projected_qty=4, reorder_level=10, reorder_qty=20)
		self.assertTrue(below["configured"])
		self.assertTrue(below["below_reorder_level"])
		self.assertTrue(below["reorder_triggered"])
		self.assertEqual(below["shortfall_qty"], 6)
		self.assertEqual(below["recommended_reorder_qty"], 20)

		at_level = reorder_signal(projected_qty=10, reorder_level=10, reorder_qty=20)
		self.assertFalse(at_level["below_reorder_level"])
		self.assertTrue(at_level["at_or_below_reorder_level"])
		self.assertTrue(at_level["reorder_triggered"])
		self.assertEqual(at_level["recommended_reorder_qty"], 20)

		deficiency_larger = reorder_signal(projected_qty=-5, reorder_level=10, reorder_qty=4)
		self.assertEqual(deficiency_larger["shortfall_qty"], 15)
		self.assertEqual(deficiency_larger["recommended_reorder_qty"], 15)

		healthy = reorder_signal(projected_qty=15, reorder_level=10, reorder_qty=20)
		self.assertFalse(healthy["reorder_triggered"])
		self.assertEqual(healthy["recommended_reorder_qty"], 0)

		inactive_zero_rule = reorder_signal(projected_qty=0, reorder_level=0, reorder_qty=0)
		self.assertFalse(inactive_zero_rule["configured"])
		self.assertFalse(inactive_zero_rule["reorder_triggered"])

	def test_transfer_quantity_protects_source_and_only_fills_target_shortfall(self):
		self.assertEqual(
			transfer_opportunity_quantity(
				source_available_qty=100,
				target_available_qty=5,
				source_protected_qty=40,
				target_required_qty=25,
			),
			20,
		)
		self.assertEqual(
			transfer_opportunity_quantity(
				source_available_qty=50,
				target_available_qty=0,
				source_protected_qty=40,
				target_required_qty=25,
			),
			10,
		)
		self.assertEqual(
			transfer_opportunity_quantity(
				source_available_qty=30,
				target_available_qty=0,
				source_protected_qty=40,
				target_required_qty=25,
			),
			0,
		)
		self.assertEqual(
			transfer_opportunity_quantity(
				source_available_qty=100,
				target_available_qty=30,
				source_protected_qty=40,
				target_required_qty=25,
			),
			0,
		)


if __name__ == "__main__":
	unittest.main()
