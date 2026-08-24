from __future__ import annotations

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from retailedge.customer_sales_action_summary import get_customer_sales_action_summary


class TestCustomerSalesActionSummary(FrappeTestCase):
	@patch("retailedge.customer_sales_action_summary.get_sales_quality_intelligence")
	@patch("retailedge.customer_sales_action_summary.get_customer_opportunity_intelligence")
	def test_provider_emits_only_non_duplicate_action_domains(self, opportunity, quality):
		opportunity.return_value = {
			"summary": [
				{"label": "Retention Follow-up", "value": 3},
				{"label": "Receivable Follow-up", "value": 9},
				{"label": "Growth Opportunities", "value": 2},
			],
			"metadata": {"sales_truth": "Submitted ERPNext Sales Invoice"},
		}
		quality.return_value = {
			"summary": [
				{"label": "High Reduction Invoices", "value": 4},
				{"label": "Low / Negative Margin Invoices", "value": 1},
			],
			"metadata": {"sales_truth": "Submitted ERPNext Sales Invoice / Sales Invoice Item"},
			"show_costs": 1,
		}

		result = get_customer_sales_action_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		items = result["items"]
		kinds = {item["kind"] for item in items}
		self.assertEqual(
			kinds,
			{
				"customer_retention_follow_up",
				"customer_growth_opportunity",
				"high_price_reduction",
				"low_or_negative_transactional_margin",
			},
		)
		self.assertNotIn("overdue_receivable", kinds)
		self.assertTrue(result["metadata"]["receivables_excluded"])
		self.assertFalse(result["metadata"]["basket_affinity_actionable"])

	@patch("retailedge.customer_sales_action_summary.get_sales_quality_intelligence")
	@patch("retailedge.customer_sales_action_summary.get_customer_opportunity_intelligence")
	def test_cost_restricted_sales_quality_does_not_emit_margin_action(self, opportunity, quality):
		opportunity.return_value = {"summary": [], "metadata": {}}
		quality.return_value = {
			"summary": [{"label": "High Reduction Invoices", "value": 2}],
			"metadata": {},
			"show_costs": 0,
		}
		result = get_customer_sales_action_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		self.assertEqual([item["kind"] for item in result["items"]], ["high_price_reduction"])
		self.assertFalse(result["metadata"]["cost_visibility_applied"])

	@patch("retailedge.customer_sales_action_summary.get_sales_quality_intelligence")
	@patch("retailedge.customer_sales_action_summary.get_customer_opportunity_intelligence")
	def test_action_identity_is_stable_and_routes_to_edgesuite_pages(self, opportunity, quality):
		opportunity.return_value = {
			"summary": [{"label": "Retention Follow-up", "value": 1}],
			"metadata": {},
		}
		quality.return_value = {"summary": [], "metadata": {}, "show_costs": 0}
		item = get_customer_sales_action_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)["items"][0]
		self.assertEqual(item["source"], "r11_customer_opportunity")
		self.assertEqual(item["semantic_key"], "customer_retention_follow_up")
		self.assertEqual(item["route"], "/app/customer-opportunity-intelligence")
		self.assertEqual(item["target_type"], "Page")
		self.assertEqual(item["open_mode"], "same_tab")
