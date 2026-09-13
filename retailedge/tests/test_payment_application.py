from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

import frappe

from retailedge.payment_application import (
	apply_customer_advance,
	apply_customer_advances,
	create_sales_invoice_payment_draft,
)


class _Row(frappe._dict):
	def as_dict(self):
		return dict(self)


class _FakeReconciliation(SimpleNamespace):
	def __init__(self):
		super().__init__(payments=[], invoices=[], allocation=[], get_calls=0, allocate_calls=0, reconcile_calls=0)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def get_unreconciled_entries(self):
		self.get_calls += 1
		self.payments = [_Row(reference_type="Payment Entry", reference_name="ACC-PAY-ADV-1", amount=1200.0, posting_date="2026-08-28", currency="NGN")]
		self.invoices = [_Row(invoice_type="Sales Invoice", invoice_number="SINV-0001", outstanding_amount=900.0, invoice_date="2026-08-28", currency="NGN")]

	def allocate_entries(self, args):
		self.allocate_calls += 1
		self.allocation = [_Row(allocated_amount=900.0, difference_amount=0, amount=1200.0, unreconciled_amount=1200.0)]

	def reconcile(self):
		self.reconcile_calls += 1


class TestPaymentApplication(unittest.TestCase):
	@patch("retailedge.payment_application.frappe.db.get_value")
	@patch("retailedge.payment_application._payment_branch", return_value="Lagos")
	@patch("retailedge.payment_application._invoice_branch", return_value="Lagos")
	@patch("retailedge.payment_application.validate_user_branch_access")
	@patch("retailedge.payment_application._company_currency", return_value="NGN")
	@patch("retailedge.payment_application._assert_read")
	@patch("retailedge.payment_application._assert_reconciliation_permission")
	@patch("retailedge.payment_application.frappe.get_doc")
	@patch("retailedge.payment_application.frappe.new_doc")
	def test_apply_advance_delegates_write_to_payment_reconciliation(self, mock_new_doc, mock_get_doc, _mock_reconcile_permission, _mock_read, _mock_currency, mock_branch_access, _mock_invoice_branch, _mock_payment_branch, mock_db_value):
		invoice = SimpleNamespace(name="SINV-0001", docstatus=1, customer="CUST-001", company="Demo Company", currency="NGN", outstanding_amount=900.0, debit_to="Debtors - DC")
		payment = SimpleNamespace(name="ACC-PAY-ADV-1", docstatus=1, payment_type="Receive", party_type="Customer", party="CUST-001", company="Demo Company", unallocated_amount=1200.0, paid_from="Debtors - DC", paid_from_account_currency="NGN", book_advance_payments_in_separate_party_account=0)
		mock_get_doc.side_effect = [invoice, payment]
		reconciliation = _FakeReconciliation()
		mock_new_doc.return_value = reconciliation
		mock_db_value.side_effect = lambda doctype, name, field: 400.0 if doctype == "Sales Invoice" else 700.0

		result = apply_customer_advance("SINV-0001", "ACC-PAY-ADV-1", 500)

		self.assertEqual(mock_branch_access.call_count, 2)
		for branch_call in mock_branch_access.call_args_list:
			self.assertEqual(branch_call.args[0], "Lagos")
			self.assertEqual(branch_call.kwargs.get("company"), "Demo Company")
			self.assertTrue(branch_call.kwargs.get("throw"))
		mock_new_doc.assert_called_once_with("Payment Reconciliation")
		self.assertEqual(reconciliation.company, "Demo Company")
		self.assertEqual(reconciliation.party_type, "Customer")
		self.assertEqual(reconciliation.party, "CUST-001")
		self.assertEqual(reconciliation.receivable_payable_account, "Debtors - DC")
		self.assertEqual(reconciliation.payment_name, "ACC-PAY-ADV-1")
		self.assertEqual(reconciliation.invoice_name, "SINV-0001")
		self.assertEqual(reconciliation.get_calls, 1)
		self.assertEqual(reconciliation.allocate_calls, 1)
		self.assertEqual(reconciliation.reconcile_calls, 1)
		self.assertEqual(reconciliation.allocation[0].allocated_amount, 500.0)
		self.assertEqual(result["source_of_truth"], "Payment Reconciliation")
		self.assertEqual(result["invoice_outstanding_amount"], 400.0)
		self.assertEqual(result["payment_unallocated_amount"], 700.0)

	@patch("retailedge.payment_application._assert_read")
	@patch("retailedge.payment_application._assert_reconciliation_permission")
	@patch("retailedge.payment_application.frappe.get_doc")
	def test_apply_advance_rejects_customer_company_mismatch(self, mock_get_doc, _mock_permission, _mock_read):
		mock_get_doc.side_effect = [SimpleNamespace(docstatus=1, customer="CUST-001", company="Demo Company", outstanding_amount=500), SimpleNamespace(docstatus=1, payment_type="Receive", party_type="Customer", party="CUST-002", company="Demo Company", unallocated_amount=500)]
		with self.assertRaises(frappe.ValidationError):
			apply_customer_advance("SINV-0001", "ACC-PAY-1", 100)

	@patch("retailedge.payment_application._assert_read")
	@patch("retailedge.payment_application._assert_reconciliation_permission")
	@patch("retailedge.payment_application.frappe.get_doc")
	def test_apply_advance_rejects_amount_over_available_payment(self, mock_get_doc, _mock_permission, _mock_read):
		mock_get_doc.side_effect = [SimpleNamespace(docstatus=1, customer="CUST-001", company="Demo Company", outstanding_amount=1000), SimpleNamespace(docstatus=1, payment_type="Receive", party_type="Customer", party="CUST-001", company="Demo Company", unallocated_amount=200)]
		with self.assertRaises(frappe.ValidationError):
			apply_customer_advance("SINV-0001", "ACC-PAY-1", 300)

	@patch("retailedge.payment_application._company_currency", return_value="NGN")
	@patch("retailedge.payment_application._assert_read")
	@patch("retailedge.payment_application._assert_reconciliation_permission")
	@patch("retailedge.payment_application.frappe.get_doc")
	def test_apply_advance_redirects_separate_advance_account_to_full_reconciliation(self, mock_get_doc, _mock_permission, _mock_read, _mock_currency):
		mock_get_doc.side_effect = [SimpleNamespace(docstatus=1, customer="CUST-001", company="Demo Company", currency="NGN", outstanding_amount=1000), SimpleNamespace(docstatus=1, payment_type="Receive", party_type="Customer", party="CUST-001", company="Demo Company", unallocated_amount=500, paid_from_account_currency="NGN", book_advance_payments_in_separate_party_account=1)]
		with self.assertRaises(frappe.ValidationError):
			apply_customer_advance("SINV-0001", "ACC-PAY-1", 300)

	@patch("retailedge.payment_application.frappe.db.get_value", return_value=250.0)
	@patch("retailedge.payment_application.apply_customer_advance")
	def test_apply_customer_advances_reuses_reconciliation_primitive_in_one_request(self, mock_apply, _mock_get_value):
		mock_apply.side_effect = [
			{"payment_entry": "ACC-PAY-1", "allocated_amount": 400.0, "source_of_truth": "Payment Reconciliation"},
			{"payment_entry": "ACC-PAY-2", "allocated_amount": 350.0, "source_of_truth": "Payment Reconciliation"},
		]

		result = apply_customer_advances(
			"SINV-0001",
			frappe.as_json(
				[
					{"payment_entry": "ACC-PAY-1", "allocated_amount": 400},
					{"payment_entry": "ACC-PAY-2", "allocated_amount": 350},
				]
			),
		)

		self.assertEqual(
			mock_apply.call_args_list,
			[
				call(sales_invoice="SINV-0001", payment_entry="ACC-PAY-1", allocated_amount=400.0),
				call(sales_invoice="SINV-0001", payment_entry="ACC-PAY-2", allocated_amount=350.0),
			],
		)
		self.assertEqual(result["applied_count"], 2)
		self.assertEqual(result["allocated_amount"], 750.0)
		self.assertEqual(result["invoice_outstanding_amount"], 250.0)
		self.assertEqual(result["source_of_truth"], "Payment Reconciliation")

	@patch("retailedge.payment_application.apply_customer_advance")
	def test_apply_customer_advances_rejects_duplicate_payment_entry(self, mock_apply):
		with self.assertRaises(frappe.ValidationError):
			apply_customer_advances(
				"SINV-0001",
				[
					{"payment_entry": "ACC-PAY-1", "allocated_amount": 100},
					{"payment_entry": "ACC-PAY-1", "allocated_amount": 50},
				],
			)
		mock_apply.assert_not_called()

	@patch("retailedge.payment_application.create_simple_payment_draft")
	@patch("retailedge.payment_application.validate_user_branch_access")
	@patch("retailedge.payment_application._assert_read")
	@patch("retailedge.payment_application.frappe.get_doc")
	def test_sales_invoice_payment_draft_derives_invoice_authority_server_side(self, mock_get_doc, _mock_read, mock_branch_access, mock_create_draft):
		mock_get_doc.return_value = SimpleNamespace(
			name="SINV-0001",
			docstatus=1,
			is_return=0,
			customer="CUST-001",
			company="Demo Company",
			branch="Lagos",
			outstanding_amount=900.0,
		)
		mock_create_draft.return_value = {"name": "ACC-PAY-DRAFT-1", "docstatus": 0, "route": "/app/payment-entry/ACC-PAY-DRAFT-1"}

		result = create_sales_invoice_payment_draft(
			"SINV-0001",
			{
				"company": "Wrong Company",
				"party": "WRONG-CUSTOMER",
				"branch": "Wrong Branch",
				"posting_date": "2026-08-30",
				"mode_of_payment": "Cash",
				"amount": 300,
			},
		)

		mock_branch_access.assert_called_once_with("Lagos", user=frappe.session.user, company="Demo Company", throw=True)
		mock_create_draft.assert_called_once()
		intent, values = mock_create_draft.call_args.args
		self.assertEqual(intent, "receive-customer-payment")
		self.assertEqual(values["company"], "Demo Company")
		self.assertEqual(values["party"], "CUST-001")
		self.assertEqual(values["branch"], "Lagos")
		self.assertEqual(values["references"], [{"reference_name": "SINV-0001", "allocated_amount": 300.0}])
		self.assertEqual(result["posting_status"], "Draft")
		self.assertEqual(result["outstanding_effect"], "none_until_payment_entry_submission")
		self.assertEqual(result["authoritative_outstanding_amount"], 900.0)


if __name__ == "__main__":
	unittest.main()
