from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.cashier_customer_receipt import (
	_build_payment_entry,
	_post_native_payment,
	_receipt_values,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class _PaymentStub:
	def __init__(self):
		self.flags = SimpleNamespace()
		self.references = []
		self.inserted = 0
		self.submitted = 0

	def set(self, fieldname, value):
		setattr(self, fieldname, value)

	def append(self, table, row):
		self.references.append(SimpleNamespace(**row))
		return self.references[-1]

	def insert(self, ignore_permissions=False):
		self.inserted += 1
		self.insert_ignore_permissions = ignore_permissions
		return self

	def submit(self):
		self.submitted += 1
		self.docstatus = 1
		return self


class TestCashierCustomerReceipt(unittest.TestCase):
	def test_receipt_values_allow_partial_payment_but_not_overpayment(self):
		invoice = SimpleNamespace(outstanding_amount=200000)
		with patch(
			"retailedge.cashier_customer_receipt._resolve_mode",
			return_value={
				"mode_of_payment": "Cash",
				"account": "Cash - RC",
				"account_type": "Cash",
				"account_currency": "NGN",
			},
		):
			values = _receipt_values(
				invoice,
				"RetailEdge Consulting",
				"Ketu",
				"NGN",
				{"posting_date": "2026-10-30", "mode_of_payment": "Cash", "amount": 75000},
			)
			self.assertEqual(values["amount"], 75000)
			self.assertEqual(values["remaining"], 125000)
			with self.assertRaises(frappe.ValidationError):
				_receipt_values(
					invoice,
					"RetailEdge Consulting",
					"Ketu",
					"NGN",
					{"posting_date": "2026-10-30", "mode_of_payment": "Cash", "amount": 200001},
				)

	def test_bank_payment_requires_reference_number(self):
		invoice = SimpleNamespace(outstanding_amount=100000)
		with patch(
			"retailedge.cashier_customer_receipt._resolve_mode",
			return_value={
				"mode_of_payment": "Bank Transfer",
				"account": "Bank - RC",
				"account_type": "Bank",
				"account_currency": "NGN",
			},
		):
			with self.assertRaises(frappe.ValidationError):
				_receipt_values(
					invoice,
					"RetailEdge Consulting",
					"Ketu",
					"NGN",
					{"posting_date": "2026-10-30", "mode_of_payment": "Bank Transfer", "amount": 100000},
				)

	@patch("retailedge.cashier_customer_receipt._payment_branch_field", return_value="retailedge_branch")
	@patch("retailedge.cashier_customer_receipt.frappe.new_doc")
	def test_payment_entry_is_exactly_bound_to_the_invoice(self, mock_new_doc, _mock_branch_field):
		payment = _PaymentStub()
		mock_new_doc.return_value = payment
		invoice = SimpleNamespace(
			name="ACC-SINV-2026-00038",
			company="RetailEdge Consulting",
			customer="CUST-001",
			debit_to="Debtors - RC",
			due_date="2026-10-01",
			grand_total=200000,
		)
		receipt = {
			"posting_date": "2026-10-30",
			"mode_of_payment": "Cash",
			"mode": {"account": "Cash - RC", "account_type": "Cash"},
			"amount": 50000,
			"reference_no": "",
			"reference_date": "2026-10-30",
			"outstanding": 200000,
		}

		result = _build_payment_entry(invoice, "Ketu", receipt)
		self.assertIs(result, payment)
		self.assertEqual(payment.payment_type, "Receive")
		self.assertEqual(payment.party_type, "Customer")
		self.assertEqual(payment.party, "CUST-001")
		self.assertEqual(payment.paid_from, "Debtors - RC")
		self.assertEqual(payment.paid_to, "Cash - RC")
		self.assertEqual(payment.retailedge_branch, "Ketu")
		self.assertEqual(len(payment.references), 1)
		self.assertEqual(payment.references[0].reference_doctype, "Sales Invoice")
		self.assertEqual(payment.references[0].reference_name, "ACC-SINV-2026-00038")
		self.assertEqual(payment.references[0].allocated_amount, 50000)

	def test_posting_exception_keeps_native_document_hooks_and_ledger_posting(self):
		payment = _PaymentStub()
		previous = getattr(frappe.flags, "ignore_account_permission", False)
		_post_native_payment(payment)
		self.assertEqual(payment.inserted, 1)
		self.assertTrue(payment.insert_ignore_permissions)
		self.assertEqual(payment.submitted, 1)
		self.assertTrue(payment.flags.ignore_permissions)
		self.assertEqual(getattr(frappe.flags, "ignore_account_permission", False), previous)

	def test_server_boundary_is_cashier_invoice_branch_and_concurrency_scoped(self):
		source = (APP_ROOT / "cashier_customer_receipt.py").read_text(encoding="utf-8")
		for contract in (
			'user_has_retailedge_role(CASHIER_ROLE, user=user)',
			'frappe.has_permission(SALES_INVOICE_DOCTYPE, "read", doc=invoice)',
			"validate_user_branch_access(",
			"get_operational_branch_scope(",
			'"SELECT name FROM `tabSales Invoice` WHERE name = %s FOR UPDATE"',
			"expected_invoice_modified",
			"expected_outstanding_amount",
			'payment.payment_type = "Receive"',
			'payment.party_type = "Customer"',
			'"reference_doctype": SALES_INVOICE_DOCTYPE',
			"payment.insert(ignore_permissions=True)",
			"payment.submit()",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"frappe.db.commit()",
			'frappe.db.set_value("Sales Invoice"',
			'frappe.new_doc("GL Entry")',
			'frappe.new_doc("Payment Ledger Entry")',
		):
			self.assertNotIn(forbidden, source)

	def test_cashier_still_does_not_receive_generic_payment_entry_permission(self):
		permissions = (APP_ROOT / "patches" / "ensure_retailedge_cashier_selling_document_permissions.py").read_text(encoding="utf-8")
		persona = (APP_ROOT / "tests" / "test_persona_effective_permissions.py").read_text(encoding="utf-8")
		self.assertNotIn('"Payment Entry"', permissions)
		self.assertIn('for doctype in ("Payment Entry", "Journal Entry", "Purchase Invoice"):', persona)
		self.assertIn('{"read": False, "create": False, "write": False, "submit": False, "cancel": False}', persona)

	def test_professional_selling_exposes_receipt_only_for_outstanding_submitted_invoice(self):
		records = (APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSellingRecords.vue").read_text(encoding="utf-8")
		for contract in (
			'const CASHIER_RECEIPT_ACTION = "cashier-receive-payment"',
			'this.activeDocument?.key === "sales-invoice"',
			'Number(row?.docstatus || 0) === 1',
			'!Number(row?.is_return || 0)',
			'Number(row?.outstanding_amount || 0) > 0.005',
			'label: "Receive Payment"',
			'frappe.set_route("cashier-customer-receipt", row.name)',
		):
			self.assertIn(contract, records)

	def test_receipt_page_uses_edgesuite_review_then_post_contract(self):
		page = json.loads(
			(APP_ROOT / "retailedge" / "page" / "cashier_customer_receipt" / "cashier_customer_receipt.json").read_text(encoding="utf-8")
		)
		roles = {row.get("role") for row in page.get("roles") or []}
		self.assertEqual(roles, {"RetailEdgeCashier", "RetailEdge Cashier"})
		component = (APP_ROOT / "public" / "js" / "cashier_customer_receipt" / "CashierCustomerReceipt.vue").read_text(encoding="utf-8")
		for contract in (
			"EdgeAppShell",
			"EdgeLinkField",
			'"Review Payment"',
			'"Post Payment"',
			"expected_invoice_modified",
			"expected_outstanding_amount",
			'POST_METHOD',
			'"POST"',
		):
			self.assertIn(contract, component)


if __name__ == "__main__":
	unittest.main()
