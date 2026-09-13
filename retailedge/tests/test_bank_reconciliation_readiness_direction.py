from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness import (
	_apply_direction_aware_readiness,
)


class ReconciliationReadinessDirectionTests(unittest.TestCase):
	@patch(
		"retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.get_reconciliation_preflight"
	)
	@patch(
		"retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.frappe.get_all"
	)
	def test_outflow_uses_canonical_bridge_but_ordinary_inflow_does_not(self, get_all, preflight):
		get_all.return_value = [
			{"name": "BT-IN", "deposit": 100000, "withdrawal": 0},
			{"name": "BT-OUT", "deposit": 0, "withdrawal": 75000},
		]
		preflight.return_value = {
			"status": "Ready",
			"blocking_reason": "",
			"canonical_bank_account": "GTBank - ACME",
			"canonical_payment_account": "GTBank - ACME",
			"payment_event_source": "Payment Entry",
			"payment_event_amount": 75000,
			"candidate_account": "GTBank - ACME",
			"account_resolution_status": "match",
		}
		rows = [
			{
				"bank_match_review": "RE-IN",
				"bank_transaction": "BT-IN",
				"suggested_document_type": "Payment Entry",
				"reconciliation_readiness_status": "Ready for Reconciliation",
			},
			{
				"bank_match_review": "RE-OUT",
				"bank_transaction": "BT-OUT",
				"suggested_document_type": "Payment Entry",
				"reconciliation_readiness_status": "Not Ready",
			},
		]

		result = _apply_direction_aware_readiness(rows, {"direction": "All"})

		self.assertEqual(result[0]["direction"], "Inflow")
		self.assertEqual(result[1]["direction"], "Outflow")
		self.assertEqual(result[1]["reconciliation_readiness_status"], "Ready for Reconciliation")
		preflight.assert_called_once_with("RE-OUT")

	@patch(
		"retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.get_reconciliation_preflight"
	)
	@patch(
		"retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.frappe.get_all"
	)
	def test_journal_entry_inflow_still_uses_canonical_bridge(self, get_all, preflight):
		get_all.return_value = [{"name": "BT-DEP", "deposit": 450000, "withdrawal": 0}]
		preflight.return_value = {
			"status": "Needs Review",
			"blocking_reason": "Decision is not confirmed yet.",
		}
		rows = [
			{
				"bank_match_review": "RE-JE",
				"bank_transaction": "BT-DEP",
				"suggested_document_type": "Journal Entry",
				"reconciliation_readiness_status": "Not Ready",
			}
		]

		result = _apply_direction_aware_readiness(rows, {"direction": "All"})

		self.assertEqual(result[0]["direction"], "Inflow")
		self.assertEqual(result[0]["reconciliation_readiness_status"], "Needs Review")
		preflight.assert_called_once_with("RE-JE")

	@patch(
		"retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.get_reconciliation_preflight"
	)
	@patch(
		"retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness.retailedge_bank_match_reconciliation_readiness.frappe.get_all"
	)
	def test_direction_filter_excludes_opposite_side(self, get_all, preflight):
		get_all.return_value = [
			{"name": "BT-IN", "deposit": 100000, "withdrawal": 0},
			{"name": "BT-OUT", "deposit": 0, "withdrawal": 50000},
		]
		preflight.return_value = {"status": "Not Ready", "blocking_reason": "Review"}
		rows = [
			{"bank_match_review": "RE-IN", "bank_transaction": "BT-IN", "suggested_document_type": "Payment Entry"},
			{"bank_match_review": "RE-OUT", "bank_transaction": "BT-OUT", "suggested_document_type": "Payment Entry"},
		]

		result = _apply_direction_aware_readiness(rows, {"direction": "Outflow"})

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["bank_transaction"], "BT-OUT")
		self.assertEqual(result[0]["direction"], "Outflow")


if __name__ == "__main__":
	unittest.main()
