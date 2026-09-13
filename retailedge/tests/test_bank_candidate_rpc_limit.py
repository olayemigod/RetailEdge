from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.bank_candidate_engine import get_direction_aware_bank_candidates


class BankCandidateRpcLimitTests(unittest.TestCase):
	@patch("retailedge.bank_candidate_engine._can_read_candidate", return_value=True)
	@patch("retailedge.bank_candidate_engine._hydrate_payment_entry_metadata", return_value={})
	@patch("retailedge.bank_candidate_engine.enrich_ranked_candidates", side_effect=lambda _bt, rows: rows)
	@patch("retailedge.bank_candidate_engine._journal_entry_candidates", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_candidate_engine.normalize_bank_transaction")
	@patch("retailedge.bank_candidate_engine.assert_can_access_bank_transaction_matching")
	def test_string_rpc_limit_is_normalized_before_candidate_queries(
		self,
		_assert_access,
		normalize,
		payment_candidates,
		sales_candidates,
		journal_candidates,
		_enrich,
		_metadata,
		_can_read,
	):
		normalize.return_value = {"direction": "Inflow", "amount": 1000}

		result = get_direction_aware_bank_candidates("BT-RPC", limit="20")

		self.assertEqual(result["count"], 0)
		self.assertEqual(payment_candidates.call_args.kwargs["limit"], 20)
		self.assertEqual(sales_candidates.call_args.kwargs["limit"], 20)
		self.assertEqual(journal_candidates.call_args.kwargs["limit"], 20)

	@patch("retailedge.bank_candidate_engine._can_read_candidate", return_value=True)
	@patch("retailedge.bank_candidate_engine._hydrate_payment_entry_metadata", return_value={})
	@patch("retailedge.bank_candidate_engine.enrich_ranked_candidates", side_effect=lambda _bt, rows: rows)
	@patch("retailedge.bank_candidate_engine._journal_entry_candidates", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_candidate_engine.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_candidate_engine.normalize_bank_transaction")
	@patch("retailedge.bank_candidate_engine.assert_can_access_bank_transaction_matching")
	def test_rpc_limit_is_bounded(
		self,
		_assert_access,
		normalize,
		payment_candidates,
		_sales_candidates,
		_journal_candidates,
		_enrich,
		_metadata,
		_can_read,
	):
		normalize.return_value = {"direction": "Outflow", "amount": 1000}

		get_direction_aware_bank_candidates("BT-RPC", limit="5000")

		self.assertEqual(payment_candidates.call_args.kwargs["limit"], 100)


if __name__ == "__main__":
	unittest.main()
