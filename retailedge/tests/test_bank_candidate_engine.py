from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.bank_candidate_engine import (
	CATEGORY_BANK_DEPOSIT,
	CATEGORY_CUSTOMER_RECEIPT,
	CATEGORY_EXPENSE,
	CATEGORY_SUPPLIER_PAYMENT,
	_payment_entry_business_category,
	get_direction_aware_bank_candidates,
)


class DirectionAwareBankCandidateEngineTests(unittest.TestCase):
	def test_payment_entry_business_categories_follow_direction_and_context(self):
		self.assertEqual(
			_payment_entry_business_category(
				{"payment_type": "Receive", "party_type": "Customer"}, "Inflow"
			),
			CATEGORY_CUSTOMER_RECEIPT,
		)
		self.assertEqual(
			_payment_entry_business_category(
				{"payment_type": "Pay", "party_type": "Supplier"}, "Outflow"
			),
			CATEGORY_SUPPLIER_PAYMENT,
		)
		self.assertEqual(
			_payment_entry_business_category(
				{"payment_type": "Internal Transfer"}, "Inflow"
			),
			CATEGORY_BANK_DEPOSIT,
		)
		self.assertEqual(
			_payment_entry_business_category(
				{"payment_type": "Pay", "remarks": "Office rent expense"}, "Outflow"
			),
			CATEGORY_EXPENSE,
		)

	@patch("retailedge.bank_candidate_engine._hydrate_payment_entry_metadata", return_value={})
	@patch("retailedge.bank_candidate_engine.enrich_ranked_candidates", side_effect=lambda _bt, rows: rows)
	@patch("retailedge.bank_candidate_engine._journal_entry_candidates", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_sales_invoice_candidates_for_bank_transaction")
	@patch("retailedge.bank_candidate_engine.find_payment_entry_candidates_for_bank_transaction")
	@patch("retailedge.bank_candidate_engine.normalize_bank_transaction")
	@patch("retailedge.bank_candidate_engine.assert_can_access_bank_transaction_matching")
	def test_inflow_searches_payment_and_sales_candidates(
		self,
		_assert_access,
		normalize,
		payment_candidates,
		sales_candidates,
		_journal,
		_enrich,
		_metadata,
	):
		normalize.return_value = {"direction": "Inflow", "amount": 1000}
		payment_candidates.return_value = [
			{"document_type": "Payment Entry", "document_name": "PE-1", "candidate_amount": 1000}
		]
		sales_candidates.return_value = [
			{"document_type": "Sales Invoice", "document_name": "SI-1", "candidate_amount": 1000}
		]

		result = get_direction_aware_bank_candidates("BT-1")

		self.assertEqual(result["direction"], "Inflow")
		self.assertEqual(result["count"], 2)
		sales_candidates.assert_called_once()

	@patch("retailedge.bank_candidate_engine._hydrate_payment_entry_metadata")
	@patch("retailedge.bank_candidate_engine.enrich_ranked_candidates", side_effect=lambda _bt, rows: rows)
	@patch("retailedge.bank_candidate_engine._journal_entry_candidates", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_sales_invoice_candidates_for_bank_transaction")
	@patch("retailedge.bank_candidate_engine.find_payment_entry_candidates_for_bank_transaction")
	@patch("retailedge.bank_candidate_engine.normalize_bank_transaction")
	@patch("retailedge.bank_candidate_engine.assert_can_access_bank_transaction_matching")
	def test_outflow_does_not_search_sales_invoice_receipts(
		self,
		_assert_access,
		normalize,
		payment_candidates,
		sales_candidates,
		_journal,
		_enrich,
		metadata,
	):
		normalize.return_value = {"direction": "Outflow", "amount": 75000}
		payment_candidates.return_value = [
			{"document_type": "Payment Entry", "document_name": "PE-SUP-1", "candidate_amount": 75000}
		]
		metadata.return_value = {
			"PE-SUP-1": {"payment_type": "Pay", "party_type": "Supplier", "party": "SUP-1"}
		}

		result = get_direction_aware_bank_candidates("BT-OUT")

		self.assertEqual(result["direction"], "Outflow")
		self.assertEqual(result["count"], 1)
		self.assertEqual(result["candidates"][0]["transaction_category"], CATEGORY_SUPPLIER_PAYMENT)
		sales_candidates.assert_not_called()

	@patch("retailedge.bank_candidate_engine._hydrate_payment_entry_metadata", return_value={})
	@patch("retailedge.bank_candidate_engine.enrich_ranked_candidates")
	@patch("retailedge.bank_candidate_engine._journal_entry_candidates")
	@patch("retailedge.bank_candidate_engine.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_candidate_engine.normalize_bank_transaction")
	@patch("retailedge.bank_candidate_engine.assert_can_access_bank_transaction_matching")
	def test_journal_candidates_enter_same_fuzzy_ranking_path(
		self,
		_assert_access,
		normalize,
		_payment,
		_sales,
		journal,
		enrich,
		_metadata,
	):
		bank = {"direction": "Inflow", "amount": 450000, "description": "cash deposit"}
		normalize.return_value = bank
		journal.return_value = [
			{
				"document_type": "Journal Entry",
				"document_name": "JV-DEP-1",
				"candidate_category": "Deposit to Bank",
				"transaction_category": CATEGORY_BANK_DEPOSIT,
				"candidate_amount": 450000,
			}
		]
		enrich.return_value = journal.return_value

		result = get_direction_aware_bank_candidates("BT-DEP")

		self.assertEqual(result["count"], 1)
		self.assertEqual(result["candidates"][0]["candidate_category"], "Deposit to Bank")
		enrich.assert_called_once()

	@patch(
		"retailedge.bank_candidate_engine.normalize_bank_transaction",
		return_value={"direction": "Unknown", "amount": 1000},
	)
	@patch("retailedge.bank_candidate_engine.assert_can_access_bank_transaction_matching")
	def test_unknown_direction_fails_closed(self, _assert_access, _normalize):
		with self.assertRaises(Exception):
			get_direction_aware_bank_candidates("BT-UNKNOWN")


if __name__ == "__main__":
	unittest.main()
