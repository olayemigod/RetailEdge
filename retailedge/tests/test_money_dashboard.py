from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.money_dashboard import (
	_attention_items,
	_headline_summary,
	get_money_dashboard_data,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestMoneyDashboard(unittest.TestCase):
	def test_headline_summary_keeps_period_flow_separate_from_current_positions(self):
		sections = {
			"cash": {
				"available": True,
				"summary": [
					{"label": "Money In", "value": 10000, "type": "Currency"},
					{"label": "Money Out", "value": 7500, "type": "Currency"},
					{"label": "Net Change", "value": 2500, "type": "Currency"},
				],
			},
			"receivables": {
				"available": True,
				"summary": [{"label": "Total Receivables", "value": 4000, "datatype": "Currency"}],
			},
			"payables": {
				"available": True,
				"summary": [{"label": "Total Payables", "value": 3000, "datatype": "Currency"}],
			},
		}
		cards = _headline_summary(sections)
		self.assertEqual(
			[card["label"] for card in cards],
			["Money In", "Money Out", "Period Net Change", "Receivables", "Payables"],
		)
		self.assertNotIn("Cash Balance", [card["label"] for card in cards])

	def test_attention_only_surfaces_positive_overdue_balances(self):
		sections = {
			"receivables": {
				"available": True,
				"summary": [
					{"label": "Overdue", "value": 2000, "datatype": "Currency"},
					{"label": "Over 90 Days", "value": 0, "datatype": "Currency"},
				],
			},
			"payables": {
				"available": True,
				"summary": [
					{"label": "Overdue", "value": 0, "datatype": "Currency"},
					{"label": "Over 90 Days", "value": 500, "datatype": "Currency"},
				],
			},
		}
		items = _attention_items(sections)
		self.assertEqual({item["metric"] for item in items}, {"Overdue", "Over 90 Days"})
		self.assertEqual(next(item for item in items if item["metric"] == "Over 90 Days")["tone"], "danger")

	@patch("retailedge.money_dashboard.require_dashboard_action", return_value={"can_view": True})
	@patch("retailedge.money_dashboard.get_supplier_payables")
	@patch("retailedge.money_dashboard.get_customer_receivables")
	@patch("retailedge.money_dashboard.get_cash_movement")
	def test_dashboard_composes_existing_money_services(self, cash, receivables, payables, capability):
		cash.return_value = {
			"summary": [{"label": "Net Change", "value": 1000, "type": "Currency"}],
			"rows": [{"voucher_no": "ACC-PAY-1"}],
		}
		receivables.return_value = {
			"summary": [{"label": "Total Receivables", "value": 2500, "datatype": "Currency"}],
			"rows": [{"invoice": "SINV-1"}],
		}
		payables.return_value = {
			"summary": [{"label": "Total Payables", "value": 1800, "datatype": "Currency"}],
			"rows": [{"invoice": "PINV-1"}],
		}
		result = get_money_dashboard_data(
			{"company": "Demo Company", "branch": "Aba", "from_date": "2026-08-01", "to_date": "2026-08-19"}
		)
		self.assertEqual(cash.call_count, 1)
		self.assertEqual(receivables.call_count, 1)
		self.assertEqual(payables.call_count, 1)
		capability.assert_called_once_with("money-overview", "view", company="Demo Company", branch="Aba")
		self.assertEqual(result["sections"]["cash"]["time_basis"], "selected_period")
		self.assertEqual(result["sections"]["receivables"]["time_basis"], "current_position")
		self.assertIn("not presented as a closing cash or bank balance", result["metadata"]["cash_balance_warning"])
		self.assertEqual(result["metadata"]["composition"], "existing_money_reporting_engines")

	def test_source_contract_does_not_query_money_tables_directly(self):
		source = (APP_ROOT / "money_dashboard.py").read_text(encoding="utf-8")
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("frappe.get_list", source)
		self.assertNotIn("frappe.get_all", source)
		self.assertIn("get_cash_movement", source)
		self.assertIn("get_customer_receivables", source)
		self.assertIn("get_supplier_payables", source)
		self.assertIn("require_dashboard_action", source)


if __name__ == "__main__":
	unittest.main()
