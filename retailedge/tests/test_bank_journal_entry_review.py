from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match import (
	SUPPORTED_REVIEW_DOCUMENT_TYPES,
	_build_journal_entry_source_candidate,
)


class JournalEntryBankMatchReviewTests(unittest.TestCase):
	def test_journal_entry_is_supported_review_type(self):
		self.assertIn("Journal Entry", SUPPORTED_REVIEW_DOCUMENT_TYPES)

	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.get_all"
	)
	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.db.get_value"
	)
	def test_inflow_uses_bank_ledger_debit(self, get_value, get_all):
		get_value.return_value = {
			"name": "JV-DEP-1",
			"posting_date": "2026-08-18",
			"company": "ACME",
			"voucher_type": "Bank Entry",
			"cheque_no": "DEP-001",
			"user_remark": "Cash deposit",
			"docstatus": 1,
		}
		get_all.return_value = [
			{
				"account": "GTBank - ACME",
				"debit_in_account_currency": 450000,
				"credit_in_account_currency": 0,
				"party_type": None,
				"party": None,
			}
		]

		candidate = _build_journal_entry_source_candidate(
			"JV-DEP-1",
			bank_context={
				"resolved_bank_account": "GTBank - ACME",
				"bank_direction": "Inflow",
			},
		)

		self.assertEqual(candidate["candidate_amount"], 450000)
		self.assertEqual(candidate["payment_account"], "GTBank - ACME")
		self.assertEqual(candidate["payment_event_source"], "Journal Entry")

	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.get_all"
	)
	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.db.get_value"
	)
	def test_outflow_uses_bank_ledger_credit(self, get_value, get_all):
		get_value.return_value = {
			"name": "JV-EXP-1",
			"posting_date": "2026-08-18",
			"company": "ACME",
			"voucher_type": "Journal Entry",
			"cheque_no": "EXP-001",
			"user_remark": "Office expense",
			"docstatus": 1,
		}
		get_all.return_value = [
			{
				"account": "GTBank - ACME",
				"debit_in_account_currency": 0,
				"credit_in_account_currency": 75000,
				"party_type": None,
				"party": None,
			}
		]

		candidate = _build_journal_entry_source_candidate(
			"JV-EXP-1",
			bank_context={
				"resolved_bank_account": "GTBank - ACME",
				"bank_direction": "Outflow",
			},
		)

		self.assertEqual(candidate["candidate_amount"], 75000)

	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.db.get_value"
	)
	def test_draft_journal_entry_is_not_review_candidate(self, get_value):
		get_value.return_value = {
			"name": "JV-DRAFT-1",
			"posting_date": "2026-08-18",
			"company": "ACME",
			"voucher_type": "Journal Entry",
			"cheque_no": "DRAFT-1",
			"user_remark": "Draft",
			"docstatus": 0,
		}

		candidate = _build_journal_entry_source_candidate(
			"JV-DRAFT-1",
			bank_context={
				"resolved_bank_account": "GTBank - ACME",
				"bank_direction": "Outflow",
			},
		)

		self.assertIsNone(candidate)

	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.get_all"
	)
	@patch(
		"retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match.frappe.db.get_value"
	)
	def test_multiple_matching_bank_rows_fail_closed(self, get_value, get_all):
		get_value.return_value = {
			"name": "JV-AMB-1",
			"posting_date": "2026-08-18",
			"company": "ACME",
			"voucher_type": "Bank Entry",
			"cheque_no": "AMB-1",
			"user_remark": "Transfer",
			"docstatus": 1,
		}
		get_all.return_value = [
			{"account": "GTBank - ACME", "debit_in_account_currency": 100000, "credit_in_account_currency": 0},
			{"account": "GTBank - ACME", "debit_in_account_currency": 100000, "credit_in_account_currency": 0},
		]

		candidate = _build_journal_entry_source_candidate(
			"JV-AMB-1",
			bank_context={
				"resolved_bank_account": "GTBank - ACME",
				"bank_direction": "Inflow",
			},
		)

		self.assertIsNone(candidate)


if __name__ == "__main__":
	unittest.main()
