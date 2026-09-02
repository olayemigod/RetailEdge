from __future__ import annotations

from unittest import TestCase

from retailedge.professional_purchasing import (
	_attention_summary,
	_classify_purchase_order_attention,
)


class TestProfessionalPurchasingAttention(TestCase):
	def test_overdue_receipt_uses_supplied_server_date(self):
		result = _classify_purchase_order_attention(
			{
				"docstatus": 1,
				"status": "To Receive and Bill",
				"schedule_date": "2026-08-29",
				"per_received": 25,
				"per_billed": 25,
			},
			today="2026-08-30",
		)
		self.assertIn("overdue_receipt", {flag["key"] for flag in result["attention_flags"]})
		self.assertEqual(result["attention_level"], "Review")

	def test_received_not_fully_billed_is_read_only_exception(self):
		result = _classify_purchase_order_attention(
			{
				"docstatus": 1,
				"status": "To Bill",
				"schedule_date": "2026-09-05",
				"per_received": 100,
				"per_billed": 60,
			},
			today="2026-08-30",
		)
		flags = {flag["key"]: flag for flag in result["attention_flags"]}
		self.assertIn("received_not_billed", flags)
		self.assertEqual(flags["received_not_billed"]["kind"], "exception")

	def test_billed_ahead_of_receipt_is_review_not_accounting_error(self):
		result = _classify_purchase_order_attention(
			{
				"docstatus": 1,
				"status": "To Receive",
				"schedule_date": "2026-09-05",
				"per_received": 20,
				"per_billed": 80,
			},
			today="2026-08-30",
		)
		flags = {flag["key"]: flag for flag in result["attention_flags"]}
		self.assertEqual(flags["billed_ahead_of_receipt"]["kind"], "review")
		self.assertIn("ready_to_receive", flags)

	def test_draft_and_closed_orders_do_not_raise_active_attention(self):
		for row in (
			{"docstatus": 0, "status": "Draft", "schedule_date": "2026-08-01", "per_received": 0, "per_billed": 0},
			{"docstatus": 1, "status": "Closed", "schedule_date": "2026-08-01", "per_received": 0, "per_billed": 0},
			{"docstatus": 1, "status": "Completed", "schedule_date": "2026-08-01", "per_received": 100, "per_billed": 100},
		):
			result = _classify_purchase_order_attention(row, today="2026-08-30")
			self.assertEqual(result["attention_flags"], [])
			self.assertEqual(result["attention_level"], "Clear")

	def test_summary_counts_review_flags_without_persisting_state(self):
		rows = [
			{"attention_flags": [{"key": "overdue_receipt"}, {"key": "received_not_billed"}]},
			{"attention_flags": [{"key": "billed_ahead_of_receipt"}, {"key": "ready_to_receive"}]},
			{"attention_flags": [{"key": "ready_to_receive"}]},
		]
		summary = _attention_summary(rows)
		self.assertEqual(summary["overdue_receipt"], 1)
		self.assertEqual(summary["received_not_billed"], 1)
		self.assertEqual(summary["billed_ahead_of_receipt"], 1)
		self.assertEqual(summary["ready_to_receive"], 2)
		self.assertEqual(summary["attention_total"], 2)


if __name__ == "__main__":
	import unittest

	unittest.main()
