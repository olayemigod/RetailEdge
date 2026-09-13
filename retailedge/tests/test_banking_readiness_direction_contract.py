from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from retailedge.reconciliation_handoff import get_payment_event_reconciliation_context


class BankingReadinessDirectionContractTests(IntegrationTestCase):
    @patch("retailedge.reconciliation_handoff.has_doctype", return_value=True)
    @patch("retailedge.reconciliation_handoff.has_field", return_value=False)
    @patch("retailedge.reconciliation_handoff.frappe.db.get_value")
    def test_supplier_pay_uses_paid_from_and_paid_amount(
        self,
        get_value,
        _has_field,
        _has_doctype,
    ):
        get_value.return_value = frappe._dict(
            {
                "name": "ACC-PAY-OUTFLOW",
                "posting_date": "2026-08-23",
                "payment_type": "Pay",
                "paid_from": "Access Bank - RC",
                "paid_to": "Creditors - RC",
                "paid_amount": 750000,
                "received_amount": 750000,
                "docstatus": 1,
            }
        )

        result = get_payment_event_reconciliation_context(
            "Payment Entry",
            "ACC-PAY-OUTFLOW",
            match_doc=frappe._dict({"direction": "Outflow"}),
        )

        self.assertEqual(result.get("candidate_account"), "Access Bank - RC")
        self.assertEqual(result.get("candidate_amount"), 750000)

    @patch("retailedge.reconciliation_handoff.has_doctype", return_value=True)
    @patch("retailedge.reconciliation_handoff.has_field", return_value=False)
    @patch("retailedge.reconciliation_handoff.frappe.db.get_value")
    def test_customer_receive_uses_paid_to_and_received_amount(
        self,
        get_value,
        _has_field,
        _has_doctype,
    ):
        get_value.return_value = frappe._dict(
            {
                "name": "ACC-PAY-INFLOW",
                "posting_date": "2026-08-23",
                "payment_type": "Receive",
                "paid_from": "Debtors - RC",
                "paid_to": "Access Bank - RC",
                "paid_amount": 500000,
                "received_amount": 500000,
                "docstatus": 1,
            }
        )

        result = get_payment_event_reconciliation_context(
            "Payment Entry",
            "ACC-PAY-INFLOW",
            match_doc=frappe._dict({"direction": "Inflow"}),
        )

        self.assertEqual(result.get("candidate_account"), "Access Bank - RC")
        self.assertEqual(result.get("candidate_amount"), 500000)
