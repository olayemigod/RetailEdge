from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import banking_readiness


class JournalEntryReviewEvidenceFallbackTests(FrappeTestCase):
	@patch("retailedge.banking_readiness.has_field", return_value=True)
	@patch("retailedge.banking_readiness._bank_accounts_for_ledger")
	@patch("retailedge.banking_readiness._journal_entry_reconciliation_context")
	@patch("retailedge.banking_readiness.get_payment_event_reconciliation_context")
	@patch("retailedge.banking_readiness.evaluate_bank_account_readiness")
	@patch("retailedge.banking_readiness.normalize_bank_transaction")
	@patch("retailedge.banking_readiness.get_bank_transaction_reconciliation_context")
	@patch("retailedge.banking_readiness.frappe.db.get_value")
	def test_legacy_journal_review_uses_live_bank_gl_for_evidence_hydration(
		self,
		get_value,
		bank_context,
		normalize,
		evaluate_readiness,
		generic_candidate,
		journal_candidate,
		bank_accounts,
		_has_field,
	):
		def fake_get_value(doctype, name, fields=None, as_dict=False):
			if doctype == "RetailEdge Bank Transaction Match":
				return frappe._dict(
					{
						"name": "RE-BTM-JE-LEGACY",
						"bank_transaction": "ACC-BTN-2026-00016",
						"suggested_document_type": "Journal Entry",
						"suggested_document": "ACC-JV-2026-00001",
						"company": "RetailEdge Consulting",
						"bank_account": "Access Bank Ketu - Access Bank",
						"bank_amount": 185000,
						"candidate_amount": 185000,
						"bank_direction": "Outflow",
						"payment_account": "",
						"resolved_payment_account": "",
					}
				)
			if doctype == "Journal Entry" and fields == "company":
				return "RetailEdge Consulting"
			return None

		get_value.side_effect = fake_get_value
		bank_context.return_value = {
			"bank_transaction": "ACC-BTN-2026-00016",
			"bank_account": "Access Bank Ketu - Access Bank",
			"bank_transaction_amount": 185000,
			"company": "RetailEdge Consulting",
			"bank_transaction_date": "2026-08-24",
			"reference": "QA-BANK-EXP-185K",
		}
		normalize.return_value = {"direction": "Outflow"}
		evaluate_readiness.return_value = {
			"bank_account": "Access Bank Ketu - Access Bank",
			"bank": "Access Bank",
			"company": "RetailEdge Consulting",
			"resolved_gl_account": "Bank - RC",
			"readiness": "Ready",
		}
		generic_candidate.return_value = {}
		journal_candidate.return_value = {
			"candidate_doctype": "Journal Entry",
			"candidate_name": "ACC-JV-2026-00001",
			"candidate_date": "2026-08-24",
			"candidate_account": "Bank - RC",
			"candidate_amount": 185000,
			"candidate_reference": "QA-BANK-EXP-185K",
			"candidate_company": "RetailEdge Consulting",
			"candidate_category": "Expense Payment",
			"transaction_category": "Expense",
		}
		bank_accounts.return_value = [
			frappe._dict(
				{
					"name": "Access Bank Ketu - Access Bank",
					"bank": "Access Bank",
					"account": "Bank - RC",
					"company": "RetailEdge Consulting",
				}
			)
		]

		result = banking_readiness.build_match_account_evidence("RE-BTM-JE-LEGACY")

		fallback_match = journal_candidate.call_args.args[1]
		self.assertEqual(fallback_match.get("payment_account"), "Bank - RC")
		self.assertEqual(fallback_match.get("resolved_payment_account"), "Bank - RC")
		self.assertEqual(result["accounting"]["gl_account"], "Bank - RC")
		self.assertEqual(result["accounting"]["bank_account"], "Access Bank Ketu - Access Bank")
		self.assertEqual(result["accounting"]["bank"], "Access Bank")
		self.assertEqual(result["accounting"]["date"], "2026-08-24")
		self.assertEqual(result["accounting"]["reference"], "QA-BANK-EXP-185K")
		self.assertEqual(result["transaction_category"], "Expense")


if __name__ == "__main__":
	unittest.main()
