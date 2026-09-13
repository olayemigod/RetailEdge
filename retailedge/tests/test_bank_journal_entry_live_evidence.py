import unittest
from unittest.mock import patch

import frappe

from retailedge import banking_readiness


class JournalEntryLiveEvidenceTests(unittest.TestCase):
	@patch("retailedge.banking_readiness.has_field", return_value=True)
	@patch("retailedge.banking_readiness.has_doctype", return_value=True)
	@patch("retailedge.banking_readiness.frappe.get_all")
	@patch("retailedge.banking_readiness.frappe.db.get_value")
	def test_submitted_journal_entry_reads_standard_docstatus_and_live_posting_date(
		self,
		get_value,
		get_all,
		_has_doctype,
		_has_field,
	):
		def fake_get_value(doctype, name, fields=None, as_dict=False):
			if doctype == "Journal Entry":
				self.assertIn("docstatus", fields)
				self.assertIn("posting_date", fields)
				return frappe._dict(
					{
						"name": "ACC-JV-2026-00001",
						"posting_date": "2026-08-24",
						"company": "RetailEdge Consulting",
						"voucher_type": "Bank Entry",
						"cheque_no": "QA-BANK-EXP-185K",
						"docstatus": 1,
					}
				)
			return None

		def fake_get_all(doctype, **kwargs):
			if doctype == "Journal Entry Account" and kwargs.get("filters", {}).get("account") == "Bank - RC":
				return [
					frappe._dict(
						{
							"account": "Bank - RC",
							"debit_in_account_currency": 0,
							"credit_in_account_currency": 185000,
							"party_type": None,
							"party": None,
						}
					)
				]
			if doctype == "Journal Entry Account":
				return [
					frappe._dict({"account": "Bank - RC"}),
					frappe._dict({"account": "Office Rent - RC"}),
				]
			if doctype == "Account":
				return [
					frappe._dict(
						{
							"name": "Office Rent - RC",
							"root_type": "Expense",
							"account_type": "",
						}
					)
				]
			return []

		get_value.side_effect = fake_get_value
		get_all.side_effect = fake_get_all

		result = banking_readiness._journal_entry_reconciliation_context(
			"ACC-JV-2026-00001",
			{
				"direction": "Outflow",
				"resolved_payment_account": "Bank - RC",
			},
		)

		self.assertEqual(result["candidate_docstatus"], 1)
		self.assertEqual(result["candidate_date"], "2026-08-24")
		self.assertEqual(result["candidate_reference"], "QA-BANK-EXP-185K")
		self.assertEqual(result["candidate_account"], "Bank - RC")
		self.assertEqual(result["candidate_amount"], 185000)
		self.assertEqual(result["transaction_category"], "Expense")


if __name__ == "__main__":
	unittest.main()
