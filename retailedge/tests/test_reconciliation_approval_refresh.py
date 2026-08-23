from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.reconciliation_approval import (
    APPROVAL_APPROVED,
    approve_reconciliation_for_match,
)


class _StaleSupplierMatch:
    def __init__(self):
        self.name = "RE-BTM-2026-0095"
        self.bank_transaction = "ACC-BTN-2026-00009"
        self.suggested_document_type = "Payment Entry"
        self.suggested_document = "ACC-PAY-2026-00001"
        self.payment_row_index = None
        self.bank_amount = 750000
        self.candidate_amount = 750000
        self.payment_account = "Creditors - RC"
        self.resolved_payment_account = "Creditors - RC"
        self.decision_status = "Confirmed"
        self.review_status = "Confirmed"
        self.confirmed_by = "matcher@example.com"
        self.confirmed_on = "2026-08-23 15:06:53"
        self.approval_status = "Pending"
        self.approval_requested_by = None
        self.approval_requested_on = None
        self.approved_by = None
        self.approved_on = None
        self.approval_note = None
        self.approval_candidate_identity = ""
        self.execution_status = "Blocked"
        self.action_logs = []
        self.last_action = None
        self.last_action_by = None
        self.last_action_on = None
        self.validate_calls = 0
        self.save_calls = 0

    def has_permission(self, _ptype):
        return True

    def validate(self):
        self.validate_calls += 1
        # Simulate the corrected DocType hydration of an existing pre-fix row:
        # supplier-payment Outflow must bind to the Payment Entry bank side.
        self.payment_account = "Bank - RC"
        self.resolved_payment_account = "Bank - RC"

    def append(self, fieldname, value):
        getattr(self, fieldname).append(frappe._dict(value))

    def save(self, **_kwargs):
        self.save_calls += 1
        # Frappe calls validate again during save. It must remain idempotent.
        self.validate()
        return self

    def as_dict(self):
        return frappe._dict(
            {
                key: value
                for key, value in self.__dict__.items()
                if key not in {"validate_calls", "save_calls"}
            }
        )


class ReconciliationApprovalRefreshTests(unittest.TestCase):
    def test_existing_stale_supplier_match_binds_approval_to_refreshed_bank_account(self):
        doc = _StaleSupplierMatch()
        readiness = {"readiness_group": "Ready", "block_reason": ""}

        with (
            patch("retailedge.reconciliation_approval.assert_can_access_bank_transaction_matching"),
            patch("retailedge.reconciliation_approval.frappe.get_doc", return_value=doc),
            patch(
                "retailedge.reconciliation_approval._settings_snapshot",
                return_value={"required": True, "allowed_roles": ["System Manager"]},
            ),
            patch("retailedge.reconciliation_approval.frappe.get_roles", return_value=["System Manager"]),
            patch(
                "retailedge.reconciliation_approval.frappe.session",
                frappe._dict(user="approver@example.com"),
            ),
            patch(
                "retailedge.reconciliation_bridge._load_match_for_preflight",
                return_value=frappe._dict({"name": doc.name}),
            ),
            patch(
                "retailedge.reconciliation_bridge.build_reconciliation_readiness_result",
                return_value=readiness,
            ),
        ):
            result = approve_reconciliation_for_match(doc.name, approval_note="QA approval")

        self.assertGreaterEqual(doc.validate_calls, 2)
        self.assertEqual(doc.save_calls, 1)
        self.assertEqual(doc.payment_account, "Bank - RC")
        self.assertEqual(doc.resolved_payment_account, "Bank - RC")
        self.assertIn('"payment_account":"Bank - RC"', doc.approval_candidate_identity)
        self.assertNotIn('"payment_account":"Creditors - RC"', doc.approval_candidate_identity)
        self.assertEqual(result["status"], APPROVAL_APPROVED)
        self.assertTrue(result["is_satisfied"])


if __name__ == "__main__":
    unittest.main()
