from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import inventory_profitability_signals as signals


def _inventory_payload():
	return {
		"rows": [
			{
				"item_code": "FAST-PROFIT",
				"item_name": "Fast Profit",
				"item_group": "Products",
				"actual_qty": 0,
				"available_qty": 0,
				"stock_status": "Out of Stock",
				"movement_class": "Normal",
				"stock_cover_days": 0,
				"replenishment_status": "No reorder rule",
				"recommended_reorder_qty": 0,
			},
			{
				"item_code": "PROFIT-REORDER",
				"item_name": "Profit Reorder",
				"item_group": "Products",
				"actual_qty": 12,
				"available_qty": 12,
				"stock_status": "Available",
				"movement_class": "Normal",
				"stock_cover_days": 12,
				"replenishment_status": "Reorder Now",
				"recommended_reorder_qty": 20,
			},
			{
				"item_code": "LOW-SLOW",
				"item_name": "Low Slow",
				"item_group": "Products",
				"actual_qty": 15,
				"available_qty": 15,
				"stock_status": "Available",
				"movement_class": "Slow",
				"stock_cover_days": 120,
				"replenishment_status": "Healthy",
				"recommended_reorder_qty": 0,
			},
		],
		"scope": {
			"company": "Test Company",
			"branch": "Main",
			"from_date": "2026-05-26",
			"to_date": "2026-08-23",
		},
	}


def _profitability_payload():
	return {
		"top_contributors": [
			{
				"item_code": "FAST-PROFIT",
				"net_sales": 500000,
				"gross_profit": 150000,
				"gross_margin_percent": 30,
			},
			{
				"item_code": "PROFIT-REORDER",
				"net_sales": 350000,
				"gross_profit": 90000,
				"gross_margin_percent": 25.7,
			},
		],
		"margin_leakage": [
			{
				"item_code": "LOW-SLOW",
				"net_sales": 100000,
				"gross_profit": 5000,
				"gross_margin_percent": 5,
			}
		],
		"scope": {
			"company": "Test Company",
			"branch": "Main",
			"from_date": "2026-08-01",
			"to_date": "2026-08-23",
		},
		"metadata": {"financial_truth": "ERPNext Profit and Loss Statement / Gross and Net Profit Report"},
	}


class TestInventoryProfitabilitySignals(unittest.TestCase):
	@patch("retailedge.inventory_profitability_signals.get_profitability_intelligence")
	@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
	def test_top_r8_profit_contributor_stockout_is_flagged_without_reorder_rule(
		self, inventory, profitability
	):
		inventory.return_value = _inventory_payload()
		profitability.return_value = _profitability_payload()

		result = signals.get_inventory_profitability_signals(
			{
				"company": "Test Company",
				"branch": "Main",
				"lookback_days": 90,
				"from_date": "2026-08-01",
				"to_date": "2026-08-23",
			}
		)

		risk = next(row for row in result["rows"] if row["kind"] == "top_profit_contributor_stockout")
		self.assertEqual(risk["item_code"], "FAST-PROFIT")
		self.assertEqual(risk["severity"], "danger")
		self.assertEqual(risk["gross_profit"], 150000)
		self.assertEqual(risk["replenishment_status"], "No reorder rule")
		self.assertEqual(risk["recommended_reorder_qty"], 0)
		profitability.assert_called_once_with(
			{
				"company": "Test Company",
				"branch": "Main",
				"from_date": "2026-08-01",
				"to_date": "2026-08-23",
			}
		)
		self.assertEqual(result["scope"]["from_date"], "2026-08-01")
		self.assertEqual(result["scope"]["to_date"], "2026-08-23")
		self.assertEqual(result["scope"]["inventory_evidence_from_date"], "2026-05-26")
		self.assertEqual(result["scope"]["inventory_evidence_to_date"], "2026-08-23")
		self.assertIn("independently", result["metadata"]["profitability_period_contract"])
		self.assertIn("even when no ERPNext reorder rule", result["metadata"]["stockout_contract"])

	@patch("retailedge.inventory_profitability_signals.get_profitability_intelligence")
	@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
	def test_top_r8_profit_contributor_reorder_signal_remains_when_stock_is_available(
		self, inventory, profitability
	):
		inventory.return_value = _inventory_payload()
		profitability.return_value = _profitability_payload()

		result = signals.get_inventory_profitability_signals({"company": "Test Company"})

		risk = next(row for row in result["rows"] if row["kind"] == "top_profit_contributor_reorder")
		self.assertEqual(risk["item_code"], "PROFIT-REORDER")
		self.assertEqual(risk["severity"], "warning")
		self.assertEqual(risk["recommended_reorder_qty"], 20)

	@patch("retailedge.inventory_profitability_signals.get_profitability_intelligence")
	@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
	def test_r8_margin_leakage_combines_with_r10_slow_stock_classification(
		self, inventory, profitability
	):
		inventory.return_value = _inventory_payload()
		profitability.return_value = _profitability_payload()

		result = signals.get_inventory_profitability_signals({"company": "Test Company"})

		risk = next(row for row in result["rows"] if row["kind"] == "low_margin_slow_stock")
		self.assertEqual(risk["item_code"], "LOW-SLOW")
		self.assertEqual(risk["gross_margin_percent"], 5)
		self.assertEqual(risk["movement_class"], "Slow")
		self.assertEqual(risk["severity"], "warning")
		profitability.assert_called_once_with({"company": "Test Company", "branch": ""})

	@patch(
		"retailedge.inventory_profitability_signals.get_profitability_intelligence",
		side_effect=frappe.PermissionError,
	)
	@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
	def test_cost_visibility_failure_returns_unavailable_without_profitability_rows(
		self, inventory, profitability
	):
		inventory.return_value = _inventory_payload()

		result = signals.get_inventory_profitability_signals(
			{
				"company": "Test Company",
				"from_date": "2026-08-01",
				"to_date": "2026-08-23",
			}
		)

		self.assertFalse(result["available"])
		self.assertEqual(result["rows"], [])
		self.assertEqual(result["summary"][0]["value"], 0)
		self.assertEqual(result["scope"]["from_date"], "2026-08-01")
		self.assertEqual(result["scope"]["to_date"], "2026-08-23")
		self.assertIn("cost visibility", result["metadata"]["reason"].lower())

	def test_source_contract_reuses_r8_and_r10_without_parallel_profit_math(self):
		text = Path(signals.__file__).read_text(encoding="utf-8")
		self.assertIn("get_profitability_intelligence", text)
		self.assertIn("_build_inventory_health_dataset", text)
		self.assertIn("R8 top_contributors", text)
		self.assertIn("R8 margin_leakage", text)
		self.assertNotIn("DEFAULT_LOW_MARGIN_PERCENT", text)
		self.assertNotIn("incoming_rate", text)
		self.assertNotIn("Sales Invoice Item", text)
		self.assertNotIn("frappe.get_all", text)
		self.assertNotIn("frappe.db.commit", text)
		self.assertNotIn(".submit(", text)
		self.assertNotIn(".insert(", text)


if __name__ == "__main__":
	unittest.main()
