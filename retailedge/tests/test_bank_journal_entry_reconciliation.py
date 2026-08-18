from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

import frappe

from retailedge.reconciliation_bridge import (
	EXECUTION_STATUS_EXECUTED,
	NATIVE_EXECUTION_DOCTYPES,
	READINESS_NEEDS_REVIEW,
	READINESS_NOT_READY,
	READINESS_READY,
	TARGET_AVAILABLE,
	TARGET_MANUAL_REVIEW,
	_execute_native_reconciliation,
	_journal_entry_readiness,
	resolve_reconciliation_target,
)


class JournalEntryReconciliationBridgeTests(unittest.TestCase):
	def test_journal_entry_is_native_execution_type(self):
		self.assertIn("Journal Entry", NATIVE_EXECUTION_DOCTYPES)

	def test_unconfirmed_journal_entry_stays_in_review(self):
		status, reason = _journal_entry_readiness(
			{
				"suggested_document_type": "Journal Entry",
				"decision_status": "Needs Review",
				"candidate_docstatus": 1,
				"candidate_exists": True,
				"candidate_amount": 75000,
				"bank_amount": 75000,
				"amount_difference": 0,
				"account_resolution_status": "match",
			}
		)
		self.assertEqual(status, READINESS_NEEDS_REVIEW)
		self.assertIn("not confirmed", reason.lower())

	def test_submitted_exact_journal_entry_is_ready_after_confirmation(self):
		status, _reason = _journal_entry_readiness(
			{
				"suggested_document_type": "Journal Entry",
				"decision_status": "Confirmed",
				"candidate_docstatus": 1,
				"candidate_exists": True,
				"candidate_amount": 75000,
				"bank_amount": 75000,
				"amount_difference": 0,
				"account_resolution_status": "match",
			}
		)
		self.assertEqual(status, READINESS_READY)

	def test_amount_mismatch_blocks_journal_entry(self):
		status, reason = _journal_entry_readiness(
			{
				"suggested_document_type": "Journal Entry",
				"decision_status": "Confirmed",
				"candidate_docstatus": 1,
				"candidate_exists": True,
				"amount_difference": 500,
				"account_resolution_status": "match",
			}
		)
		self.assertEqual(status, READINESS_NOT_READY)
		self.assertIn("amount", reason.lower())

	def test_journal_entry_target_requires_submitted_revalidated_source(self):
		blocked = resolve_reconciliation_target(
			{
				"suggested_document_type": "Journal Entry",
				"suggested_document": "JV-1",
				"candidate_docstatus": 0,
				"payment_event_source": "Journal Entry",
			}
		)
		self.assertEqual(blocked["target_status"], TARGET_MANUAL_REVIEW)

		available = resolve_reconciliation_target(
			{
				"suggested_document_type": "Journal Entry",
				"suggested_document": "JV-1",
				"candidate_docstatus": 1,
				"payment_event_source": "Journal Entry",
				"bank_transaction": "BT-1",
			}
		)
		self.assertEqual(available["target_status"], TARGET_AVAILABLE)
		self.assertEqual(available["erpnext_target_doctype"], "Journal Entry")

	@patch("retailedge.reconciliation_bridge._bank_transaction_link_state")
	@patch("retailedge.reconciliation_bridge.frappe.get_attr")
	def test_native_journal_entry_execution_passes_amount_to_erpnext(self, get_attr, link_state):
		link_state.side_effect = [
			{"state": "ready", "message": "Ready"},
			{"state": "already_handled", "message": "Handled"},
		]
		native_method = Mock()
		get_attr.return_value = native_method

		result = _execute_native_reconciliation(
			frappe._dict(
				{
					"name": "RE-BTM-1",
					"bank_transaction": "BT-1",
					"suggested_document_type": "Journal Entry",
					"suggested_document": "JV-1",
				}
			),
			{
				"bank_transaction": "BT-1",
				"erpnext_target_doctype": "Journal Entry",
				"erpnext_target_name": "JV-1",
				"candidate_amount": 450000,
			},
		)

		self.assertEqual(result["execution_status"], EXECUTION_STATUS_EXECUTED)
		native_method.assert_called_once()
		args = native_method.call_args.args
		self.assertEqual(args[0], "BT-1")
		voucher = json.loads(args[1])[0]
		self.assertEqual(voucher["payment_doctype"], "Journal Entry")
		self.assertEqual(voucher["payment_name"], "JV-1")
		self.assertEqual(voucher["amount"], 450000)


if __name__ == "__main__":
	unittest.main()
