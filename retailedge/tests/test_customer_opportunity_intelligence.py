from __future__ import annotations

import unittest

import frappe

from retailedge.customer_opportunity_intelligence import (
	_attention_status,
	_percent_change,
	_prior_period_filters,
	build_comparison_rows,
)


class TestCustomerOpportunityIntelligence(unittest.TestCase):
	def test_prior_period_is_immediately_preceding_equal_length_window(self):
		filters = frappe._dict(
			company="Example Co",
			from_date="2026-08-01",
			to_date="2026-08-31",
			invoice_kind="All",
		)
		prior = _prior_period_filters(filters)
		self.assertEqual(prior.from_date, "2026-07-01")
		self.assertEqual(prior.to_date, "2026-07-31")

	def test_no_current_purchase_is_follow_up_not_churn(self):
		prior = [
			frappe._dict(
				name="SINV-PRIOR-1",
				customer="CUST-1",
				customer_name="Customer One",
				base_net_total=1000,
				is_return=0,
			)
		]
		row = build_comparison_rows([], prior, receivables={}, change_threshold_percent=25)[0]
		keys = {signal["key"] for signal in row["signals"]}
		self.assertIn("no_current_purchase", keys)
		self.assertIn("declining_value", keys)
		self.assertIn("declining_frequency", keys)
		self.assertEqual(row["attention_status"], "Follow-up")

	def test_declining_value_and_frequency_use_configured_threshold(self):
		prior = [
			frappe._dict(name="P-1", customer="CUST-2", customer_name="Customer Two", base_net_total=1000, is_return=0),
			frappe._dict(name="P-2", customer="CUST-2", customer_name="Customer Two", base_net_total=1000, is_return=0),
		]
		current = [
			frappe._dict(name="C-1", customer="CUST-2", customer_name="Customer Two", base_net_total=1000, is_return=0),
		]
		row = build_comparison_rows(current, prior, receivables={}, change_threshold_percent=25)[0]
		self.assertEqual(row["value_change_percent"], -50)
		self.assertEqual(row["frequency_change_percent"], -50)
		keys = {signal["key"] for signal in row["signals"]}
		self.assertIn("declining_value", keys)
		self.assertIn("declining_frequency", keys)

	def test_growth_signals_are_opportunities(self):
		prior = [
			frappe._dict(name="P-3", customer="CUST-3", customer_name="Customer Three", base_net_total=500, is_return=0),
		]
		current = [
			frappe._dict(name="C-2", customer="CUST-3", customer_name="Customer Three", base_net_total=500, is_return=0),
			frappe._dict(name="C-3", customer="CUST-3", customer_name="Customer Three", base_net_total=500, is_return=0),
		]
		row = build_comparison_rows(current, prior, receivables={}, change_threshold_percent=25)[0]
		keys = {signal["key"] for signal in row["signals"]}
		self.assertIn("growing_value", keys)
		self.assertIn("growing_frequency", keys)
		self.assertEqual(row["attention_status"], "Opportunity")

	def test_returns_reduce_period_value_without_increasing_purchase_frequency(self):
		current = [
			frappe._dict(name="C-4", customer="CUST-4", customer_name="Customer Four", base_net_total=1000, is_return=0),
			frappe._dict(name="RET-4", customer="CUST-4", customer_name="Customer Four", base_net_total=-300, is_return=1),
		]
		row = build_comparison_rows(current, [], receivables={}, change_threshold_percent=25)[0]
		self.assertEqual(row["current_net_sales"], 700)
		self.assertEqual(row["current_return_value"], 300)
		self.assertEqual(row["current_purchase_count"], 1)

	def test_overdue_receivable_is_explicit_follow_up_signal(self):
		current = [
			frappe._dict(name="C-5", customer="CUST-5", customer_name="Customer Five", base_net_total=1000, is_return=0),
		]
		row = build_comparison_rows(
			current,
			[],
			receivables={"CUST-5": {"current_outstanding": 400, "overdue_outstanding": 250, "max_overdue_days": 40}},
			change_threshold_percent=25,
		)[0]
		keys = {signal["key"] for signal in row["signals"]}
		self.assertIn("overdue_receivable", keys)
		self.assertEqual(row["attention_status"], "Receivable Follow-up")

	def test_percent_change_requires_positive_prior_baseline(self):
		self.assertIsNone(_percent_change(100, 0))
		self.assertEqual(_percent_change(75, 100), -25)
		self.assertEqual(_percent_change(125, 100), 25)

	def test_retention_signal_takes_priority_over_receivable_and_opportunity(self):
		signals = [
			{"kind": "opportunity"},
			{"kind": "receivable"},
			{"kind": "retention"},
		]
		self.assertEqual(_attention_status(signals), "Follow-up")


if __name__ == "__main__":
	unittest.main()
