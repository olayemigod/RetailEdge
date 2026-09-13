from __future__ import annotations

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from retailedge.customer_sales_action_summary import get_customer_sales_action_summary


class TestCustomerSalesActionSummary(FrappeTestCase):
	@patch("retailedge.customer_sales_action_summary.get_sales_quality_action_counts")
	@patch("retailedge.customer_sales_action_summary.get_customer_opportunity_action_counts")
	def test_provider_emits_only_non_duplicate_action_domains(self, opportunity, quality):
		opportunity.return_value = {"retention_follow_up": 3, "growth_opportunities": 2, "metadata": {}}
		quality.return_value = {
			"high_reduction_invoices": 4,
			"low_or_negative_margin_invoices": 1,
			"show_costs": 1,
			"metadata": {"lightweight_action_summary": True},
		}
		result = get_customer_sales_action_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		kinds = {item["kind"] for item in result["items"]}
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
		self.assertTrue(result["metadata"]["lightweight_summary"])

	@patch("retailedge.customer_sales_action_summary.get_sales_quality_action_counts")
	@patch("retailedge.customer_sales_action_summary.get_customer_opportunity_action_counts")
	def test_cost_restricted_sales_quality_does_not_emit_margin_action(self, opportunity, quality):
		opportunity.return_value = {"retention_follow_up": 0, "growth_opportunities": 0, "metadata": {}}
		quality.return_value = {
			"high_reduction_invoices": 2,
			"low_or_negative_margin_invoices": 0,
			"metadata": {},
			"show_costs": 0,
		}
		result = get_customer_sales_action_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)
		self.assertEqual([item["kind"] for item in result["items"]], ["high_price_reduction"])
		self.assertFalse(result["metadata"]["cost_visibility_applied"])

	@patch("retailedge.customer_sales_action_summary.get_sales_quality_action_counts")
	@patch("retailedge.customer_sales_action_summary.get_customer_opportunity_action_counts")
	def test_period_scope_is_part_of_r11_action_identity(self, opportunity, quality):
		opportunity.return_value = {"retention_follow_up": 1, "growth_opportunities": 0, "metadata": {}}
		quality.return_value = {
			"high_reduction_invoices": 0,
			"low_or_negative_margin_invoices": 0,
			"metadata": {},
			"show_costs": 0,
		}
		item = get_customer_sales_action_summary(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-24"}
		)["items"][0]
		self.assertEqual(item["fingerprint_scope"], "period:2026-08-01:2026-08-24")
		self.assertEqual(item["source"], "r11_customer_opportunity")
		self.assertEqual(item["semantic_key"], "customer_retention_follow_up")
		self.assertEqual(item["route"], "/app/customer-opportunity-intelligence")
