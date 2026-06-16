from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge import api as retailedge_api
from retailedge.reconciliation_bridge import (
	ERPNext_NATIVE_RECONCILIATION_METHOD,
	PREFLIGHT_ALREADY_RECONCILED,
	PREFLIGHT_EXCEPTION,
	PREFLIGHT_NEEDS_REVIEW,
	PREFLIGHT_NOT_READY,
	PREFLIGHT_READY,
	PREFLIGHT_TARGET_AMBIGUOUS,
	EXECUTION_GATE_ALLOWED,
	EXECUTION_GATE_BLOCKED,
	EXECUTION_GATE_NEEDS_APPROVAL,
	EXECUTION_GATE_PERMISSION_DENIED,
	EXECUTION_GATE_SETTINGS_DISABLED,
	EXECUTION_STATUS_ALREADY_HANDLED,
	EXECUTION_STATUS_BLOCKED,
	EXECUTION_STATUS_EXECUTED,
	EXECUTION_STATUS_FAILED,
	READINESS_GROUP_ALREADY_HANDLED,
	READINESS_GROUP_BLOCKED,
	READINESS_GROUP_NEEDS_REVIEW,
	READINESS_GROUP_READY,
	BLOCK_ALREADY_HANDLED,
	BLOCK_AMOUNT_MISMATCH,
	BLOCK_BANK_ACCOUNT_MISMATCH,
	BLOCK_MISSING_SOURCE_DOCUMENT,
	BLOCK_UNSUPPORTED_CANDIDATE_TYPE,
	TARGET_AMBIGUOUS,
	TARGET_AVAILABLE,
	TARGET_MISSING,
	TARGET_MANUAL_REVIEW,
	build_reconciliation_preflight,
	build_reconciliation_readiness_result,
	check_reconciliation_execution_gate,
	check_reconciliation_execution_gate_for_matches,
	dry_run_reconciliation_for_matches,
	dry_run_reconciliation_for_match,
	execute_reconciliation_for_match,
	get_reconciliation_execution_settings_snapshot,
	get_reconciliation_preflight,
	reconcile_confirmed_bank_match,
	resolve_reconciliation_target,
)


class ReconciliationBridgeTests(unittest.TestCase):
	def _ready_payment_entry_match(self, **overrides):
		row = {
			"name": "RE-BTM-2026-0006",
			"bank_match_review": "RE-BTM-2026-0006",
			"bank_transaction": "ACC-BTN-2026-00007",
			"bank_transaction_date": "2026-05-26",
			"bank_account": "Moniepoint - moniepoint",
			"bank_amount": 1090,
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-2026-00012",
			"candidate_doctype": "Payment Entry",
			"candidate_name": "ACC-PAY-2026-00012",
			"candidate_docstatus": 1,
			"candidate_category": "Payment Entry Match",
			"candidate_amount": 1090,
			"candidate_account": "Demo Bank Account - PED",
			"candidate_date": "2026-05-26",
			"payment_event_source": "Payment Entry",
			"payment_event_amount": 1090,
			"payment_account": "Demo Bank Account - PED",
			"resolved_bank_account": "Demo Bank Account - PED",
			"resolved_payment_account": "Demo Bank Account - PED",
			"account_resolution_status": "match_via_mapping",
			"review_status": "Confirmed",
			"decision_status": "Confirmed",
			"reconciliation_readiness_status": "Ready for Reconciliation",
			"handoff_status": "Ready for ERPNext Reconciliation",
			"amount_difference": 0,
			"match_confidence": "Strong Match",
			"match_score": 100,
			"blocking_reason": "",
			"branch": "HQ",
		}
		row.update(overrides)
		return row

	def _execution_enabled_settings(self, **overrides):
		settings = {
			"enable_bank_reconciliation_execution": 1,
			"require_reconciliation_dry_run_before_execution": 1,
			"minimum_reconciliation_readiness_status": "Ready",
			"allowed_reconciliation_execution_roles": "System Manager\nAccounts Manager\nRetailEdge Manager\nRetailEdgeManager",
			"require_second_approval_for_reconciliation_execution": 0,
		}
		settings.update(overrides)
		return settings

	def _run_gate(self, match=None, settings=None, roles=None, user="test@example.com"):
		match = match or self._ready_payment_entry_match()
		settings = settings if settings is not None else self._execution_enabled_settings()
		roles = roles or ["System Manager"]
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.frappe.get_roles", return_value=roles):
			return check_reconciliation_execution_gate("RE-BTM-2026-0006", user=user, settings=settings)

	def test_execution_settings_snapshot_defaults_are_safe(self):
		snapshot = get_reconciliation_execution_settings_snapshot(settings={})

		self.assertFalse(snapshot["enable_bank_reconciliation_execution"])
		self.assertTrue(snapshot["require_reconciliation_dry_run_before_execution"])
		self.assertEqual(snapshot["minimum_reconciliation_readiness_status"], READINESS_GROUP_READY)
		self.assertIn("System Manager", snapshot["allowed_reconciliation_execution_roles"])
		self.assertTrue(snapshot["require_second_approval_for_reconciliation_execution"])

	def test_execution_settings_snapshot_empty_values_are_safe(self):
		snapshot = get_reconciliation_execution_settings_snapshot(
			settings={
				"enable_bank_reconciliation_execution": "",
				"require_reconciliation_dry_run_before_execution": "",
				"minimum_reconciliation_readiness_status": "",
				"allowed_reconciliation_execution_roles": "",
				"require_second_approval_for_reconciliation_execution": "",
			}
		)

		self.assertFalse(snapshot["enable_bank_reconciliation_execution"])
		self.assertTrue(snapshot["require_reconciliation_dry_run_before_execution"])
		self.assertEqual(snapshot["minimum_reconciliation_readiness_status"], READINESS_GROUP_READY)
		self.assertIn("System Manager", snapshot["allowed_reconciliation_execution_roles"])
		self.assertTrue(snapshot["require_second_approval_for_reconciliation_execution"])

	def test_execution_settings_snapshot_respects_explicit_boolean_values(self):
		snapshot = get_reconciliation_execution_settings_snapshot(
			settings={
				"enable_bank_reconciliation_execution": 1,
				"require_reconciliation_dry_run_before_execution": 0,
				"require_second_approval_for_reconciliation_execution": 0,
			}
		)

		self.assertTrue(snapshot["enable_bank_reconciliation_execution"])
		self.assertFalse(snapshot["require_reconciliation_dry_run_before_execution"])
		self.assertFalse(snapshot["require_second_approval_for_reconciliation_execution"])

	def test_reconciliation_execution_settings_fields_exist_with_safe_defaults(self):
		path = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_settings/retailedge_settings.json"
		settings = json.loads(Path(path).read_text())
		fields = {field["fieldname"]: field for field in settings["fields"]}

		self.assertEqual(fields["enable_bank_reconciliation_execution"].get("default"), "0")
		self.assertEqual(fields["require_reconciliation_dry_run_before_execution"].get("default"), "1")
		self.assertEqual(fields["minimum_reconciliation_readiness_status"].get("default"), "Ready")
		self.assertIn("System Manager", fields["allowed_reconciliation_execution_roles"].get("default"))
		self.assertEqual(fields["require_second_approval_for_reconciliation_execution"].get("default"), "1")

	def test_execution_gate_blocked_when_setting_disabled(self):
		payload = self._run_gate(settings={})

		self.assertFalse(payload["can_execute"])
		self.assertEqual(payload["status"], EXECUTION_GATE_SETTINGS_DISABLED)
		self.assertFalse(payload["execution_attempted"])

	def test_execution_gate_blocked_when_match_not_confirmed(self):
		payload = self._run_gate(match=self._ready_payment_entry_match(decision_status="Needs Review", review_status="Needs Review"))

		self.assertFalse(payload["can_execute"])
		self.assertEqual(payload["status"], EXECUTION_GATE_BLOCKED)
		self.assertIn("confirmed", " ".join(payload["block_reasons"]).lower())

	def test_execution_gate_blocked_when_dry_run_not_ready(self):
		payload = self._run_gate(match=self._ready_payment_entry_match(candidate_amount=1089, amount_difference=1))

		self.assertFalse(payload["can_execute"])
		self.assertEqual(payload["status"], EXECUTION_GATE_BLOCKED)
		self.assertEqual(payload["dry_run_status"], READINESS_GROUP_BLOCKED)

	def test_execution_gate_blocks_blocked_needs_review_and_already_handled_readiness(self):
		blocked = self._run_gate(match=self._ready_payment_entry_match(candidate_amount=1089, amount_difference=1))
		needs_review = self._run_gate(match=self._ready_payment_entry_match(decision_status="Needs Review", review_status="Needs Review"))
		already = self._run_gate(
			match=self._ready_payment_entry_match(
				reconciliation_readiness_status="Already Reconciled",
				handoff_status="Already Reconciled",
			)
		)

		self.assertEqual(blocked["dry_run_status"], READINESS_GROUP_BLOCKED)
		self.assertEqual(needs_review["dry_run_status"], READINESS_GROUP_NEEDS_REVIEW)
		self.assertEqual(already["dry_run_status"], READINESS_GROUP_ALREADY_HANDLED)
		self.assertFalse(blocked["can_execute"])
		self.assertFalse(needs_review["can_execute"])
		self.assertFalse(already["can_execute"])

	def test_execution_gate_blocked_when_user_lacks_allowed_role(self):
		payload = self._run_gate(roles=["RetailEdgeAuditor"])

		self.assertFalse(payload["can_execute"])
		self.assertEqual(payload["status"], EXECUTION_GATE_PERMISSION_DENIED)

	def test_execution_gate_needs_approval_when_second_approval_required(self):
		payload = self._run_gate(settings=self._execution_enabled_settings(require_second_approval_for_reconciliation_execution=1))

		self.assertFalse(payload["can_execute"])
		self.assertEqual(payload["status"], EXECUTION_GATE_NEEDS_APPROVAL)

	def test_execution_gate_allowed_only_when_all_gates_pass(self):
		payload = self._run_gate()

		self.assertTrue(payload["can_execute"])
		self.assertEqual(payload["status"], EXECUTION_GATE_ALLOWED)
		self.assertFalse(payload["execution_attempted"])
		self.assertFalse(payload["execution_available_in_r58"])
		self.assertTrue(payload["execution_available_in_r59"])
		self.assertTrue(payload["final_confirmation_required"])

	def test_execution_gate_does_not_mutate_bank_transaction(self):
		with patch("retailedge.reconciliation_bridge.frappe.db.set_value") as mock_set_value:
			payload = self._run_gate()

		self.assertEqual(payload["status"], EXECUTION_GATE_ALLOWED)
		mock_set_value.assert_not_called()

	def test_execution_gate_does_not_mutate_payment_entry_or_sales_invoice(self):
		with patch("retailedge.reconciliation_bridge.frappe.get_doc") as mock_get_doc:
			self._run_gate()

		mock_get_doc.assert_not_called()

	def test_execution_gate_does_not_create_journal_entry_or_gl_entry(self):
		with patch("retailedge.reconciliation_bridge.frappe.new_doc") as mock_new_doc:
			self._run_gate()

		mock_new_doc.assert_not_called()

	def test_execution_gate_for_matches_summarizes_without_execution(self):
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge.check_reconciliation_execution_gate",
			side_effect=[
				{"status": EXECUTION_GATE_ALLOWED, "can_execute": True},
				{"status": EXECUTION_GATE_BLOCKED, "can_execute": False},
			],
		):
			summary = check_reconciliation_execution_gate_for_matches(["A", "B"])

		self.assertEqual(summary["total_count"], 2)
		self.assertEqual(summary["allowed_count"], 1)
		self.assertEqual(summary["blocked_count"], 1)
		self.assertFalse(summary["execution_attempted"])

	def _bank_transaction_doc(self, status="Unreconciled", unallocated_amount=1090, links=None):
		links = links or []
		return SimpleNamespace(
			name="ACC-BTN-2026-00007",
			status=status,
			unallocated_amount=unallocated_amount,
			payment_entries=[SimpleNamespace(**row) for row in links],
		)

	def _execution_context(self, match=None, settings=None, roles=None, bank_docs=None):
		match = match or self._ready_payment_entry_match()
		settings = settings if settings is not None else self._execution_enabled_settings()
		roles = roles or ["System Manager"]
		bank_docs = bank_docs or [
			self._bank_transaction_doc(),
			self._bank_transaction_doc(
				status="Reconciled",
				unallocated_amount=0,
				links=[{"payment_document": "Payment Entry", "payment_entry": match["suggested_document"], "allocated_amount": match["candidate_amount"]}],
			),
		]
		return patch.multiple(
			"retailedge.reconciliation_bridge",
			assert_can_access_bank_transaction_matching=unittest.mock.DEFAULT,
			_load_match_for_preflight=unittest.mock.DEFAULT,
			get_retailedge_settings=unittest.mock.DEFAULT,
		), match, settings, roles, bank_docs

	def test_execute_reconciliation_blocks_when_confirm_missing(self):
		match = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge._update_execution_audit") as mock_audit, patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=False)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertIn("confirmation", payload["message"].lower())
		mock_get_attr.assert_not_called()
		mock_audit.assert_called_once()

	def test_execute_reconciliation_blocks_when_setting_disabled(self):
		match = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value={}), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge._update_execution_audit"), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertEqual(payload["gate_status_at_execution"], EXECUTION_GATE_SETTINGS_DISABLED)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_blocks_when_match_not_confirmed(self):
		match = self._ready_payment_entry_match(decision_status="Needs Review", review_status="Needs Review")
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge._update_execution_audit"), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertEqual(payload["gate_status_at_execution"], EXECUTION_GATE_BLOCKED)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_blocks_when_dry_run_not_ready(self):
		match = self._ready_payment_entry_match(candidate_amount=1089, amount_difference=1)
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge._update_execution_audit"), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertEqual(payload["dry_run_status_at_execution"], READINESS_GROUP_BLOCKED)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_blocks_when_gate_not_allowed(self):
		match = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.check_reconciliation_execution_gate", return_value={"can_execute": False, "status": EXECUTION_GATE_BLOCKED, "message": "Blocked by test gate."}), patch(
			"retailedge.reconciliation_bridge._update_execution_audit"
		), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertEqual(payload["gate_status_at_execution"], EXECUTION_GATE_BLOCKED)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_blocks_when_user_lacks_role(self):
		match = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["RetailEdgeAuditor"]
		), patch("retailedge.reconciliation_bridge._update_execution_audit"), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertEqual(payload["gate_status_at_execution"], EXECUTION_GATE_PERMISSION_DENIED)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_blocks_when_second_approval_required(self):
		match = self._ready_payment_entry_match()
		settings = self._execution_enabled_settings(require_second_approval_for_reconciliation_execution=1)
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=settings), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge._update_execution_audit"), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertEqual(payload["gate_status_at_execution"], EXECUTION_GATE_NEEDS_APPROVAL)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_uses_stored_reviewed_candidate_only(self):
		match = self._ready_payment_entry_match(suggested_document="ACC-PAY-LOCKED", candidate_name="ACC-PAY-LOCKED")
		before_doc = self._bank_transaction_doc()
		after_doc = self._bank_transaction_doc(status="Reconciled", unallocated_amount=0, links=[{"payment_document": "Payment Entry", "payment_entry": "ACC-PAY-LOCKED", "allocated_amount": 1090}])
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", side_effect=[before_doc, after_doc]), patch(
			"retailedge.reconciliation_bridge._update_execution_audit"
		), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			mock_native = unittest.mock.Mock()
			mock_get_attr.return_value = mock_native
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_EXECUTED)
		mock_native.assert_called_once()
		self.assertEqual(json.loads(mock_native.call_args.args[1]), [{"payment_doctype": "Payment Entry", "payment_name": "ACC-PAY-LOCKED"}])
		self.assertNotIn("CURRENT", mock_native.call_args.args[1])

	def test_execute_reconciliation_does_not_substitute_candidate_when_target_differs(self):
		match = self._ready_payment_entry_match(suggested_document="ACC-PAY-LOCKED", candidate_name="ACC-PAY-LOCKED")
		dry_run = build_reconciliation_readiness_result(match)
		dry_run["erpnext_target_name"] = "ACC-PAY-CURRENT"
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.build_reconciliation_readiness_result", return_value=dry_run), patch(
			"retailedge.reconciliation_bridge.check_reconciliation_execution_gate", return_value={"can_execute": True, "status": EXECUTION_GATE_ALLOWED}
		), patch("retailedge.reconciliation_bridge._update_execution_audit"), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertIn("does not match", payload["message"])
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_already_handled_is_idempotent(self):
		match = self._ready_payment_entry_match()
		linked_doc = self._bank_transaction_doc(status="Reconciled", unallocated_amount=0, links=[{"payment_document": "Payment Entry", "payment_entry": "ACC-PAY-2026-00012", "allocated_amount": 1090}])
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=linked_doc), patch(
			"retailedge.reconciliation_bridge._update_execution_audit"
		), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_ALREADY_HANDLED)
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_conflict_blocks_safely(self):
		match = self._ready_payment_entry_match()
		conflict_doc = self._bank_transaction_doc(links=[{"payment_document": "Payment Entry", "payment_entry": "ACC-PAY-OTHER", "allocated_amount": 1090}])
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=conflict_doc), patch(
			"retailedge.reconciliation_bridge._update_execution_audit"
		), patch("retailedge.reconciliation_bridge.frappe.get_attr") as mock_get_attr:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_BLOCKED)
		self.assertIn("different", payload["message"])
		mock_get_attr.assert_not_called()

	def test_execute_reconciliation_failure_is_sanitized(self):
		match = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._bank_transaction_doc()), patch(
			"retailedge.reconciliation_bridge._update_execution_audit"
		), patch("retailedge.reconciliation_bridge.frappe.get_attr", side_effect=Exception("native route unavailable: secret stack detail")):
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_FAILED)
		self.assertIn("failed", payload["message"].lower())
		self.assertIn("native route unavailable", payload["execution_error_summary"])

	def test_execute_reconciliation_does_not_create_journal_or_payment_entry_or_mutate_sales_invoice_manually(self):
		match = self._ready_payment_entry_match(suggested_document="ACC-PAY-LOCKED", candidate_name="ACC-PAY-LOCKED")
		before_doc = self._bank_transaction_doc()
		after_doc = self._bank_transaction_doc(status="Reconciled", unallocated_amount=0, links=[{"payment_document": "Payment Entry", "payment_entry": "ACC-PAY-LOCKED", "allocated_amount": 1090}])
		with patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching"), patch(
			"retailedge.reconciliation_bridge._load_match_for_preflight", return_value=match
		), patch("retailedge.reconciliation_bridge.get_retailedge_settings", return_value=self._execution_enabled_settings()), patch(
			"retailedge.reconciliation_bridge.frappe.get_roles", return_value=["System Manager"]
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", side_effect=[before_doc, after_doc]), patch(
			"retailedge.reconciliation_bridge._update_execution_audit"
		), patch("retailedge.reconciliation_bridge.frappe.get_attr", return_value=unittest.mock.Mock()), patch(
			"retailedge.reconciliation_bridge.frappe.new_doc"
		) as mock_new_doc, patch("retailedge.reconciliation_bridge.frappe.db.set_value") as mock_set_value:
			payload = execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)

		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_EXECUTED)
		mock_new_doc.assert_not_called()
		mock_set_value.assert_not_called()

	def test_api_wrapper_exposes_execute_reconciliation_for_match(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._execute_reconciliation_for_match", return_value={"execution_status": EXECUTION_STATUS_EXECUTED}
		) as mock_execute:
			payload = retailedge_api.execute_reconciliation_for_match("RE-BTM-2026-0006", confirm=True)
		self.assertEqual(payload["execution_status"], EXECUTION_STATUS_EXECUTED)
		mock_execute.assert_called_once_with(match_name="RE-BTM-2026-0006", confirm=True)

	def test_execution_audit_fields_exist_on_match_doctype(self):
		path = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_transaction_match/retailedge_bank_transaction_match.json"
		match_json = json.loads(Path(path).read_text())
		fields = {field["fieldname"]: field for field in match_json["fields"]}
		self.assertEqual(fields["execution_status"].get("default"), "Not Executed")
		self.assertIn("Executed", fields["execution_status"].get("options"))
		for fieldname in (
			"executed_by",
			"executed_on",
			"execution_reference",
			"execution_message",
			"execution_error_summary",
			"dry_run_status_at_execution",
			"gate_status_at_execution",
			"execution_bank_transaction",
			"execution_candidate_doctype",
			"execution_candidate_name",
			"execution_payment_event_identity",
		):
			self.assertIn(fieldname, fields)


	def test_payment_entry_target_resolves_cleanly(self):
		target = resolve_reconciliation_target(self._ready_payment_entry_match())
		self.assertEqual(target["target_status"], TARGET_AVAILABLE)
		self.assertEqual(target["erpnext_target_doctype"], "Payment Entry")
		self.assertEqual(target["erpnext_target_name"], "ACC-PAY-2026-00012")
		self.assertIn("Payment Entry ACC-PAY-2026-00012", target["recommended_action"])

	@patch("retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice", return_value=[])
	def test_invoice_payment_row_without_voucher_is_reported_as_missing_target(self, _mock_refs):
		target = resolve_reconciliation_target(
			{
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "ACC-SINV-2026-00023",
				"candidate_docstatus": 1,
				"payment_event_source": "Invoice Payment Row",
				"bank_transaction": "ACC-BTN-2026-00003",
			}
		)
		self.assertEqual(target["target_status"], TARGET_MISSING)
		self.assertIn("missing", target["blocking_reason"].lower())

	@patch(
		"retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice",
		return_value=[
			{
				"payment_entry": "ACC-PAY-2026-00021",
				"reference_allocated_amount": 810,
				"docstatus": 1,
			}
		],
	)
	def test_invoice_payment_row_with_linked_voucher_stays_ambiguous(self, _mock_refs):
		target = resolve_reconciliation_target(
			{
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "ACC-SINV-2026-00023",
				"candidate_docstatus": 1,
				"payment_event_source": "POS Payment Row",
				"bank_transaction": "ACC-BTN-2026-00003",
			}
		)
		self.assertEqual(target["target_status"], TARGET_AMBIGUOUS)
		self.assertIn("parent-invoice", target["blocking_reason"])

	def test_ready_confirmed_payment_entry_match_passes_preflight(self):
		payload = build_reconciliation_preflight(self._ready_payment_entry_match())
		self.assertEqual(payload["status"], PREFLIGHT_READY)
		self.assertTrue(payload["dry_run"])
		self.assertEqual(payload["erpnext_target_status"], TARGET_AVAILABLE)
		self.assertEqual(payload["erpnext_target_doctype"], "Payment Entry")
		self.assertTrue(payload["native_execution_supported"])

	def test_readiness_result_ready_shape_for_confirmed_payment_entry(self):
		payload = build_reconciliation_readiness_result(self._ready_payment_entry_match())

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_READY)
		self.assertEqual(payload["block_code"], "ready")
		self.assertEqual(payload["review_name"], "RE-BTM-2026-0006")
		self.assertEqual(payload["candidate_doctype"], "Payment Entry")
		self.assertEqual(payload["candidate_name"], "ACC-PAY-2026-00012")
		self.assertEqual(payload["payment_event_identity"], "Payment Entry:ACC-PAY-2026-00012")
		self.assertTrue(payload["dry_run"])
		self.assertTrue(payload["native_execution_supported"])
		self.assertFalse(payload["execution_attempted"])

	def test_readiness_bank_account_mismatch_returns_blocked(self):
		payload = build_reconciliation_readiness_result(
			self._ready_payment_entry_match(
				account_resolution_status="mismatch",
				blocking_reason="Bank and payment accounts do not align for safe reconciliation.",
			)
		)

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_BLOCKED)
		self.assertEqual(payload["block_code"], BLOCK_BANK_ACCOUNT_MISMATCH)
		self.assertIn("account", payload["block_reason"].lower())

	def test_readiness_amount_mismatch_returns_blocked(self):
		payload = build_reconciliation_readiness_result(
			self._ready_payment_entry_match(candidate_amount=1089, amount_difference=1)
		)

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_BLOCKED)
		self.assertEqual(payload["block_code"], BLOCK_AMOUNT_MISMATCH)
		self.assertIn("amount", " ".join(payload["warnings"]).lower())

	def test_readiness_missing_candidate_returns_blocked(self):
		payload = build_reconciliation_readiness_result(
			self._ready_payment_entry_match(suggested_document="", candidate_name="", candidate_exists=False)
		)

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_BLOCKED)
		self.assertEqual(payload["block_code"], BLOCK_MISSING_SOURCE_DOCUMENT)

	def test_readiness_unsupported_candidate_type_returns_blocked(self):
		payload = build_reconciliation_readiness_result(
			self._ready_payment_entry_match(
				suggested_document_type="Journal Entry",
				suggested_document="ACC-JV-2026-00001",
				candidate_doctype="Journal Entry",
				candidate_name="ACC-JV-2026-00001",
			)
		)

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_BLOCKED)
		self.assertEqual(payload["block_code"], BLOCK_UNSUPPORTED_CANDIDATE_TYPE)

	def test_readiness_already_reconciled_is_already_handled(self):
		payload = build_reconciliation_readiness_result(
			self._ready_payment_entry_match(
				reconciliation_readiness_status="Already Reconciled",
				handoff_status="Already Reconciled",
			)
		)

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_ALREADY_HANDLED)
		self.assertEqual(payload["block_code"], BLOCK_ALREADY_HANDLED)

	@patch("retailedge.reconciliation_bridge._load_match_for_preflight")
	@patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching")
	def test_dry_run_one_confirmed_review_does_not_mutate_bank_transaction(self, _mock_access, mock_load):
		mock_load.return_value = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.frappe.db.set_value") as mock_set_value:
			payload = dry_run_reconciliation_for_match("RE-BTM-2026-0006")

		self.assertEqual(payload["eligibility_status"], READINESS_GROUP_READY)
		mock_set_value.assert_not_called()

	@patch("retailedge.reconciliation_bridge._load_match_for_preflight")
	@patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching")
	def test_dry_run_does_not_mutate_payment_entry_or_sales_invoice(self, _mock_access, mock_load):
		mock_load.return_value = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.frappe.get_doc") as mock_get_doc:
			dry_run_reconciliation_for_match("RE-BTM-2026-0006")

		mock_get_doc.assert_not_called()

	@patch("retailedge.reconciliation_bridge._load_match_for_preflight")
	@patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching")
	def test_dry_run_does_not_create_journal_entry_or_gl_entry(self, _mock_access, mock_load):
		mock_load.return_value = self._ready_payment_entry_match()
		with patch("retailedge.reconciliation_bridge.frappe.new_doc") as mock_new_doc:
			dry_run_reconciliation_for_match("RE-BTM-2026-0006")

		mock_new_doc.assert_not_called()

	@patch("retailedge.reconciliation_bridge._load_match_for_preflight")
	@patch("retailedge.reconciliation_bridge.assert_can_access_bank_transaction_matching")
	def test_dry_run_selected_groups_ready_and_blocked_results(self, _mock_access, mock_load):
		def load(name):
			if name == "READY":
				return self._ready_payment_entry_match(name="READY", bank_match_review="READY")
			return self._ready_payment_entry_match(
				name="BLOCKED",
				bank_match_review="BLOCKED",
				account_resolution_status="mismatch",
				blocking_reason="Bank and payment accounts do not align for safe reconciliation.",
			)

		mock_load.side_effect = load
		summary = dry_run_reconciliation_for_matches(["READY", "BLOCKED"])

		self.assertTrue(summary["dry_run"])
		self.assertEqual(summary["total_count"], 2)
		self.assertEqual(summary["ready_count"], 1)
		self.assertEqual(summary["blocked_count"], 1)
		self.assertEqual(len(summary["groups"][READINESS_GROUP_READY]), 1)
		self.assertEqual(len(summary["groups"][READINESS_GROUP_BLOCKED]), 1)

	def test_unconfirmed_match_fails_preflight(self):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				review_status="Needs Review",
				decision_status="Needs Review",
				reconciliation_readiness_status="Needs Review",
				handoff_status="Needs Review Before Reconciliation",
				blocking_reason="Review the match before reconciliation.",
			)
		)
		self.assertEqual(payload["status"], PREFLIGHT_NEEDS_REVIEW)

	def test_rejected_match_is_not_ready(self):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				review_status="Rejected",
				decision_status="Rejected",
				reconciliation_readiness_status="Not Ready",
				handoff_status="Not Eligible for Reconciliation",
				blocking_reason="Rejected or cancelled matches are not eligible.",
			)
		)
		self.assertEqual(payload["status"], PREFLIGHT_NOT_READY)

	def test_already_reconciled_status_is_preserved(self):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				reconciliation_readiness_status="Already Reconciled",
				handoff_status="Already Reconciled",
			)
		)
		self.assertEqual(payload["status"], PREFLIGHT_ALREADY_RECONCILED)

	def test_account_mismatch_becomes_exception(self):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				account_resolution_status="mismatch",
				reconciliation_readiness_status="Exception",
				handoff_status="Exception / Manual Investigation Required",
				blocking_reason="Bank and payment accounts do not align for safe reconciliation.",
			)
		)
		self.assertEqual(payload["status"], PREFLIGHT_EXCEPTION)

	def test_invoice_payment_row_preflight_stays_target_ambiguous(self):
		with patch(
			"retailedge.reconciliation_bridge.get_payment_entries_for_sales_invoice",
			return_value=[],
		):
			payload = build_reconciliation_preflight(
				self._ready_payment_entry_match(
					suggested_document_type="Sales Invoice",
					suggested_document="ACC-SINV-2026-00023",
					candidate_doctype="Sales Invoice",
					candidate_name="ACC-SINV-2026-00023",
					candidate_docstatus=1,
					candidate_category="Invoice Payment Row Match",
					payment_event_source="Invoice Payment Row",
					reconciliation_readiness_status="Ready for Reconciliation",
					handoff_status="Ready for ERPNext Reconciliation",
				)
			)
		self.assertEqual(payload["status"], PREFLIGHT_TARGET_AMBIGUOUS)
		self.assertEqual(payload["erpnext_target_status"], TARGET_MISSING)

	def test_missing_match_returns_safe_exception_payload(self):
		payload = build_reconciliation_preflight({})
		self.assertEqual(payload["status"], PREFLIGHT_EXCEPTION)
		self.assertTrue(payload["dry_run"])
		self.assertEqual(payload["native_reconciliation_method"], ERPNext_NATIVE_RECONCILIATION_METHOD)

	@patch("retailedge.reconciliation_bridge._load_match_for_preflight")
	def test_get_reconciliation_preflight_uses_loaded_match_context(self, mock_load):
		mock_load.return_value = self._ready_payment_entry_match()
		payload = get_reconciliation_preflight("RE-BTM-2026-0006")
		self.assertEqual(payload["status"], PREFLIGHT_READY)
		mock_load.assert_called_once_with("RE-BTM-2026-0006")

	def test_reconcile_bridge_dry_run_false_is_deferred(self):
		with patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			return_value=build_reconciliation_preflight(self._ready_payment_entry_match()),
		):
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertFalse(payload["dry_run"])
		self.assertFalse(payload["execution_attempted"])
		self.assertTrue(payload["execution_deferred"])
		self.assertIn("deferred in R6.0", payload["notes"])

	def test_api_wrapper_exposes_safe_preflight_output(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._get_reconciliation_preflight",
			return_value={"status": PREFLIGHT_READY, "dry_run": True},
		) as mock_preflight:
			payload = retailedge_api.get_reconciliation_preflight("RE-BTM-2026-0006")
			self.assertEqual(payload["status"], PREFLIGHT_READY)
			mock_preflight.assert_called_once_with("RE-BTM-2026-0006")

	def test_api_wrapper_exposes_guarded_reconcile_bridge(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._reconcile_confirmed_bank_match",
			return_value={"status": PREFLIGHT_READY, "dry_run": True},
		) as mock_bridge:
			payload = retailedge_api.reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=True)
			self.assertEqual(payload["status"], PREFLIGHT_READY)
			mock_bridge.assert_called_once_with(match_name="RE-BTM-2026-0006", dry_run=True)

