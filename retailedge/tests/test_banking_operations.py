from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.banking_operations import (
    CATEGORY_BANK_DEPOSIT,
    CATEGORY_CUSTOMER_RECEIPT,
    CATEGORY_EXPENSE,
    CATEGORY_POS_SALE,
    CATEGORY_SUPPLIER_PAYMENT,
    DIRECTION_INFLOW,
    DIRECTION_OUTFLOW,
    STATUS_EXCEPTION,
    STATUS_NEEDS_REVIEW,
    STATUS_PAYMENT_EVIDENCE_REQUIRED,
    STATUS_READY_TO_RECONCILE,
    STATUS_RECONCILED,
    STATUS_RECONCILIATION_FAILED,
    classify_transaction_category,
    derive_operational_status,
    direction_matches,
    get_bank_transaction_direction,
    match_and_reconcile,
    normalize_direction,
)


class BankingOperationsTests(unittest.TestCase):
    def test_direction_aliases_normalize_to_canonical_values(self):
        self.assertEqual(normalize_direction("credit"), DIRECTION_INFLOW)
        self.assertEqual(normalize_direction("deposit"), DIRECTION_INFLOW)
        self.assertEqual(normalize_direction("debit"), DIRECTION_OUTFLOW)
        self.assertEqual(normalize_direction("withdrawal"), DIRECTION_OUTFLOW)

    @patch("retailedge.banking_operations.normalize_bank_transaction")
    def test_bank_transaction_direction_prefers_canonical_inflow(self, normalize):
        normalize.return_value = {"direction": "Inflow"}
        self.assertEqual(get_bank_transaction_direction("BT-1"), DIRECTION_INFLOW)

    @patch("retailedge.banking_operations.frappe.throw", side_effect=ValueError("unknown direction"))
    @patch("retailedge.banking_operations.normalize_bank_transaction")
    def test_bank_transaction_direction_fails_closed_when_unknown(self, normalize, _throw):
        normalize.return_value = {"direction": "Unknown"}
        with self.assertRaises(ValueError):
            get_bank_transaction_direction("BT-1")

    @patch("retailedge.banking_operations.get_bank_transaction_direction", return_value=DIRECTION_OUTFLOW)
    def test_direction_filter_allows_all_or_matching_direction(self, _direction):
        self.assertTrue(direction_matches("BT-2", "All"))
        self.assertTrue(direction_matches("BT-2", "Outflow"))
        self.assertFalse(direction_matches("BT-2", "Inflow"))

    def test_pos_payment_row_is_classified_as_pos_sale(self):
        category = classify_transaction_category(
            {
                "suggested_document_type": "Sales Invoice",
                "candidate_category": "Sales Invoice Payment Row",
                "payment_event_source": "POS Payment Row",
            },
            DIRECTION_INFLOW,
        )
        self.assertEqual(category, CATEGORY_POS_SALE)

    def test_deposit_to_bank_is_first_class_inflow_category(self):
        category = classify_transaction_category(
            {
                "suggested_document_type": "Journal Entry",
                "candidate_category": "Deposit to Bank",
                "payment_event_source": "Deposit to Bank",
            },
            DIRECTION_INFLOW,
        )
        self.assertEqual(category, CATEGORY_BANK_DEPOSIT)

    def test_bank_paid_expense_is_first_class_outflow_category(self):
        category = classify_transaction_category(
            {
                "suggested_document_type": "Expense Claim",
                "candidate_category": "Expense Payment",
            },
            DIRECTION_OUTFLOW,
        )
        self.assertEqual(category, CATEGORY_EXPENSE)

    def test_customer_and_supplier_payment_categories_follow_business_context(self):
        self.assertEqual(
            classify_transaction_category(
                {"suggested_document_type": "Payment Entry", "party_type": "Customer"},
                DIRECTION_INFLOW,
            ),
            CATEGORY_CUSTOMER_RECEIPT,
        )
        self.assertEqual(
            classify_transaction_category(
                {"suggested_document_type": "Payment Entry", "party_type": "Supplier"},
                DIRECTION_OUTFLOW,
            ),
            CATEGORY_SUPPLIER_PAYMENT,
        )

    def test_confirmed_ready_match_becomes_ready_to_reconcile(self):
        status = derive_operational_status(
            {"decision_status": "Confirmed", "execution_status": "Not Executed"},
            {
                "status": "Ready",
                "readiness_group": "Ready",
                "erpnext_target_status": "Reconciliation Target Available",
            },
        )
        self.assertEqual(status, STATUS_READY_TO_RECONCILE)

    def test_missing_payment_voucher_is_not_treated_as_reconciled(self):
        status = derive_operational_status(
            {"decision_status": "Confirmed", "execution_status": "Not Executed"},
            {
                "status": "Not Ready",
                "readiness_group": "Blocked",
                "erpnext_target_status": "Payment Voucher Missing",
            },
        )
        self.assertEqual(status, STATUS_PAYMENT_EVIDENCE_REQUIRED)

    def test_ambiguous_target_becomes_exception(self):
        status = derive_operational_status(
            {"decision_status": "Confirmed", "execution_status": "Not Executed"},
            {"status": "Target Ambiguous", "readiness_group": "Blocked"},
        )
        self.assertEqual(status, STATUS_EXCEPTION)

    def test_needs_review_remains_needs_review(self):
        status = derive_operational_status(
            {"decision_status": "Needs Review", "execution_status": "Not Executed"},
            {"status": "Needs Review", "readiness_group": "Needs Review"},
        )
        self.assertEqual(status, STATUS_NEEDS_REVIEW)

    def test_executed_or_already_reconciled_is_terminal_reconciled(self):
        self.assertEqual(
            derive_operational_status(
                {"decision_status": "Confirmed", "execution_status": "Executed"}, {}
            ),
            STATUS_RECONCILED,
        )
        self.assertEqual(
            derive_operational_status(
                {"decision_status": "Confirmed", "execution_status": "Not Executed"},
                {"status": "Already Reconciled", "readiness_group": "Already Handled"},
            ),
            STATUS_RECONCILED,
        )

    def test_failed_execution_has_visible_operational_status(self):
        self.assertEqual(
            derive_operational_status(
                {"decision_status": "Confirmed", "execution_status": "Failed"}, {}
            ),
            STATUS_RECONCILIATION_FAILED,
        )

    @patch("retailedge.banking_operations.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_operations.assert_can_manage_bank_transaction_match")
    @patch("retailedge.banking_operations.get_bank_match_operational_status")
    @patch("retailedge.banking_operations.execute_reconciliation_for_match")
    @patch("retailedge.banking_operations._load_match")
    def test_match_and_reconcile_requires_final_confirmation(
        self,
        load_match,
        execute,
        operational,
        _assert_manage,
        _assert_access,
    ):
        load_match.return_value = frappe._dict(
            {"name": "MATCH-1", "decision_status": "Confirmed", "bank_transaction": "BT-1"}
        )
        operational.return_value = {
            "operational_status": STATUS_READY_TO_RECONCILE,
            "recommended_action": "Reconcile",
        }

        result = match_and_reconcile("MATCH-1", confirm_reconciliation=False)

        self.assertEqual(result["status"], "Reconciliation Confirmation Required")
        execute.assert_not_called()

    @patch("retailedge.banking_operations.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_operations.assert_can_manage_bank_transaction_match")
    @patch("retailedge.banking_operations.get_bank_match_operational_status")
    @patch("retailedge.banking_operations.execute_reconciliation_for_match")
    @patch("retailedge.banking_operations._load_match")
    def test_match_and_reconcile_delegates_execution_to_existing_bridge(
        self,
        load_match,
        execute,
        operational,
        _assert_manage,
        _assert_access,
    ):
        load_match.return_value = frappe._dict(
            {"name": "MATCH-1", "decision_status": "Confirmed", "bank_transaction": "BT-1"}
        )
        operational.side_effect = [
            {"operational_status": STATUS_READY_TO_RECONCILE, "recommended_action": "Reconcile"},
            {"operational_status": STATUS_RECONCILED},
        ]
        execute.return_value = {
            "execution_status": "Executed",
            "message": "Reconciled through ERPNext.",
        }

        result = match_and_reconcile("MATCH-1", confirm_reconciliation=True)

        execute.assert_called_once_with("MATCH-1", confirm=True)
        self.assertEqual(result["status"], "Executed")
        self.assertEqual(result["operational"]["operational_status"], STATUS_RECONCILED)


if __name__ == "__main__":
    unittest.main()
