from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.project_receipts import create_project_receipt_draft


class _DraftPayment(SimpleNamespace):
	doctype = "Payment Entry"

	def __init__(self):
		super().__init__(name="ACC-PAY-PROJ-1", docstatus=0, insert_calls=0, references=[])

	def insert(self):
		self.insert_calls += 1
		return self

	def get(self, key):
		return getattr(self, key, None)


class TestProjectReceipts(unittest.TestCase):
	@patch("retailedge.project_receipts._payment_branch_field", return_value="retailedge_branch")
	@patch("retailedge.project_receipts.get_simple_payment_mode_details")
	@patch("retailedge.project_receipts.get_party_details")
	@patch("retailedge.project_receipts.validate_user_branch_access")
	@patch("retailedge.project_receipts._assert_permission")
	@patch("retailedge.project_receipts.frappe.db.get_value", return_value="NGN")
	@patch("retailedge.project_receipts.frappe.new_doc")
	@patch("retailedge.project_receipts.frappe.get_doc")
	def test_project_receipt_is_draft_native_payment_entry(
		self,
		mock_get_doc,
		mock_new_doc,
		_mock_currency,
		_mock_permission,
		mock_branch_access,
		mock_party_details,
		mock_mode_details,
		_mock_branch_field,
	):
		project = SimpleNamespace(
			name="PROJ-0001", company="Demo Company", customer="CUST-001", cost_center="Main - DC"
		)
		mock_get_doc.return_value = project
		payment = _DraftPayment()
		mock_new_doc.return_value = payment
		mock_party_details.return_value = frappe._dict(
			party_account="Debtors - DC", party_account_currency="NGN"
		)
		mock_mode_details.return_value = {
			"account": "Bank - DC",
			"account_currency": "NGN",
			"reference_required": True,
		}

		result = create_project_receipt_draft(
			{
				"project": "PROJ-0001",
				"branch": "Lagos",
				"mode_of_payment": "Bank Transfer",
				"amount": 250000,
				"reference_no": "PRJ-TRF-1",
				"reference_date": "2026-08-28",
			}
		)

		self.assertEqual(payment.insert_calls, 1)
		self.assertEqual(payment.docstatus, 0)
		self.assertEqual(payment.payment_type, "Receive")
		self.assertEqual(payment.party_type, "Customer")
		self.assertEqual(payment.party, "CUST-001")
		self.assertEqual(payment.project, "PROJ-0001")
		self.assertEqual(payment.cost_center, "Main - DC")
		self.assertEqual(payment.retailedge_branch, "Lagos")
		self.assertEqual(payment.paid_amount, 250000)
		self.assertEqual(result["source_of_truth"], "Payment Entry")
		mock_branch_access.assert_called_once()

	@patch("retailedge.project_receipts._assert_permission")
	@patch("retailedge.project_receipts.frappe.get_doc")
	def test_project_receipt_rejects_wrong_customer(self, mock_get_doc, _mock_permission):
		mock_get_doc.return_value = SimpleNamespace(
			name="PROJ-0001", company="Demo Company", customer="CUST-001", cost_center=None
		)
		with self.assertRaises(frappe.ValidationError):
			create_project_receipt_draft(
				{
					"project": "PROJ-0001",
					"customer": "CUST-OTHER",
					"mode_of_payment": "Cash",
					"amount": 1000,
				}
			)

	@patch("retailedge.project_receipts._payment_branch_field", return_value=None)
	@patch("retailedge.project_receipts.validate_user_branch_access")
	@patch("retailedge.project_receipts._assert_permission")
	@patch("retailedge.project_receipts.frappe.get_doc")
	def test_project_receipt_fails_closed_without_branch_attribution(
		self,
		mock_get_doc,
		_mock_permission,
		mock_branch_access,
		_mock_branch_field,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="PROJ-0001", company="Demo Company", customer="CUST-001", cost_center=None
		)
		with self.assertRaises(frappe.ValidationError):
			create_project_receipt_draft(
				{
					"project": "PROJ-0001",
					"branch": "Lagos",
					"mode_of_payment": "Cash",
					"amount": 1000,
				}
			)
		mock_branch_access.assert_called_once()


if __name__ == "__main__":
	unittest.main()
