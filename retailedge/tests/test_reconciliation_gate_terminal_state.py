from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.reconciliation_bridge import (
	EXECUTION_GATE_BLOCKED,
	EXECUTION_STATUS_ALREADY_HANDLED,
	EXECUTION_STATUS_EXECUTED,
	check_reconciliation_execution_gate,
)


class ReconciliationGateTerminalStateTests(unittest.TestCase):
	def _ready_match(self, **overrides):
		row = {
			"name": "RE-BTM-TEST-TERMINAL",
			"bank_transaction": "ACC-BTN-TEST-TERMINAL",
			"bank_account": "Access Bank Test",
			"bank_amount": 750000,
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-TEST-TERMINAL",
			"candidate_doctype": "Payment Entry",
			"candidate_name": "ACC-PAY-TEST-TERMINAL",
			"candidate_docstatus": 1,
			"candidate_amount": 750000,
			"candidate_account": "Bank - RC",
			"payment_event_source": "Payment Entry",
			"payment_event_amount": 750000,
			"payment_account": "Bank - RC",
			"resolved_bank_account": "Bank - RC",
			"resolved_payment_account": "Bank - RC",
			"account_resolution_status": "match_via_mapping",
			"decision_status": "Confirmed",
			"review_status": "Confirmed",
			"reconciliation_readiness_status": "Ready for Reconciliation",
			"handoff_status": "Ready for ERPNext Reconciliation",
			"amount_difference": 0,
			"match_confidence": "Strong Match",
			"match_score": 100,
			"blocking_reason": "",
			"execution_status": "Not Executed",
			"erpnext_reconciliation_status": "Unreconciled",
		}
		row.update(overrides)
		return frappe._dict(row)

	def _settings(self):
		return {
			"enable_bank_reconciliation_execution": 1,
			"require_reconciliation_dry_run_before_execution": 1,
			"minimum_reconciliation_readiness_status": "Ready",
			"allowed_reconciliation_execution_roles": "System Manager",
			"require_second_approval_for_reconciliation_execution": 0,
		}

	def _run_gate(self, match):
		with (
			patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"),
			patch("retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match),
			patch("retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]),
			patch("retailedge.reconciliation_bridge.build_reconciliation_readiness_result") as readiness,
		):
			payload = check_reconciliation_execution_gate(
				match["name"],
				user="operator@example.com",
				settings=self._settings(),
			)
		return payload, readiness

	def test_terminal_retailedge_execution_status_blocks_gate_before_dry_run(self):
		for status in (EXECUTION_STATUS_EXECUTED, EXECUTION_STATUS_ALREADY_HANDLED):
			with self.subTest(status=status):
				payload, readiness = self._run_gate(
					self._ready_match(execution_status=status)
				)
				self.assertEqual(payload["status"], EXECUTION_GATE_BLOCKED)
				self.assertFalse(payload["can_execute"])
				self.assertFalse(payload["execution_available_in_r59"])
				self.assertIn("already been handled", payload["message"].lower())
				readiness.assert_not_called()

	def test_live_erpnext_reconciled_status_blocks_gate_before_dry_run(self):
		payload, readiness = self._run_gate(
			self._ready_match(erpnext_reconciliation_status="Reconciled")
		)
		self.assertEqual(payload["status"], EXECUTION_GATE_BLOCKED)
		self.assertFalse(payload["can_execute"])
		self.assertFalse(payload["execution_available_in_r59"])
		self.assertIn("already reconciled in erpnext", payload["message"].lower())
		readiness.assert_not_called()
