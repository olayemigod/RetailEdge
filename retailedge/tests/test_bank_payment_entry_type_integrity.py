from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.bank_transaction_matching import (
	_build_matching_row,
	_build_payment_entry_candidate,
	_get_payment_entry_rows,
	get_auto_match_status_for_row,
)


class BankPaymentEntryTypeIntegrityTests(unittest.TestCase):
	def test_internal_transfer_candidate_preserves_type_and_no_fake_customer_party(self):
		bank_transaction = frappe._dict(
			bank_transaction="ACC-BTN-1",
			direction="Inflow",
			amount=200000,
		)
		payment_entry = frappe._dict(
			name="ACC-PAY-2026-00016",
			posting_date="2026-10-01",
			payment_type="Internal Transfer",
			party_type=None,
			party=None,
			paid_from="Cash - RC",
			paid_to="Bank - RC",
			paid_amount=200000,
			received_amount=200000,
			reference_no="Mathew Alao",
			retailedge_branch="Ketu",
			mode_of_payment=None,
		)

		candidate = _build_payment_entry_candidate(bank_transaction, payment_entry, [])

		self.assertEqual(candidate["payment_entry_payment_type"], "Internal Transfer")
		self.assertIsNone(candidate["party_type"])
		self.assertIsNone(candidate["party"])
		self.assertIsNone(candidate["customer"])
		self.assertEqual(candidate["payment_account"], "Bank - RC")

	def test_matching_row_does_not_invent_customer_for_partyless_payment_entry(self):
		row = _build_matching_row(
			frappe._dict(
				bank_transaction="ACC-BTN-1",
				transaction_date="2026-10-01",
				bank_account="Access Bank Ketu - Access Bank",
				amount=200000,
				direction="Inflow",
			),
			{
				"document_type": "Payment Entry",
				"document_name": "ACC-PAY-2026-00016",
				"payment_entry_payment_type": "Internal Transfer",
				"party": None,
				"party_type": None,
				"customer": None,
				"customer_display": None,
			},
			action_status="Needs Review",
		)

		self.assertIsNone(row["party_type"])
		self.assertIsNone(row["party"])
		self.assertIsNone(row["customer"])
		self.assertEqual(row["payment_entry_payment_type"], "Internal Transfer")

	def test_internal_transfer_candidate_is_manual_review_only_even_when_other_signals_are_strong(self):
		row = {
			"bank_transaction": "ACC-BTN-1",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-2026-00016",
			"candidate_category": "payment_entry_match",
			"amount_scenario": "Submitted Payment Entry Amount",
			"match_confidence": "Strong Match",
			"match_score": 100,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"payment_entry_payment_type": "Internal Transfer",
			"payment_account": "Bank - RC",
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 95,
			"allow_auto_match_payment_entry": 1,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 0,
			"require_same_branch_for_auto_match": 0,
			"require_no_duplicate_candidate_for_auto_match": 0,
			"require_no_active_review_for_auto_match": 0,
		}

		status = get_auto_match_status_for_row(row, settings=settings)

		self.assertEqual(status["status"], "Needs Manual Review")
		self.assertEqual(status["category"], "manual_review")
		self.assertFalse(status["eligible_prepare"])
		self.assertFalse(status["eligible_confirm"])

	@patch("retailedge.bank_transaction_matching._dedupe_named_rows", side_effect=lambda rows: rows)
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	def test_direct_payment_entry_query_fetches_payment_type_and_mode(
		self, _has_field, get_all, _dedupe
	):
		get_all.return_value = []
		bank_transaction = frappe._dict(
			company="RetailEdge Consulting",
			transaction_date="2026-10-01",
		)

		_get_payment_entry_rows(bank_transaction, frappe._dict(), {"date_window_days": 3})

		fields = get_all.call_args.kwargs["fields"]
		self.assertIn("payment_type", fields)
		self.assertIn("mode_of_payment", fields)


if __name__ == "__main__":
	unittest.main()
