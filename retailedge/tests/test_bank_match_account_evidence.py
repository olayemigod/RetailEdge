from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge import banking_readiness


class BankMatchAccountEvidenceTests(FrappeTestCase):
	def test_review_ui_requests_server_authoritative_account_evidence(self):
		path = Path(frappe.get_app_path("retailedge", "public", "js", "bank_match_review_ui.js"))
		text = path.read_text()
		self.assertIn("retailedge.banking_readiness.get_match_account_evidence", text)
		self.assertIn('cardHeader("Bank Statement"', text)
		self.assertIn('cardHeader("Accounting Record"', text)
		self.assertIn('"Bank Identity & Accounting Safety"', text)
		self.assertIn('valueRow("Bank Account"', text)
		self.assertIn('valueRow("GL Account"', text)
		self.assertIn('evidenceLabel(item.status)', text)

	@patch("retailedge.banking_readiness.has_field", return_value=True)
	@patch("retailedge.banking_readiness.has_doctype", return_value=True)
	@patch("retailedge.banking_readiness.frappe.get_all")
	@patch("retailedge.banking_readiness.frappe.db.get_value")
	def test_candidate_bank_account_is_resolved_from_same_company_gl(
		self,
		get_value,
		get_all,
		_has_doctype,
		_has_field,
	):
		def fake_get_value(doctype, name, fields=None, as_dict=False):
			if doctype == "RetailEdge Bank Transaction Match":
				return frappe._dict(
					{
						"name": "RE-BTM-TEST",
						"bank_transaction": "ACC-BTN-TEST",
						"suggested_document_type": "Payment Entry",
						"suggested_document": "ACC-PAY-TEST",
						"company": "Retail Co",
						"bank_account": "Access Bank Ketu",
						"bank_amount": 750000,
						"candidate_amount": 750000,
						"bank_direction": "Outflow",
					}
				)
			if doctype == "Bank Account":
				return frappe._dict(
					{
						"name": "Access Bank Ketu",
						"bank": "Access Bank",
						"account": "Bank - RC",
						"company": "Retail Co",
						"disabled": 0,
					}
				)
			if doctype == "Account":
				return frappe._dict(
					{
						"name": "Bank - RC",
						"company": "Retail Co",
						"account_type": "Bank",
						"is_group": 0,
						"disabled": 0,
					}
				)
			if doctype == "Payment Entry" and fields == "company":
				return "Retail Co"
			return None

		get_value.side_effect = fake_get_value
		get_all.side_effect = lambda doctype, **kwargs: (
			[
				frappe._dict(
					{
						"name": "Access Bank Ketu",
						"bank": "Access Bank",
						"account": "Bank - RC",
						"company": "Retail Co",
					}
				)
			]
			if doctype == "Bank Account"
			else []
		)

		with (
			patch(
				"retailedge.banking_readiness.get_bank_transaction_reconciliation_context",
				return_value={
					"bank_transaction": "ACC-BTN-TEST",
					"bank_account": "Access Bank Ketu",
					"bank_transaction_amount": 750000,
					"company": "Retail Co",
					"bank_transaction_date": "2026-08-23",
				},
			),
			patch(
				"retailedge.banking_readiness.normalize_bank_transaction",
				return_value={"direction": "Outflow"},
			),
			patch(
				"retailedge.banking_readiness.get_payment_event_reconciliation_context",
				return_value={
					"candidate_doctype": "Payment Entry",
					"candidate_name": "ACC-PAY-TEST",
					"candidate_account": "Bank - RC",
					"candidate_amount": 750000,
					"candidate_date": "2026-08-23",
					"candidate_mode_of_payment": "Bank Transfer",
				},
			),
			patch("retailedge.banking_readiness.frappe.db.count", return_value=1),
		):
			result = banking_readiness.build_match_account_evidence("RE-BTM-TEST")

		self.assertEqual(result["statement"]["bank"], "Access Bank")
		self.assertEqual(result["statement"]["gl_account"], "Bank - RC")
		self.assertEqual(result["accounting"]["bank"], "Access Bank")
		self.assertEqual(result["accounting"]["bank_account"], "Access Bank Ketu")
		self.assertEqual(result["accounting"]["gl_account"], "Bank - RC")
		self.assertEqual(result["accounting"]["gl_account_label"], "Paid From")
		statuses = {row["key"]: row["status"] for row in result["evidence"]}
		self.assertEqual(statuses["bank_account"], "Match")
		self.assertEqual(statuses["gl_account"], "Match")
		self.assertEqual(statuses["amount"], "Match")
