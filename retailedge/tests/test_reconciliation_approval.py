from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.banking_operations import (
    STATUS_AWAITING_APPROVAL,
    STATUS_READY_TO_RECONCILE,
    derive_operational_status,
)
from retailedge.banking_workspace import QUEUE_TO_RECONCILE, _status_belongs_to_queue
from retailedge.reconciliation_approval import (
    APPROVAL_APPROVED,
    APPROVAL_INVALIDATED,
    APPROVAL_NOT_REQUIRED,
    APPROVAL_PENDING,
    _candidate_identity,
    build_reconciliation_approval_state,
)
from retailedge.reconciliation_bridge import (
    EXECUTION_GATE_ALLOWED,
    EXECUTION_GATE_NEEDS_APPROVAL,
    READINESS_GROUP_READY,
    check_reconciliation_execution_gate,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class ReconciliationApprovalTests(unittest.TestCase):
    def _match(self, **overrides):
        row = frappe._dict(
            {
                "name": "RE-BTM-2026-0099",
                "bank_transaction": "ACC-BTN-2026-00099",
                "suggested_document_type": "Payment Entry",
                "suggested_document": "ACC-PAY-2026-00099",
                "candidate_doctype": "Payment Entry",
                "candidate_name": "ACC-PAY-2026-00099",
                "candidate_docstatus": 1,
                "bank_amount": 155000,
                "candidate_amount": 155000,
                "amount_difference": 0,
                "payment_event_source": "Payment Entry",
                "payment_account": "Access Bank - RC",
                "resolved_payment_account": "Access Bank - RC",
                "resolved_bank_account": "Access Bank - RC",
                "account_resolution_status": "match_via_mapping",
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
                "reconciliation_readiness_status": "Ready for Reconciliation",
                "handoff_status": "Ready for ERPNext Reconciliation",
                "match_confidence": "Strong Match",
                "match_score": 100,
                "execution_status": "Not Executed",
            }
        )
        row.update(overrides)
        return row

    def _settings(self, required=1):
        return {
            "enable_bank_reconciliation_execution": 1,
            "require_reconciliation_dry_run_before_execution": 1,
            "minimum_reconciliation_readiness_status": "Ready",
            "allowed_reconciliation_execution_roles": "System Manager\nAccounts Manager",
            "require_second_approval_for_reconciliation_execution": required,
        }

    def test_approval_not_required_when_setting_disabled(self):
        state = build_reconciliation_approval_state(
            self._match(), user="matcher@example.com", settings=self._settings(required=0)
        )
        self.assertEqual(state["status"], APPROVAL_NOT_REQUIRED)
        self.assertTrue(state["is_satisfied"])

    def test_confirmed_match_is_pending_without_second_approval(self):
        state = build_reconciliation_approval_state(
            self._match(), user="approver@example.com", settings=self._settings()
        )
        self.assertEqual(state["status"], APPROVAL_PENDING)
        self.assertFalse(state["is_satisfied"])

    def test_valid_different_user_approval_is_satisfied(self):
        row = self._match()
        row.approval_status = APPROVAL_APPROVED
        row.approved_by = "approver@example.com"
        row.approved_on = "2026-08-19 18:05:00"
        row.approval_candidate_identity = _candidate_identity(row)

        state = build_reconciliation_approval_state(
            row, user="matcher@example.com", settings=self._settings()
        )
        self.assertEqual(state["status"], APPROVAL_APPROVED)
        self.assertTrue(state["is_satisfied"])

    def test_same_user_approval_is_invalidated(self):
        row = self._match()
        row.approval_status = APPROVAL_APPROVED
        row.approved_by = row.confirmed_by
        row.approved_on = "2026-08-19 18:05:00"
        row.approval_candidate_identity = _candidate_identity(row)

        state = build_reconciliation_approval_state(
            row, user="other@example.com", settings=self._settings()
        )
        self.assertEqual(state["status"], APPROVAL_INVALIDATED)
        self.assertFalse(state["is_satisfied"])

    def test_approval_before_latest_confirmation_is_invalidated(self):
        row = self._match()
        row.approval_status = APPROVAL_APPROVED
        row.approved_by = "approver@example.com"
        row.approved_on = "2026-08-19 17:59:59"
        row.approval_candidate_identity = _candidate_identity(row)

        state = build_reconciliation_approval_state(
            row, user="executor@example.com", settings=self._settings()
        )
        self.assertEqual(state["status"], APPROVAL_INVALIDATED)
        self.assertFalse(state["is_satisfied"])

    def test_candidate_change_invalidates_old_approval(self):
        row = self._match()
        row.approval_status = APPROVAL_APPROVED
        row.approved_by = "approver@example.com"
        row.approved_on = "2026-08-19 18:05:00"
        row.approval_candidate_identity = _candidate_identity(row)
        row.suggested_document = "ACC-PAY-2026-00100"
        row.candidate_name = "ACC-PAY-2026-00100"

        state = build_reconciliation_approval_state(
            row, user="executor@example.com", settings=self._settings()
        )
        self.assertEqual(state["status"], APPROVAL_INVALIDATED)
        self.assertFalse(state["is_satisfied"])

    def test_confirmer_cannot_be_presented_as_approver(self):
        with patch("retailedge.reconciliation_approval.frappe.get_roles", return_value=["System Manager"]):
            state = build_reconciliation_approval_state(
                self._match(), user="matcher@example.com", settings=self._settings()
            )
        self.assertFalse(state["can_approve"])
        self.assertTrue(state["same_user_blocked"])

    def test_different_allowed_user_can_approve(self):
        with patch("retailedge.reconciliation_approval.frappe.get_roles", return_value=["Accounts Manager"]):
            state = build_reconciliation_approval_state(
                self._match(), user="approver@example.com", settings=self._settings()
            )
        self.assertTrue(state["can_approve"])

    def test_ready_match_is_awaiting_approval_until_satisfied(self):
        preflight = {"readiness_group": READINESS_GROUP_READY, "status": "Ready"}
        pending = {"required": True, "is_satisfied": False}
        approved = {"required": True, "is_satisfied": True}

        self.assertEqual(
            derive_operational_status(self._match(), preflight=preflight, approval=pending),
            STATUS_AWAITING_APPROVAL,
        )
        self.assertEqual(
            derive_operational_status(self._match(), preflight=preflight, approval=approved),
            STATUS_READY_TO_RECONCILE,
        )

    def test_awaiting_approval_belongs_to_to_reconcile_queue(self):
        self.assertTrue(_status_belongs_to_queue(STATUS_AWAITING_APPROVAL, QUEUE_TO_RECONCILE))

    def test_execution_gate_accepts_valid_persisted_approval(self):
        row = self._match()
        row.approval_status = APPROVAL_APPROVED
        row.approved_by = "approver@example.com"
        row.approved_on = "2026-08-19 18:05:00"
        row.approval_candidate_identity = _candidate_identity(row)
        dry_run = {
            "readiness_group": READINESS_GROUP_READY,
            "eligibility_status": READINESS_GROUP_READY,
            "block_reason": "",
        }
        with (
            patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"),
            patch("retailedge.reconciliation_bridge._load_match_for_preflight", return_value=row),
            patch("retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]),
        ):
            result = check_reconciliation_execution_gate(
                row.name,
                user="executor@example.com",
                settings=self._settings(),
                dry_run_result=dry_run,
            )
        self.assertEqual(result["status"], EXECUTION_GATE_ALLOWED)
        self.assertTrue(result["can_execute"])

    def test_execution_gate_still_needs_approval_when_pending(self):
        row = self._match()
        dry_run = {
            "readiness_group": READINESS_GROUP_READY,
            "eligibility_status": READINESS_GROUP_READY,
            "block_reason": "",
        }
        with (
            patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"),
            patch("retailedge.reconciliation_bridge._load_match_for_preflight", return_value=row),
            patch("retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]),
        ):
            result = check_reconciliation_execution_gate(
                row.name,
                user="executor@example.com",
                settings=self._settings(),
                dry_run_result=dry_run,
            )
        self.assertEqual(result["status"], EXECUTION_GATE_NEEDS_APPROVAL)
        self.assertFalse(result["can_execute"])

    def test_match_doctype_persists_approval_audit_fields(self):
        path = APP_ROOT / "retailedge/doctype/retailedge_bank_transaction_match/retailedge_bank_transaction_match.json"
        payload = json.loads(path.read_text())
        fields = {field["fieldname"] for field in payload["fields"]}
        required = {
            "approval_status",
            "approval_requested_by",
            "approval_requested_on",
            "approved_by",
            "approved_on",
            "approval_note",
            "approval_candidate_identity",
        }
        self.assertTrue(required.issubset(fields))


if __name__ == "__main__":
    unittest.main()
