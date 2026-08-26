from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match import (
    _build_source_candidate_context,
)

MODULE = "retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match"


class PaymentEntrySourceCandidateDirectionTests(IntegrationTestCase):
    def _build_candidate(self, payload, bank_context=None):
        with (
            patch(f"{MODULE}.frappe.get_meta") as get_meta,
            patch(f"{MODULE}.frappe.db.get_value") as get_value,
        ):
            get_meta.return_value.has_field.side_effect = lambda fieldname: fieldname in {
                "mode_of_payment",
                "retailedge_branch",
            }
            get_value.return_value = frappe._dict(payload)
            return _build_source_candidate_context(
                "Payment Entry",
                payload["name"],
                bank_context=bank_context,
            )

    def test_supplier_outflow_uses_paid_from_and_paid_amount(self):
        result = self._build_candidate(
            {
                "name": "ACC-PAY-OUTFLOW",
                "posting_date": "2026-08-23",
                "company": "RetailEdge Consulting",
                "party": "Naijalivemedia",
                "party_type": "Supplier",
                "payment_type": "Pay",
                "paid_from": "Bank - RC",
                "paid_to": "Creditors - RC",
                "paid_amount": 750000,
                "received_amount": 742500,
                "reference_no": "supplier-payment",
                "mode_of_payment": "Access Bank",
            },
            bank_context={"bank_direction": "Outflow", "resolved_bank_account": "Bank - RC"},
        )

        self.assertEqual(result.get("payment_account"), "Bank - RC")
        self.assertEqual(result.get("account"), "Bank - RC")
        self.assertEqual(result.get("candidate_amount"), 750000)
        self.assertEqual(result.get("payment_entry_paid_amount"), 750000)

    def test_customer_inflow_uses_paid_to_and_received_amount(self):
        result = self._build_candidate(
            {
                "name": "ACC-PAY-INFLOW",
                "posting_date": "2026-08-23",
                "company": "RetailEdge Consulting",
                "party": "Customer A",
                "party_type": "Customer",
                "payment_type": "Receive",
                "paid_from": "Debtors - RC",
                "paid_to": "Bank - RC",
                "paid_amount": 495000,
                "received_amount": 500000,
                "reference_no": "customer-receipt",
                "mode_of_payment": "Access Bank",
            },
            bank_context={"bank_direction": "Inflow", "resolved_bank_account": "Bank - RC"},
        )

        self.assertEqual(result.get("payment_account"), "Bank - RC")
        self.assertEqual(result.get("account"), "Bank - RC")
        self.assertEqual(result.get("candidate_amount"), 500000)
        self.assertEqual(result.get("payment_entry_paid_amount"), 500000)

    def test_internal_transfer_uses_bank_transaction_direction(self):
        result = self._build_candidate(
            {
                "name": "ACC-PAY-TRANSFER",
                "posting_date": "2026-08-23",
                "company": "RetailEdge Consulting",
                "payment_type": "Internal Transfer",
                "paid_from": "Access Bank - RC",
                "paid_to": "Second Bank - RC",
                "paid_amount": 300000,
                "received_amount": 297500,
                "reference_no": "bank-transfer",
                "mode_of_payment": "Bank Transfer",
            },
            bank_context={"bank_direction": "Outflow", "resolved_bank_account": "Access Bank - RC"},
        )

        self.assertEqual(result.get("payment_account"), "Access Bank - RC")
        self.assertEqual(result.get("candidate_amount"), 300000)

    def test_internal_transfer_without_bank_direction_fails_closed(self):
        result = self._build_candidate(
            {
                "name": "ACC-PAY-TRANSFER",
                "posting_date": "2026-08-23",
                "company": "RetailEdge Consulting",
                "payment_type": "Internal Transfer",
                "paid_from": "Access Bank - RC",
                "paid_to": "Second Bank - RC",
                "paid_amount": 300000,
                "received_amount": 300000,
                "reference_no": "bank-transfer",
                "mode_of_payment": "Bank Transfer",
            },
            bank_context={},
        )

        self.assertIsNone(result)
