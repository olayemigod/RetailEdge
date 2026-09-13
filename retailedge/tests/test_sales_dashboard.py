from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.sales_dashboard import (
	_attention_items,
	_headline_summary,
	get_sales_dashboard_data,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSalesDashboard(unittest.TestCase):
	def test_headline_summary_comes_from_existing_report_cards(self):
		invoice = {
			"summary": [
				{"label": "Net Invoiced", "value": 10000, "datatype": "Currency"},
				{"label": "Invoices", "value": 20, "datatype": "Int"},
				{"label": "Returns", "value": 500, "datatype": "Currency"},
				{"label": "Net Outstanding", "value": 2500, "datatype": "Currency"},
			]
		}
		items = {"summary": [{"label": "Net Quantity", "value": 75, "datatype": "Float"}]}
		cards = _headline_summary(invoice, items)
		self.assertEqual(
			[card["label"] for card in cards],
			["Net Invoiced", "Invoices", "Returns", "Outstanding", "Net Quantity"],
		)

	def test_attention_only_surfaces_positive_returns_and_outstanding(self):
		invoice = {
			"summary": [
				{"label": "Returns", "value": 0, "datatype": "Currency"},
				{"label": "Net Outstanding", "value": 1500, "datatype": "Currency"},
			]
		}
		items = _attention_items(invoice)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["metric"], "Net Outstanding")
		self.assertEqual(items[0]["route"], "/app/sales-invoice-register")

	@patch("retailedge.sales_dashboard.require_dashboard_action", return_value={"can_view": True})
	@patch("retailedge.sales_dashboard.get_sales_by_item")
	@patch("retailedge.sales_dashboard.get_sales_invoice_register")
	def test_dashboard_composes_existing_sales_services(self, invoices, items, capability):
		invoices.return_value = {
			"summary": [{"label": "Net Invoiced", "value": 1000, "datatype": "Currency"}],
			"rows": [{"invoice": "SINV-0001"}],
			"columns": [{"fieldname": "invoice"}],
		}
		items.return_value = {
			"summary": [{"label": "Net Quantity", "value": 4, "datatype": "Float"}],
			"rows": [{"item_code": "ITEM-1", "net_sales": 1000}],
			"columns": [{"fieldname": "item_code"}],
		}
		result = get_sales_dashboard_data(
			{
				"company": "Demo Company",
				"branch": "Aba",
				"from_date": "2026-08-01",
				"to_date": "2026-08-19",
			}
		)
		self.assertEqual(invoices.call_count, 1)
		self.assertEqual(items.call_count, 1)
		capability.assert_called_once_with("sales-overview", "view", company="Demo Company", branch="Aba")
		self.assertEqual(result["recent_invoices"][0]["invoice"], "SINV-0001")
		self.assertEqual(result["top_items"][0]["item_code"], "ITEM-1")
		self.assertEqual(result["metadata"]["composition"], "existing_sales_reporting_engines")

	def test_source_contract_does_not_query_sales_tables_directly(self):
		source = (APP_ROOT / "sales_dashboard.py").read_text(encoding="utf-8")
		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("frappe.get_list", source)
		self.assertNotIn("frappe.get_all", source)
		self.assertIn("get_sales_invoice_register", source)
		self.assertIn("get_sales_by_item", source)
		self.assertIn("require_dashboard_action", source)


if __name__ == "__main__":
	unittest.main()
