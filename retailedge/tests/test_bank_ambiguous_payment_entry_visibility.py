from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.bank_transaction_matching import (
	_ambiguous_payment_entry_review_candidates,
	_derive_action_status,
	find_payment_entry_candidates_for_bank_transaction,
	get_auto_match_status_for_row,
)


def _bank():
	return frappe._dict(
		bank_transaction="ACC-BTN-TEST-1",
		amount=200000,
		direction="Inflow",
		transaction_date="2026-10-01",
		bank_account="Access Bank Ketu - Access Bank",
	)


def _candidate(name, *, party=None, reference_strength="none"):
	return {
		"document_type": "Payment Entry",
		"document_name": name,
		"suggested_document": name,
		"candidate_category": "payment_entry_match",
		"candidate_amount": 200000,
		"amount_difference": 0,
		"amount_scenario": "Submitted Payment Entry Amount",
		"payment_event_found": 1,
		"payment_event_source": "Payment Entry",
		"payment_entry_payment_type": "Receive",
		"payment_account": "Bank - RC",
		"account_resolution_status": "match",
		"date_difference_days": 0,
		"party": party,
		"customer": party,
		"customer_display": party,
		"reference_match_strength": reference_strength,
		"reference_match_exact": 1 if reference_strength == "exact" else 0,
		"score": 75,
		"confidence": "Possible Match",
		"reason": "Submitted Payment Entry candidate.",
	}


class AmbiguousPaymentEntryVisibilityTests(unittest.TestCase):
	def test_multiple_weak_identity_candidates_are_returned_for_manual_review(self):
		candidates = [
			_candidate("ACC-PAY-CASH-DEPOSIT"),
			_candidate("ACC-PAY-CUSTOMER", party="Mathew Alao"),
		]

		rows = _ambiguous_payment_entry_review_candidates(
			_bank(), candidates, {"date_window_days": 3}
		)

		self.assertEqual(len(rows), 2)
		self.assertEqual(
			{row["document_name"] for row in rows},
			{"ACC-PAY-CASH-DEPOSIT", "ACC-PAY-CUSTOMER"},
		)
		for row in rows:
			self.assertEqual(row["identity_ambiguous"], 1)
			self.assertEqual(row["identity_competing_candidates"], 2)
			self.assertEqual(row["confidence"], "Possible Match")
			self.assertIn("Choose the correct accounting event manually", row["identity_review_reason"])

	def test_single_weak_identity_candidate_is_not_labelled_ambiguous(self):
		rows = _ambiguous_payment_entry_review_candidates(
			_bank(), [_candidate("ACC-PAY-ONLY")], {"date_window_days": 3}
		)
		self.assertEqual(rows, [])

	def test_ambiguous_candidate_action_status_is_needs_review(self):
		candidate = _candidate("ACC-PAY-1")
		candidate["identity_ambiguous"] = 1
		self.assertEqual(_derive_action_status(_bank(), candidate), "Needs Review")

	def test_ambiguous_candidate_is_never_auto_match_eligible(self):
		row = {
			"bank_transaction": "ACC-BTN-TEST-1",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-1",
			"identity_ambiguous": 1,
			"identity_review_reason": "Two candidates require human selection.",
			"candidate_category": "payment_entry_match",
			"amount_scenario": "Submitted Payment Entry Amount",
			"match_confidence": "Strong Match",
			"match_score": 100,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"payment_entry_payment_type": "Receive",
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 95,
			"allow_auto_match_payment_entry": 1,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}

		status = get_auto_match_status_for_row(row, settings=settings)

		self.assertEqual(status["status"], "Needs Manual Review")
		self.assertEqual(status["category"], "ambiguous_identity")
		self.assertFalse(status["eligible_prepare"])
		self.assertFalse(status["eligible_confirm"])

	@patch("retailedge.bank_transaction_matching._build_scored_payment_entries")
	@patch(
		"retailedge.bank_transaction_matching._get_payment_entry_rows",
		return_value=[{"name": "placeholder"}],
	)
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch("retailedge.bank_transaction_matching.normalize_bank_transaction")
	@patch("retailedge.bank_transaction_matching.get_bank_transaction_matching_settings")
	def test_direct_resolver_surfaces_competing_payment_entries(
		self, mock_settings, mock_normalize, _has_doctype, _get_rows, mock_build
	):
		mock_settings.return_value = {"date_window_days": 3}
		mock_normalize.return_value = _bank()
		mock_build.return_value = [
			_candidate("ACC-PAY-CASH-DEPOSIT"),
			_candidate("ACC-PAY-CUSTOMER", party="Mathew Alao"),
		]

		rows = find_payment_entry_candidates_for_bank_transaction(
			"ACC-BTN-TEST-1",
			filters={"company": "RetailEdge Consulting"},
			limit=20,
			context={},
		)

		self.assertEqual(len(rows), 2)
		self.assertTrue(all(row.get("identity_ambiguous") for row in rows))

	@patch("retailedge.bank_transaction_matching._build_scored_payment_entries")
	@patch(
		"retailedge.bank_transaction_matching._get_payment_entry_rows",
		return_value=[{"name": "placeholder"}],
	)
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch("retailedge.bank_transaction_matching.normalize_bank_transaction")
	@patch("retailedge.bank_transaction_matching.get_bank_transaction_matching_settings")
	def test_strong_reference_candidate_wins_without_ambiguous_fallback(
		self, mock_settings, mock_normalize, _has_doctype, _get_rows, mock_build
	):
		mock_settings.return_value = {"date_window_days": 3}
		mock_normalize.return_value = _bank()
		strong = _candidate("ACC-PAY-STRONG", reference_strength="exact")
		weak = _candidate("ACC-PAY-WEAK")
		mock_build.return_value = [strong, weak]

		rows = find_payment_entry_candidates_for_bank_transaction(
			"ACC-BTN-TEST-1", filters={}, limit=20, context={}
		)

		self.assertEqual([row["document_name"] for row in rows], ["ACC-PAY-STRONG"])
		self.assertFalse(rows[0].get("identity_ambiguous", 0))


if __name__ == "__main__":
	unittest.main()
