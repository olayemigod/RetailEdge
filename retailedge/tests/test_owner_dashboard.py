from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.owner_dashboard import _attention_items, _headline_summary, _safe_section, get_owner_dashboard_data

APP_ROOT = Path(__file__).resolve().parents[1]


class TestOwnerDashboard(unittest.TestCase):
	def test_safe_section_preserves_source_summary(self):
		payload = _safe_section(
			"Sales",
			lambda: {"summary": [{"label": "Net Sales", "value": 1250}], "scope": {"branch": "Aba"}},
			"/app/sales-invoice-register",
		)
		self.assertTrue(payload["available"])
		self.assertEqual(payload["summary"][0]["value"], 1250)
		self.assertEqual(payload["scope"]["branch"], "Aba")

	def test_safe_section_hides_permission_denied_source(self):
		def denied():
			raise frappe.PermissionError

		payload = _safe_section("Cash Movement", denied, "/app/cash-movement")
		self.assertFalse(payload["available"])
		self.assertIn("permissions", payload["reason"])

	def test_headline_summary_uses_source_cards_and_respects_hidden_stock_value(self):
		sections = {
			"sales": {"available": True, "summary": [{"label": "Net Invoiced", "value": 5000, "datatype": "Currency"}]},
			"expenses": {"available": True, "summary": [{"label": "Total Expenses", "value": 900, "type": "Currency"}]},
			"receivables": {"available": True, "summary": [{"label": "Total Receivables", "value": 1200, "datatype": "Currency"}]},
			"payables": {"available": True, "summary": [{"label": "Total Payables", "value": 700, "datatype": "Currency"}]},
			"stock": {"available": True, "show_costs": False, "summary": [{"label": "Items in Scope", "value": 15, "datatype": "Int"}]},
		}
		cards = _headline_summary(sections)
		self.assertEqual([card["label"] for card in cards], ["Sales", "Expenses", "Receivables", "Payables"])
		self.assertNotIn("Stock Value", [card["label"] for card in cards])

	def test_attention_only_surfaces_positive_existing_exception_metrics(self):
		sections = {
			"expenses": {"available": True, "summary": [
				{"label": "Posting Blocked", "value": 2, "type": "Int"},
				{"label": "Submitted for Review", "value": 0, "type": "Int"},
			]},
			"receivables": {"available": True, "summary": [
				{"label": "Overdue", "value": 2500, "datatype": "Currency"},
				{"label": "Over 90 Days", "value": 0, "datatype": "Currency"},
			]},
			"stock": {"available": True, "summary": [
				{"label": "Negative Stock", "value": 1, "datatype": "Int"},
				{"label": "Out of Stock", "value": 0, "datatype": "Int"},
			]},
		}
		items = _attention_items(sections)
		self.assertEqual({item["metric"] for item in items}, {"Posting Blocked", "Overdue", "Negative Stock"})
		self.assertEqual(next(item for item in items if item["metric"] == "Negative Stock")["tone"], "danger")

	@patch("retailedge.owner_dashboard.require_dashboard_action", return_value={"can_view": True})
	@patch("retailedge.owner_dashboard.get_branch_performance_dashboard_data", return_value={"summary": []})
	@patch("retailedge.owner_dashboard.get_stock_position", return_value={"summary": [], "show_costs": 0})
	@patch("retailedge.owner_dashboard.get_supplier_payables", return_value={"summary": []})
	@patch("retailedge.owner_dashboard.get_customer_receivables", return_value={"summary": []})
	@patch("retailedge.owner_dashboard.get_cash_movement", return_value={"summary": []})
	@patch("retailedge.owner_dashboard.get_expense_register", return_value={"summary": []})
	@patch("retailedge.owner_dashboard.get_sales_invoice_register", return_value={"summary": []})
	def test_dashboard_composes_existing_report_services(
		self,
		sales,
		expenses,
		cash,
		receivables,
		payables,
		stock,
		branches,
		capability,
	):
		result = get_owner_dashboard_data(
			{"company": "Demo Company", "branch": "Aba", "from_date": "2026-08-01", "to_date": "2026-08-18"}
		)
		self.assertEqual(
			set(result["sections"]),
			{"sales", "expenses", "cash", "receivables", "payables", "stock", "branches"},
		)
		self.assertFalse(result["sections"]["stock"]["show_costs"])
		self.assertIn("headline_summary", result)
		self.assertIn("attention", result)
		for mock in (sales, expenses, cash, receivables, payables, stock, branches):
			self.assertEqual(mock.call_count, 1)
		capability.assert_called_once_with("owner-dashboard", "view", company="Demo Company", branch="Aba")
		self.assertEqual(result["metadata"]["composition"], "existing_retailedge_reporting_engines")

	def test_source_contract_does_not_query_business_tables_directly(self):
		source = (APP_ROOT / "owner_dashboard.py").read_text(encoding="utf-8")
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("frappe.get_list", source)
		self.assertIn("require_dashboard_action", source)
		self.assertIn("get_sales_invoice_register", source)
		self.assertIn("get_expense_register", source)
		self.assertIn("get_cash_movement", source)
		self.assertIn("get_customer_receivables", source)
		self.assertIn("get_supplier_payables", source)
		self.assertIn("get_stock_position", source)
		self.assertIn("get_branch_performance_dashboard_data", source)


if __name__ == "__main__":
	unittest.main()
