from __future__ import annotations

import unittest
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
    STATUS_UNMATCHED,
)


class BankingWorkspaceTests(unittest.TestCase):
    def test_queue_mapping_keeps_matching_and_reconciliation_separate(self):
        self.assertTrue(_status_belongs_to_queue(STATUS_UNMATCHED, QUEUE_TO_MATCH))
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

    @patch("retailedge.banking_workspace.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_workspace._get_review_queue_rows")
    def test_review_queue_receives_direction_and_user_filters(self, review_rows, _assert_access):
        review_rows.return_value = (
            [
                {
                    "bank_transaction": "BT-OUT",
                    "direction": "Outflow",
                    "operational_status": STATUS_READY_TO_RECONCILE,
                }
            ],
            0,
        )
        payload = get_banking_workspace_rows(
            direction="Outflow",
            queue=QUEUE_TO_RECONCILE,
            company="Demo",
            bank_account="BANK-1",
            from_date="2026-08-01",
            to_date="2026-08-31",
            search="supplier",
        )
        self.assertEqual(payload["count"], 1)
        args = review_rows.call_args.args
        filters = args[3]
        self.assertEqual(args[0], "Outflow")
        self.assertEqual(args[1], QUEUE_TO_RECONCILE)
        self.assertEqual(filters.company, "Demo")
        self.assertEqual(filters.bank_account, "BANK-1")
        self.assertEqual(filters.search, "supplier")

    @patch("retailedge.banking_workspace.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_workspace._get_review_queue_rows")
    @patch("retailedge.banking_workspace._get_unmatched_bank_transaction_rows")
    def test_to_match_combines_unmatched_and_suggested_without_losing_suggestions(
        self, unmatched_rows, review_rows, _assert_access
    ):
        unmatched_rows.return_value = (
            [
                {
                    "bank_transaction": "BT-NEW",
                    "transaction_date": "2026-08-18",
                    "direction": "Inflow",
                    "operational_status": STATUS_UNMATCHED,
                }
            ],
            0,
        )
        review_rows.return_value = (
            [
                {
                    "bank_transaction": "BT-SUGGESTED",
                    "transaction_date": "2026-08-17",
                    "direction": "Inflow",
                    "operational_status": STATUS_SUGGESTED,
                    "match_name": "MATCH-1",
                }
            ],
            0,
        )
        payload = get_banking_workspace_rows(direction="Inflow", queue=QUEUE_TO_MATCH)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            {row["operational_status"] for row in payload["rows"]},
            {STATUS_UNMATCHED, STATUS_SUGGESTED},
        )

    @patch("retailedge.banking_workspace.assert_can_access_bank_transaction_matching")
    @patch("retailedge.banking_workspace._get_review_queue_rows")
    @patch("retailedge.banking_workspace._get_unmatched_bank_transaction_rows")
    def test_to_match_respects_requested_result_limit_after_combining_sources(
        self, unmatched_rows, review_rows, _assert_access
    ):
        unmatched_rows.return_value = (
            [
                {
                    "bank_transaction": f"BT-{index}",
                    "transaction_date": f"2026-08-{18-index:02d}",
                    "operational_status": STATUS_UNMATCHED,
                }
                for index in range(4)
            ],
            0,
        )
        review_rows.return_value = (
            [
                {
                    "bank_transaction": "BT-SUGGESTED",
                    "transaction_date": "2026-08-19",
                    "operational_status": STATUS_SUGGESTED,
                }
            ],
            0,
        )
        payload = get_banking_workspace_rows(direction="All", queue=QUEUE_TO_MATCH, limit=3)
        self.assertEqual(payload["count"], 3)


if __name__ == "__main__":
    unittest.main()
