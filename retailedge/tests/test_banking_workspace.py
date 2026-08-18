from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.banking_workspace import (
    QUEUE_EXCEPTIONS,
    QUEUE_RECONCILED,
    QUEUE_TO_MATCH,
    QUEUE_TO_RECONCILE,
    _status_belongs_to_queue,
    get_banking_workspace_rows,
)
from retailedge.banking_operations import (
    STATUS_EXCEPTION,
    STATUS_NEEDS_REVIEW,
    STATUS_PAYMENT_EVIDENCE_REQUIRED,
    STATUS_READY_TO_RECONCILE,
    STATUS_RECONCILED,
    STATUS_RECONCILIATION_FAILED,
    STATUS_RECONCILIATION_PENDING,
    STATUS_UNMATCHED,
)


class BankingWorkspaceTests(unittest.TestCase):
    def test_queue_mapping_keeps_matching_and_reconciliation_separate(self):
        self.assertTrue(_status_belongs_to_queue(STATUS_UNMATCHED, QUEUE_TO_MATCH))
        self.assertTrue(_status_belongs_to_queue(STATUS_READY_TO_RECONCILE, QUEUE_TO_RECONCILE))
        self.assertTrue(_status_belongs_to_queue(STATUS_RECONCILIATION_PENDING, QUEUE_TO_RECONCILE))
        self.assertTrue(_status_belongs_to_queue(STATUS_RECONCILED, QUEUE_RECONCILED))

    def test_exception_queue_contains_manual_and_failed_cases(self):
        for status in (
            STATUS_NEEDS_REVIEW,
            STATUS_PAYMENT_EVIDENCE_REQUIRED,
            STATUS_EXCEPTION,
            STATUS_RECONCILIATION_FAILED,
        ):
            self.assertTrue(_status_belongs_to_queue(status, QUEUE_EXCEPTIONS))

    @patch("retailedge.banking_workspace.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_workspace.get_bank_match_operational_status")
    @patch("retailedge.banking_workspace.frappe.get_list")
    def test_workspace_direction_filters_review_queue_rows(
        self, get_list, operational, _assert_access
    ):
        get_list.return_value = [
            SimpleNamespace(
                name="MATCH-IN",
                bank_transaction="BT-IN",
                transaction_date="2026-08-18",
                bank_amount=100000,
                suggested_document_type="Payment Entry",
                suggested_document="PE-IN",
                decision_status="Confirmed",
                review_status="Confirmed",
                match_confidence="Strong Match",
                match_score=100,
                company="Demo",
                branch="HQ",
                bank_account="Bank",
            ),
            SimpleNamespace(
                name="MATCH-OUT",
                bank_transaction="BT-OUT",
                transaction_date="2026-08-18",
                bank_amount=75000,
                suggested_document_type="Expense Claim",
                suggested_document="EXP-1",
                decision_status="Confirmed",
                review_status="Confirmed",
                match_confidence="Strong Match",
                match_score=100,
                company="Demo",
                branch="HQ",
                bank_account="Bank",
            ),
        ]
        operational.side_effect = [
            {
                "direction": "Inflow",
                "transaction_category": "Customer Receipt",
                "operational_status": STATUS_READY_TO_RECONCILE,
                "can_execute": None,
            },
            {
                "direction": "Outflow",
                "transaction_category": "Expense",
                "operational_status": STATUS_READY_TO_RECONCILE,
                "can_execute": None,
            },
        ]

        payload = get_banking_workspace_rows(direction="Outflow", queue=QUEUE_TO_RECONCILE)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["rows"][0]["bank_transaction"], "BT-OUT")
        self.assertEqual(payload["rows"][0]["direction"], "Outflow")
        operational.assert_any_call("MATCH-IN", include_gate=False)
        operational.assert_any_call("MATCH-OUT", include_gate=False)

    @patch("retailedge.banking_workspace.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_workspace.normalize_bank_transaction")
    @patch("retailedge.banking_workspace.frappe.get_list")
    def test_to_match_queue_comes_from_unreconciled_bank_transactions(
        self, get_list, normalize, _assert_access
    ):
        bank_rows = [
            SimpleNamespace(name="BT-IN"),
            SimpleNamespace(name="BT-OUT"),
        ]
        get_list.side_effect = [bank_rows, []]
        normalize.side_effect = [
            {
                "bank_transaction": "BT-IN",
                "transaction_date": "2026-08-18",
                "amount": 100000,
                "direction": "Inflow",
                "company": "Demo",
                "bank_account": "Bank",
                "branch": "HQ",
                "is_reconciled": False,
            },
            {
                "bank_transaction": "BT-OUT",
                "transaction_date": "2026-08-18",
                "amount": 75000,
                "direction": "Outflow",
                "company": "Demo",
                "bank_account": "Bank",
                "branch": "HQ",
                "is_reconciled": False,
            },
        ]

        payload = get_banking_workspace_rows(direction="Inflow", queue=QUEUE_TO_MATCH)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["rows"][0]["bank_transaction"], "BT-IN")
        self.assertEqual(payload["rows"][0]["operational_status"], STATUS_UNMATCHED)
        self.assertEqual(payload["rows"][0]["direction"], "Inflow")


if __name__ == "__main__":
    unittest.main()
