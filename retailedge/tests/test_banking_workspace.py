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
    STATUS_SUGGESTED,
)


class BankingWorkspaceTests(unittest.TestCase):
    def test_queue_mapping_keeps_matching_and_reconciliation_separate(self):
        self.assertTrue(_status_belongs_to_queue(STATUS_SUGGESTED, QUEUE_TO_MATCH))
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

    @patch("retailedge.banking_workspace.get_bank_match_operational_status")
    @patch("retailedge.banking_workspace.frappe.get_all")
    def test_workspace_direction_filters_before_returning_rows(self, get_all, operational):
        get_all.return_value = [
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
                "can_execute": True,
            },
            {
                "direction": "Outflow",
                "transaction_category": "Expense",
                "operational_status": STATUS_READY_TO_RECONCILE,
                "can_execute": True,
            },
        ]

        payload = get_banking_workspace_rows(direction="Outflow", queue=QUEUE_TO_RECONCILE)

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["rows"][0]["bank_transaction"], "BT-OUT")
        self.assertEqual(payload["rows"][0]["direction"], "Outflow")


if __name__ == "__main__":
    unittest.main()
