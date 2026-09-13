from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.reconciliation_approval import (
    APPROVAL_PENDING,
    _candidate_identity,
    build_reconciliation_approval_state,
)


class _DocumentLike:
    def __init__(self, payload):
        self._payload = dict(payload)
        for key, value in self._payload.items():
            setattr(self, key, value)

    def as_dict(self):
        return dict(self._payload)


class ReconciliationApprovalDocumentInputTests(unittest.TestCase):
    def _settings(self):
        return {
            "require_second_approval_for_reconciliation_execution": 1,
            "allowed_reconciliation_execution_roles": "System Manager\nAccounts Manager",
        }

    def _document(self):
        return _DocumentLike(
            {
                "name": "RE-BTM-2026-0082",
                "bank_transaction": "ACC-BTN-2026-00005",
                "suggested_document_type": "Sales Invoice",
                "suggested_document": "ACC-SINV-2026-00004",
                "payment_row_index": "1",
                "bank_amount": 150000,
                "candidate_amount": 150000,
                "resolved_payment_account": "Access Bank - RC",
                "decision_status": "Confirmed",
                "review_status": "Confirmed",
                "confirmed_by": "matcher@example.com",
                "confirmed_on": "2026-08-19 18:00:00",
                "approval_status": "Pending",
                "approval_candidate_identity": "",
                "approval_requested_by": None,
                "approval_requested_on": None,
                "approved_by": None,
                "approved_on": None,
                "approval_note": None,
            }
        )

    def test_state_builder_accepts_document_like_input(self):
        document = self._document()
        with patch("retailedge.reconciliation_approval.frappe.get_roles", return_value=["Accounts Manager"]):
            state = build_reconciliation_approval_state(
                document,
                user="approver@example.com",
                settings=self._settings(),
            )

        self.assertEqual(state["status"], APPROVAL_PENDING)
        self.assertTrue(state["can_approve"])
        self.assertEqual(state["candidate_identity"], _candidate_identity(document))

    def test_candidate_identity_accepts_document_like_input(self):
        document = self._document()
        identity = _candidate_identity(document)
        self.assertIn('"candidate_name":"ACC-SINV-2026-00004"', identity)
        self.assertIn('"bank_transaction":"ACC-BTN-2026-00005"', identity)


if __name__ == "__main__":
    unittest.main()
