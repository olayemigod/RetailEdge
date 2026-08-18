from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.bank_candidate_engine import get_direction_aware_bank_candidates


class DirectionAwareBankCandidateEngineTests(unittest.TestCase):
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
	):
		normalize.return_value = {"direction": "Outflow", "amount": 75000}
		payment_candidates.return_value = [
			{"document_type": "Payment Entry", "document_name": "PE-SUP-1", "candidate_amount": 75000}
		]

		result = get_direction_aware_bank_candidates("BT-OUT")

		self.assertEqual(result["direction"], "Outflow")
		self.assertEqual(result["count"], 1)
		sales_candidates.assert_not_called()

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
	):
		bank = {"direction": "Inflow", "amount": 450000, "description": "cash deposit"}
		normalize.return_value = bank
		journal.return_value = [
			{
				"document_type": "Journal Entry",
				"document_name": "JV-DEP-1",
				"candidate_category": "Deposit to Bank",
				"candidate_amount": 450000,
			}
		]
		enrich.return_value = journal.return_value

		result = get_direction_aware_bank_candidates("BT-DEP")

		self.assertEqual(result["count"], 1)
		self.assertEqual(result["candidates"][0]["candidate_category"], "Deposit to Bank")
		enrich.assert_called_once()


if __name__ == "__main__":
	unittest.main()
