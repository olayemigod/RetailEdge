from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.advanced_payments import (
	MAX_ADVANCE_ROWS,
	create_customer_advance_draft,
	get_sales_invoice_advance_context,
	list_customer_advances,
)


class _DraftAdvance(SimpleNamespace):
	doctype = "Payment Entry"

	def __init__(self):
		super().__init__(
			name="ACC-PAY-ADV-0001",
			docstatus=0,
			insert_calls=0,
			unallocated_amount=1500.0,
		)

	def insert(self):
		self.insert_calls += 1
		return self


class TestAdvancedPayments(unittest.TestCase):
	@patch("retailedge.advanced_payments._payment_branch_field", return_value=None)
	@patch("retailedge.advanced_payments._assert_read")
	@patch("retailedge.advanced_payments.frappe.get_list")
	def test_list_customer_advances_uses_authoritative_unallocated_payment_entries(
		self,
		mock_get_list,
		_mock_assert_read,
		_mock_branch_field,
	):
		mock_get_list.return_value = [
			frappe._dict(
				name="ACC-PAY-0001",
				posting_date="2026-08-20",
				company="Demo Company",
				party="CUST-001",
				paid_amount=2500,
				received_amount=2500,
				unallocated_amount=750,
				paid_to="Bank - DC",
				mode_of_payment="Bank Transfer",
				reference_no="TRF-1",
				reference_date="2026-08-20",
			)
		]

		rows = list_customer_advances(customer="CUST-001", company="Demo Company", limit=1000)

		kwargs = mock_get_list.call_args.kwargs
		self.assertEqual(kwargs["filters"]["docstatus"], 1)
		self.assertEqual(kwargs["filters"]["payment_type"], "Receive")
		self.assertEqual(kwargs["filters"]["party_type"], "Customer")
		self.assertEqual(kwargs["filters"]["unallocated_amount"], [">", 0])
		self.assertEqual(kwargs["filters"]["party"], "CUST-001")
		self.assertEqual(kwargs["filters"]["company"], "Demo Company")
		self.assertEqual(kwargs["limit_page_length"], MAX_ADVANCE_ROWS)
		self.assertEqual(rows[0]["unallocated_amount"], 750.0)
		self.assertEqual(rows[0]["route"], "/app/payment-entry/ACC-PAY-0001")

	@patch("retailedge.advanced_payments._payment_branch_field", return_value="branch")
	@patch("retailedge.advanced_payments.get_simple_payment_mode_details")
	@patch("retailedge.advanced_payments.get_party_details")
	@patch("retailedge.advanced_payments._company_currency", return_value="NGN")
	@patch("retailedge.advanced_payments.validate_user_branch_access")
	@patch("retailedge.advanced_payments._assert_read")
	@patch("retailedge.advanced_payments._assert_create_payment_entry")
	@patch("retailedge.advanced_payments.frappe.new_doc")
	def test_create_customer_advance_draft_has_no_invoice_allocation(
		self,
		mock_new_doc,
		_mock_create_permission,
		_mock_read,
		mock_branch_access,
		_mock_currency,
		mock_party_details,
		mock_mode_details,
		_mock_branch_field,
	):
		doc = _DraftAdvance()
		mock_new_doc.return_value = doc
		mock_party_details.return_value = frappe._dict(
			party_account="Debtors - DC",
			party_account_currency="NGN",
		)
		mock_mode_details.return_value = {
			"account": "Bank - DC",
			"account_type": "Bank",
			"account_currency": "NGN",
			"reference_required": True,
		}

		result = create_customer_advance_draft(
			{
				"company": "Demo Company",
				"branch": "Lagos",
				"customer": "CUST-001",
				"posting_date": "2026-08-28",
				"mode_of_payment": "Bank Transfer",
				"amount": 1500,
				"reference_no": "TRF-ADV-1",
				"reference_date": "2026-08-28",
			}
		)

		mock_branch_access.assert_called_once()
		mock_new_doc.assert_called_once_with("Payment Entry")
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.payment_type, "Receive")
		self.assertEqual(doc.party_type, "Customer")
		self.assertEqual(doc.party, "CUST-001")
		self.assertEqual(doc.paid_from, "Debtors - DC")
		self.assertEqual(doc.paid_to, "Bank - DC")
		self.assertEqual(doc.branch, "Lagos")
		self.assertFalse(hasattr(doc, "references"))
		self.assertTrue(result["advance_payment"])
		self.assertEqual(result["allocation_status"], "Unallocated")
		self.assertEqual(result["docstatus"], 0)

	@patch("retailedge.advanced_payments._assert_create_payment_entry")
	def test_customer_advance_rejects_invoice_references(self, _mock_create_permission):
		with self.assertRaises(frappe.ValidationError):
			create_customer_advance_draft(
				{
					"company": "Demo Company",
					"customer": "CUST-001",
					"references": [{"reference_name": "SINV-1", "allocated_amount": 100}],
				}
			)

	@patch("retailedge.advanced_payments._company_currency", return_value="NGN")
	@patch("retailedge.advanced_payments.list_customer_advances")
	@patch("retailedge.advanced_payments.validate_user_branch_access")
	@patch("retailedge.advanced_payments._assert_read")
	@patch("retailedge.advanced_payments.frappe.get_doc")
	def test_sales_invoice_advance_context_is_read_only_and_scoped(
		self,
		mock_get_doc,
		_mock_read,
		mock_branch_access,
		mock_list_advances,
		_mock_currency,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="SINV-0001",
			docstatus=1,
			customer="CUST-001",
			company="Demo Company",
			branch="Lagos",
			currency="NGN",
			outstanding_amount=2000,
		)
		mock_list_advances.return_value = [
			{"name": "ACC-PAY-1", "unallocated_amount": 500.0},
			{"name": "ACC-PAY-2", "unallocated_amount": 250.0},
		]

		context = get_sales_invoice_advance_context("SINV-0001")

		mock_branch_access.assert_called_once()
		mock_list_advances.assert_called_once_with(
			customer="CUST-001",
			company="Demo Company",
			branch="Lagos",
			limit=50,
		)
		self.assertEqual(context["available_advance"], 750.0)
		self.assertEqual(context["outstanding_amount"], 2000.0)
		self.assertFalse(context["application_write_enabled"])
		self.assertIn("never mutate submitted Sales Invoice", context["application_policy"])

	@patch("retailedge.advanced_payments._company_currency", return_value="NGN")
	@patch("retailedge.advanced_payments.list_customer_advances")
	@patch("retailedge.advanced_payments._assert_read")
	@patch("retailedge.advanced_payments.frappe.get_doc")
	def test_multi_currency_invoice_does_not_offer_simple_advance_application(
		self,
		mock_get_doc,
		_mock_read,
		mock_list_advances,
		_mock_currency,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="SINV-USD-1",
			docstatus=1,
			customer="CUST-001",
			company="Demo Company",
			currency="USD",
			outstanding_amount=100,
		)
		mock_list_advances.return_value = [{"name": "ACC-PAY-1", "unallocated_amount": 100.0}]

		context = get_sales_invoice_advance_context("SINV-USD-1")

		self.assertFalse(context["currency_supported"])
		self.assertEqual(context["eligible_advances"], [])
		self.assertEqual(context["available_advance"], 0.0)


if __name__ == "__main__":
	unittest.main()
