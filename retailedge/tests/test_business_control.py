from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.business_control import _build_control_snapshot, _control_items, _percent, get_business_control_data

APP_ROOT = Path(__file__).resolve().parents[1]


def _section(*cards, available=True):
	return {"available": available, "summary": list(cards)}


def _card(label, value, datatype="Currency"):
	return {"label": label, "value": value, "datatype": datatype}


class TestBusinessControl(unittest.TestCase):
	def test_snapshot_reuses_current_receivables_payables_and_period_cash(self):
		owner = {
			"filters": {"company": "Demo", "branch": "Aba", "from_date": "2026-08-01", "to_date": "2026-08-22"},
			"sections": {
				"receivables": _section(_card("Total Receivables", 5000), _card("Overdue", 3000), _card("Over 90 Days", 1000)),
				"payables": _section(_card("Total Payables", 2500), _card("Overdue", 500), _card("Over 90 Days", 100)),
				"cash": _section(_card("Money In", 7000), _card("Money Out", 4500), _card("Net Change", 2500)),
				"expenses": _section(_card("Total Expenses", 900)),
				"profitability": _section(_card("Accounting Net Profit", 1800), _card("Transactional Gross Profit", 2200)),
			},
		}
		result = _build_control_snapshot(owner)
		cards = {card["label"]: card for card in result["position"]}
		self.assertEqual(cards["Net Trade Position"]["value"], 2500)
		self.assertEqual(cards["Net Trade Position"]["time_basis"], "current")
		self.assertEqual(cards["Net Cash Movement"]["value"], 2500)
		self.assertEqual(cards["Net Cash Movement"]["time_basis"], "period")
		self.assertEqual(result["pressure"]["receivables_overdue_percent"], 60)
		self.assertEqual(result["pressure"]["payables_overdue_percent"], 20)

	def test_trade_position_is_not_mislabelled_as_cash_or_working_capital(self):
		result = _build_control_snapshot({"sections": {"receivables": _section(_card("Total Receivables", 900)), "payables": _section(_card("Total Payables", 400))}})
		labels = [card["label"] for card in result["position"]]
		self.assertIn("Net Trade Position", labels)
		self.assertNotIn("Working Capital", labels)
		self.assertIn("not cash, working capital or accounting net assets", result["metadata"]["trade_position_definition"])

	def test_controls_rank_critical_before_warning_without_double_counting_source_metrics(self):
		sections = {
			"receivables": _section(_card("Overdue", 5000), _card("Over 90 Days", 1000)),
			"payables": _section(_card("Overdue", 300), _card("Over 90 Days", 0)),
			"expenses": _section(_card("Posting Blocked", 2, "Int")),
			"stock": _section(_card("Negative Stock", 1, "Int")),
			"profitability": _section(_card("Negative Margin Items", 3, "Int"), _card("Low Margin Items", 4, "Int")),
		}
		controls = _control_items(sections)
		critical_count = sum(1 for row in controls if row["severity"] == "critical")
		self.assertGreater(critical_count, 0)
		self.assertTrue(all(row["severity"] == "critical" for row in controls[:critical_count]))
		self.assertEqual(len({row["key"] for row in controls}), len(controls))
		self.assertIn("receivables:Over 90 Days", {row["key"] for row in controls})
		self.assertIn("receivables:Overdue", {row["key"] for row in controls})

	def test_unavailable_or_hidden_sections_fail_closed_to_zero(self):
		owner = {
			"sections": {
				"receivables": _section(_card("Total Receivables", 5000), available=False),
				"payables": _section(_card("Total Payables", 1000), available=False),
				"profitability": _section(_card("Accounting Net Profit", 900), available=False),
			}
		}
		result = _build_control_snapshot(owner)
		cards = {card["label"]: card["value"] for card in result["position"]}
		self.assertEqual(cards["Receivables"], 0)
		self.assertEqual(cards["Payables"], 0)
		self.assertEqual(cards["Accounting Net Profit"], 0)
		self.assertEqual(result["controls"], [])

	def test_percent_does_not_invent_ratio_when_denominator_is_zero(self):
		self.assertIsNone(_percent(100, 0))
		self.assertEqual(_percent(25, 100), 25)

	@patch("retailedge.business_control.get_owner_dashboard_data")
	@patch("retailedge.business_control.require_dashboard_action", return_value={"can_view": True})
	def test_business_control_calls_existing_owner_composition_instead_of_business_tables(self, capability, owner_loader):
		owner_loader.return_value = {"filters": {"company": "Demo", "branch": "Aba"}, "sections": {}}
		result = get_business_control_data({"company": "Demo", "branch": "Aba", "from_date": "2026-08-01", "to_date": "2026-08-22"})
		capability.assert_called_once_with("owner-dashboard", "view", company="Demo", branch="Aba")
		owner_loader.assert_called_once_with({"company": "Demo", "branch": "Aba", "from_date": "2026-08-01", "to_date": "2026-08-22"})
		self.assertEqual(result["metadata"]["cash_basis"], "selected-period posted Cash/Bank GL movement, not closing cash balance")

	def test_source_contract_has_no_direct_business_table_queries_or_submitted_document_mutation(self):
		source = (APP_ROOT / "business_control.py").read_text(encoding="utf-8")
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("frappe.get_list", source)
		self.assertNotIn("db_set", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertIn("get_owner_dashboard_data", source)
		self.assertIn("require_dashboard_action", source)


if __name__ == "__main__":
	unittest.main()
