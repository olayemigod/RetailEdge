from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_cash_transfer import (
	MAX_LINK_RESULTS,
	create_simple_cash_transfer_draft,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftPaymentEntry(SimpleNamespace):
	doctype = "Payment Entry"

	def __init__(self):
		super().__init__(name="ACC-PAY-TRANSFER-0001", docstatus=0, insert_calls=0)

	def insert(self):
		self.insert_calls += 1
		return self


class TestGuidedCashTransfer(unittest.TestCase):
	@patch("retailedge.guided_cash_transfer.has_field", return_value=False)
	@patch("retailedge.guided_cash_transfer._get_transfer_account")
	@patch("retailedge.guided_cash_transfer.frappe.db.get_value", return_value="NGN")
	@patch("retailedge.guided_cash_transfer._assert_read_permission")
	@patch("retailedge.guided_cash_transfer.validate_user_branch_access")
	@patch("retailedge.guided_cash_transfer._assert_can_create_payment_entry")
	@patch("retailedge.guided_cash_transfer.frappe.new_doc")
	def test_cash_to_cash_creates_internal_transfer_draft(
		self,
		mock_new_doc,
		_mock_create_permission,
		_mock_branch_access,
		_mock_read_permission,
		_mock_company_currency,
		mock_account,
		_mock_has_field,
	):
		doc = _DraftPaymentEntry()
		mock_new_doc.return_value = doc
		mock_account.side_effect = [
			{"account_type": "Cash", "account_currency": "NGN"},
			{"account_type": "Cash", "account_currency": "NGN"},
		]

		result = create_simple_cash_transfer_draft(
			{
				"company": "Demo Company",
				"branch": "Lagos",
				"posting_date": "2026-08-18",
				"from_account": "Cash Main - DC",
				"to_account": "Cash Petty - DC",
				"amount": 25000,
			}
		)

		self.assertEqual(doc.payment_type, "Internal Transfer")
		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(doc.paid_from, "Cash Main - DC")
		self.assertEqual(doc.paid_to, "Cash Petty - DC")
		self.assertEqual(doc.paid_amount, 25000)
		self.assertEqual(doc.received_amount, 25000)
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(result["docstatus"], 0)
		self.assertEqual(result["payment_type"], "Internal Transfer")

	@patch("retailedge.guided_cash_transfer.has_field", return_value=False)
	@patch("retailedge.guided_cash_transfer._get_transfer_account")
	@patch("retailedge.guided_cash_transfer.frappe.db.get_value", return_value="NGN")
	@patch("retailedge.guided_cash_transfer._assert_read_permission")
	@patch("retailedge.guided_cash_transfer.validate_user_branch_access")
	@patch("retailedge.guided_cash_transfer._assert_can_create_payment_entry")
	@patch("retailedge.guided_cash_transfer.frappe.new_doc")
	def test_bank_transfer_requires_reference_number(
		self,
		mock_new_doc,
		_mock_create_permission,
		_mock_branch_access,
		_mock_read_permission,
		_mock_company_currency,
		mock_account,
		_mock_has_field,
	):
		mock_new_doc.return_value = _DraftPaymentEntry()
		mock_account.side_effect = [
			{"account_type": "Cash", "account_currency": "NGN"},
			{"account_type": "Bank", "account_currency": "NGN"},
		]
		with self.assertRaises(frappe.ValidationError):
			create_simple_cash_transfer_draft(
				{
					"company": "Demo Company",
					"from_account": "Cash Main - DC",
					"to_account": "Bank - DC",
					"amount": 1000,
				}
			)

	def test_adapter_is_draft_only_permission_aware_and_bounded(self):
		source = (APP_ROOT / "guided_cash_transfer.py").read_text()
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("frappe.get_list(", source)
		self.assertIn('account_type": ["in", ["Bank", "Cash"]]', source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn('doc.payment_type = "Internal Transfer"', source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_simple_transfer_rejects_same_or_non_positive_accounts_before_insert(self):
		with patch("retailedge.guided_cash_transfer._assert_can_create_payment_entry"), patch(
			"retailedge.guided_cash_transfer._assert_read_permission"
		), patch("retailedge.guided_cash_transfer.frappe.db.get_value", return_value="NGN"), patch(
			"retailedge.guided_cash_transfer._get_transfer_account",
			return_value={"account_type": "Cash", "account_currency": "NGN"},
		):
			with self.assertRaises(frappe.ValidationError):
				create_simple_cash_transfer_draft(
					{
						"company": "Demo Company",
						"from_account": "Cash - DC",
						"to_account": "Cash - DC",
						"amount": 100,
					}
				)

	def test_limit_is_deliberately_small(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)


if __name__ == "__main__":
	unittest.main()
