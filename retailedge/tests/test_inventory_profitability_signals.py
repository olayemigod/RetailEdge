from __future__ import annotations

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
				"movement_class": "Fast",
				"stock_cover_days": 0,
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
			}
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


@patch("retailedge.inventory_profitability_signals.get_profitability_intelligence")
@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
def test_top_r8_profit_contributor_at_reorder_risk_is_flagged_without_new_margin_formula(inventory, profitability):
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

	risk = next(row for row in result["rows"] if row["kind"] == "top_profit_contributor_reorder")
	assert risk["item_code"] == "FAST-PROFIT"
	assert risk["severity"] == "danger"
	assert risk["gross_profit"] == 150000
	assert risk["recommended_reorder_qty"] == 20
	profitability.assert_called_once_with(
		{
			"company": "Test Company",
			"branch": "Main",
			"from_date": "2026-08-01",
			"to_date": "2026-08-23",
		}
	)
	assert result["scope"]["from_date"] == "2026-08-01"
	assert result["scope"]["to_date"] == "2026-08-23"
	assert result["scope"]["inventory_evidence_from_date"] == "2026-05-26"
	assert result["scope"]["inventory_evidence_to_date"] == "2026-08-23"
	assert "independently" in result["metadata"]["profitability_period_contract"]


@patch("retailedge.inventory_profitability_signals.get_profitability_intelligence")
@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
def test_r8_margin_leakage_combines_with_r10_slow_stock_classification(inventory, profitability):
	inventory.return_value = _inventory_payload()
	profitability.return_value = _profitability_payload()

	result = signals.get_inventory_profitability_signals({"company": "Test Company"})

	risk = next(row for row in result["rows"] if row["kind"] == "low_margin_slow_stock")
	assert risk["item_code"] == "LOW-SLOW"
	assert risk["gross_margin_percent"] == 5
	assert risk["movement_class"] == "Slow"
	assert risk["severity"] == "warning"
	profitability.assert_called_once_with({"company": "Test Company", "branch": ""})


@patch(
	"retailedge.inventory_profitability_signals.get_profitability_intelligence",
	side_effect=frappe.PermissionError,
)
@patch("retailedge.inventory_profitability_signals._build_inventory_health_dataset")
def test_cost_visibility_failure_returns_unavailable_without_profitability_rows(inventory, profitability):
	inventory.return_value = _inventory_payload()

	result = signals.get_inventory_profitability_signals(
		{
			"company": "Test Company",
			"from_date": "2026-08-01",
			"to_date": "2026-08-23",
		}
	)

	assert result["available"] is False
	assert result["rows"] == []
	assert result["summary"][0]["value"] == 0
	assert result["scope"]["from_date"] == "2026-08-01"
	assert result["scope"]["to_date"] == "2026-08-23"
	assert "cost visibility" in result["metadata"]["reason"].lower()


def test_source_contract_reuses_r8_and_r10_without_parallel_profit_math():
	text = Path(signals.__file__).read_text(encoding="utf-8")
	assert "get_profitability_intelligence" in text
	assert "_build_inventory_health_dataset" in text
	assert "R8 top_contributors" in text
	assert "R8 margin_leakage" in text
	assert "DEFAULT_LOW_MARGIN_PERCENT" not in text
	assert "incoming_rate" not in text
	assert "Sales Invoice Item" not in text
	assert "frappe.get_all" not in text
	assert "frappe.db.commit" not in text
	assert ".submit(" not in text
	assert ".insert(" not in text