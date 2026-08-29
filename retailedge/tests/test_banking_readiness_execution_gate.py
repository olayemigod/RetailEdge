from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from retailedge import banking_operations


class BankingReadinessExecutionGateTests(IntegrationTestCase):
    def _match(self):
        return frappe._dict(
            {
                "name": "RE-BTM-TEST-READINESS",
                "bank_transaction": "ACC-BTN-TEST-READINESS",
                "bank_account": "Access Bank Ketu - Access Bank",
                "company": "Retail Company",
                "decision_status": "Confirmed",
                "suggested_document_type": "Payment Entry",
                "suggested_document": "ACC-PAY-TEST-READINESS",
                "execution_status": "Not Executed",
            }
        )

    @patch.object(banking_operations, "assert_can_manage_bank_transaction_match")
    @patch.object(banking_operations, "assert_can_access_bank_transaction_matching")
    @patch.object(banking_operations, "_load_match")
    @patch.object(banking_operations, "_banking_readiness_for_match")
    @patch.object(banking_operations, "get_bank_match_operational_status")
    @patch.object(banking_operations, "execute_reconciliation_for_match")
    def test_blocked_readiness_prevents_execution(
        self,
        execute,
        operational,
        readiness,
        load_match,
        _access,
        _manage,
    ):
        load_match.return_value = self._match()
        readiness.return_value = frappe._dict(
            {
                "readiness": "Blocked",
                "can_reconcile": False,
                "issues": [
                    {
                        "code": "gl_company_mismatch",
                        "message": "Mapped ledger belongs to another company.",
                        "severity": "Blocked",
                    }
                ],
                "warnings": [],
            }
        )
        operational.return_value = {
            "operational_status": banking_operations.STATUS_EXCEPTION,
            "recommended_action": "Correct Banking Setup.",
        }

        result = banking_operations.match_and_reconcile(
            "RE-BTM-TEST-READINESS",
            confirm_reconciliation=True,
        )

        self.assertEqual(result.get("status"), banking_operations.STATUS_EXCEPTION)
        self.assertIn("another company", result.get("message"))
        execute.assert_not_called()

    @patch.object(banking_operations, "assert_can_manage_bank_transaction_match")
    @patch.object(banking_operations, "assert_can_access_bank_transaction_matching")
    @patch.object(banking_operations, "_load_match")
    @patch.object(banking_operations, "_banking_readiness_for_match")
    @patch.object(banking_operations, "get_bank_match_operational_status")
    @patch.object(banking_operations, "execute_reconciliation_for_match")
    def test_warning_readiness_does_not_override_existing_ready_flow(
        self,
        execute,
        operational,
        readiness,
        load_match,
        _access,
        _manage,
    ):
        load_match.return_value = self._match()
        readiness.return_value = frappe._dict(
            {
                "readiness": "Warning",
                "can_reconcile": True,
                "issues": [],
                "warnings": [
                    {
                        "code": "branch_not_restricted",
                        "message": "Central company-wide bank account.",
                        "severity": "Warning",
                    }
                ],
            }
        )
        operational.return_value = {
            "operational_status": banking_operations.STATUS_READY_TO_RECONCILE,
            "recommended_action": "Ready.",
        }
        execute.return_value = {
            "execution_status": "Executed",
            "message": "Reconciled.",
        }

        result = banking_operations.match_and_reconcile(
            "RE-BTM-TEST-READINESS",
            confirm_reconciliation=True,
        )

        self.assertEqual(result.get("status"), "Executed")
        execute.assert_called_once_with("RE-BTM-TEST-READINESS", confirm=True)

    @patch.object(banking_operations, "assert_can_access_bank_transaction_matching")
    @patch.object(banking_operations, "_load_match")
    @patch.object(banking_operations, "get_bank_transaction_direction")
    @patch.object(banking_operations, "get_reconciliation_preflight")
    @patch.object(banking_operations, "build_reconciliation_approval_state")
    @patch.object(banking_operations, "_banking_readiness_for_match")
    @patch.object(banking_operations, "check_reconciliation_execution_gate")
    def test_blocked_readiness_forces_operational_exception(
        self,
        execution_gate,
        readiness,
        approval,
        preflight,
        direction,
        load_match,
        _access,
    ):
        load_match.return_value = self._match()
        direction.return_value = "Outflow"
        preflight.return_value = {
            "status": "Ready",
            "readiness_group": "Ready",
            "erpnext_target_status": "Reconciliation Target Available",
            "recommended_action": "Reconcile.",
        }
        approval.return_value = {"required": False, "is_satisfied": True}
        execution_gate.return_value = {"can_execute": True, "block_reasons": []}
        readiness.return_value = frappe._dict(
            {
                "readiness": "Blocked",
                "can_reconcile": False,
                "issues": [
                    {
                        "code": "missing_gl_account",
                        "message": "Bank Account is not mapped to an accounting ledger.",
                        "severity": "Blocked",
                    }
                ],
                "warnings": [],
            }
        )

        result = banking_operations.get_bank_match_operational_status(
            "RE-BTM-TEST-READINESS"
        )

        self.assertEqual(
            result.get("operational_status"), banking_operations.STATUS_EXCEPTION
        )
        self.assertFalse(result.get("can_execute"))
        self.assertEqual(result.get("banking_readiness", {}).get("readiness"), "Blocked")
        self.assertIn("accounting ledger", result.get("recommended_action"))
