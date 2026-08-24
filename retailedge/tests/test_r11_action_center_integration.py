from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import action_center
from retailedge.action_follow_up import action_fingerprint
from retailedge.business_control_center import _build_business_control_center


_EMPTY_SUMMARY = {"summary": []}


class TestR11ActionCenterIntegration(FrappeTestCase):
	def setUp(self):
		frappe.session.user = "Administrator"

	@patch("retailedge.action_center.get_customer_sales_action_summary")
	@patch("retailedge.action_center.get_bank_exception_summary", return_value={"summary": [], "oldest_days": {}})
	@patch("retailedge.action_center.get_supplier_payables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_customer_receivables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_cash_shift_verification", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_expense_register", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_inventory_action_summary", return_value=_EMPTY_SUMMARY)
	def test_r11_actions_are_decorated_by_existing_follow_up_contract(
		self, stock, expenses, cash, receivables, payables, bank, r11
	):
		r11.return_value = {
			"items": [
				{
					"source": "r11_customer_opportunity",
					"label": "Customers need retention follow-up",
					"value": 3,
					"datatype": "Int",
					"severity": "warning",
					"route": "/app/customer-opportunity-intelligence",
					"time_basis": "period",
					"kind": "customer_retention_follow_up",
					"semantic_key": "customer_retention_follow_up",
					"target_type": "Page",
					"target": "customer-opportunity-intelligence",
					"open_mode": "same_tab",
				}
			],
			"metadata": {"receivables_excluded": True},
		}
		result = action_center.get_action_center_data(
			{"company": "Test Company", "branch": "", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		item = next(row for row in result["items"] if row["kind"] == "customer_retention_follow_up")
		expected = action_fingerprint(
			company="Test Company",
			branch="",
			source="r11_customer_opportunity",
			kind="customer_retention_follow_up",
			label="Customers need retention follow-up",
			route="/app/customer-opportunity-intelligence",
		)
		self.assertEqual(item["fingerprint"], expected)
		self.assertEqual(item["follow_up"]["effective_status"], "Open")
		self.assertTrue(result["sources"]["r11_customer_sales"]["available"])
		self.assertIn("customer_sales_provider", result["metadata"])

	def test_business_control_composition_keeps_r11_item_visible_for_follow_up_reresolution(self):
		r11_item = {
			"source": "r11_sales_quality",
			"label": "Sales invoices have high recorded price reduction",
			"value": 2,
			"datatype": "Int",
			"severity": "warning",
			"route": "/app/sales-quality-intelligence",
			"time_basis": "period",
			"kind": "high_price_reduction",
			"semantic_key": "high_price_reduction",
		}
		payload = _build_business_control_center(
			action_center={
				"filters": {"company": "Test Company", "branch": ""},
				"items": [r11_item],
				"summary": [],
				"sources": {},
				"metadata": {},
			},
			warnings={"warnings": [], "critical_count": 0, "warning_count": 0},
		)
		self.assertEqual(len(payload["items"]), 1)
		self.assertEqual(payload["items"][0]["source"], "r11_sales_quality")
		self.assertEqual(payload["items"][0]["semantic_key"], "high_price_reduction")

	@patch("retailedge.action_center.get_customer_sales_action_summary", side_effect=frappe.ValidationError("scope too broad"))
	@patch("retailedge.action_center.get_bank_exception_summary", return_value={"summary": [], "oldest_days": {}})
	@patch("retailedge.action_center.get_supplier_payables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_customer_receivables", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_cash_shift_verification", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_expense_register", return_value=_EMPTY_SUMMARY)
	@patch("retailedge.action_center.get_inventory_action_summary", return_value=_EMPTY_SUMMARY)
	def test_r11_validation_failure_isolated_from_action_center(
		self, stock, expenses, cash, receivables, payables, bank, r11
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		self.assertEqual(result["items"], [])
		self.assertFalse(result["sources"]["r11_customer_sales"]["available"])
		self.assertNotIn("scope too broad", result["sources"]["r11_customer_sales"]["reason"])
