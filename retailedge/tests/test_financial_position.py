from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.financial_position import _build_snapshot, _get_liquid_position, get_financial_position

APP_ROOT = Path(__file__).resolve().parents[1]


class TestFinancialPosition(unittest.TestCase):
	def test_snapshot_separates_current_position_from_period_metrics(self):
		owner = {
			"filters": {"company": "Demo", "branch": "", "from_date": "2026-08-01", "to_date": "2026-08-22"},
			"sections": {
				"receivables": {"available": True, "summary": [{"label": "Total Receivables", "value": 1200}]},
				"payables": {"available": True, "summary": [{"label": "Total Payables", "value": 700}]},
				"stock": {"available": True, "show_costs": True, "summary": [{"label": "Stock Value", "value": 5000}]},
				"profitability": {"available": True, "summary": [
					{"label": "Accounting Gross Profit", "value": 900},
					{"label": "Accounting Net Profit", "value": 650},
					{"label": "Transactional Gross Profit", "value": 1000},
				]},
				"cash": {"available": True, "summary": [
					{"label": "Money In", "value": 3000},
					{"label": "Money Out", "value": 2100},
					{"label": "Net Change", "value": 900},
				]},
			},
		}
		result = _build_snapshot(owner=owner, liquid={"available": True, "balance": 4000, "accounts": []})
		current = {card["label"]: card for card in result["current_position"]}
		period = {card["label"]: card for card in result["selected_period"]}
		self.assertEqual(current["Cash & Bank Balance"]["value"], 4000)
		self.assertEqual(current["Net Trade Position"]["value"], 500)
		self.assertEqual(current["Stock Value"]["value"], 5000)
		self.assertEqual(period["Net Cash Movement"]["value"], 900)
		self.assertEqual(period["Accounting Net Profit"]["value"], 650)
		self.assertEqual(current["Cash & Bank Balance"]["time_basis"], "current")
		self.assertEqual(period["Net Cash Movement"]["time_basis"], "period")

	def test_snapshot_hides_stock_value_when_cost_visibility_denies_it(self):
		owner = {
			"filters": {},
			"sections": {
				"receivables": {"available": True, "summary": []},
				"payables": {"available": True, "summary": []},
				"stock": {"available": True, "show_costs": False, "summary": [{"label": "Stock Value", "value": 9999}]},
			},
		}
		result = _build_snapshot(owner=owner, liquid={"available": True, "balance": 100, "accounts": []})
		self.assertNotIn("Stock Value", [card["label"] for card in result["current_position"]])

	def test_branch_scope_fails_closed_for_cash_and_bank_closing_balance(self):
		result = _get_liquid_position(company="Demo", branch="Aba")
		self.assertFalse(result["available"])
		self.assertIn("company-level", result["reason"])
		self.assertEqual(result["accounts"], [])

	@patch("retailedge.financial_position.require_dashboard_action", return_value={"can_view": True})
	@patch("retailedge.financial_position._get_liquid_position", return_value={"available": True, "balance": 500, "accounts": []})
	@patch("retailedge.financial_position.get_owner_dashboard_data")
	def test_service_composes_existing_reporting_services(self, owner_dashboard, liquid, capability):
		owner_dashboard.return_value = {
			"filters": {"company": "Demo", "branch": ""},
			"sections": {"receivables": {"available": True, "summary": []}, "payables": {"available": True, "summary": []}},
		}
		result = get_financial_position({"company": "Demo", "from_date": "2026-08-01", "to_date": "2026-08-22"})
		self.assertEqual(result["title"], "Financial Position Snapshot")
		owner_dashboard.assert_called_once()
		liquid.assert_called_once_with(company="Demo", branch="")
		capability.assert_called_once_with("owner-dashboard", "view", company="Demo", branch="")

	def test_source_contract_uses_erpnext_balance_helper_without_direct_sql(self):
		source = (APP_ROOT / "financial_position.py").read_text(encoding="utf-8")
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertIn("get_balance_on", source)
		self.assertIn("get_owner_dashboard_data", source)
		self.assertIn("MAX_LIQUID_ACCOUNT_SCAN", source)


if __name__ == "__main__":
	unittest.main()
