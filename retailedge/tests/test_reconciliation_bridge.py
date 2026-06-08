from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from retailedge import api as retailedge_api
from retailedge.reconciliation_bridge import (
	ERPNext_NATIVE_RECONCILIATION_METHOD,
	PREFLIGHT_ALREADY_RECONCILED,
	PREFLIGHT_EXCEPTION,
	PREFLIGHT_NEEDS_REVIEW,
	PREFLIGHT_NOT_READY,
	PREFLIGHT_READY,
	PREFLIGHT_TARGET_AMBIGUOUS,
	RECONCILIATION_STATUS_FAILED,
	RECONCILIATION_INTEGRITY_MISMATCH,
	RECONCILIATION_STATUS_RECONCILED,
	TARGET_AMBIGUOUS,
	TARGET_AVAILABLE,
	TARGET_MISSING,
	TARGET_MANUAL_REVIEW,
	build_reconciliation_preflight,
	get_reconciliation_bridge_settings,
	get_reconciliation_preflight,
	reconcile_confirmed_bank_match,
	resolve_reconciliation_target,
	validate_reconciliation_match_integrity,
)


class ReconciliationBridgeTests(unittest.TestCase):
	def _mismatched_failed_payment_entry_match(self, **overrides):
		row = self._ready_payment_entry_match(
			suggested_document="ACC-PAY-2026-00004",
			candidate_name="ACC-PAY-2026-00004",
			payment_entry="ACC-PAY-2026-00004",
			candidate_amount=15000,
			match_confidence="Weak Match",
			match_score=45,
			reconciliation_status="Reconciliation Failed",
			reconciliation_target_doctype="Payment Entry",
			reconciliation_target="ACC-PAY-2026-00012",
			reconciliation_result_message="ERPNext native reconciliation failed: Payment Entry ACC-PAY-2026-00012 is not affecting bank account None",
		)
		row.update(overrides)
		return row

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
			"reconciliation_status": "Not Reconciled",
		}
		row.update(overrides)
		return row

	def _mock_match_doc(self, **overrides):
		doc = MagicMock()
		doc.name = "RE-BTM-2026-0006"
		doc.bank_transaction = "ACC-BTN-2026-00007"
		doc.suggested_document_type = "Payment Entry"
		doc.suggested_document = "ACC-PAY-2026-00012"
		doc.decision_status = "Confirmed"
		doc.reconciliation_status = "Not Reconciled"
		doc.reconciled_on = None
		doc.reconciled_by = None
		doc.reconciliation_method = None
		doc.reconciliation_target_doctype = None
		doc.reconciliation_target = None
		doc.reconciliation_result_message = None
		for key, value in overrides.items():
			setattr(doc, key, value)
		return doc

	def _mock_bank_transaction_doc(self, **overrides):
		doc = MagicMock()
		doc.name = "ACC-BTN-2026-00007"
		doc.status = "Unreconciled"
		doc.allocated_amount = 0.0
		doc.unallocated_amount = 1090.0
		doc.docstatus = 1
		for key, value in overrides.items():
			setattr(doc, key, value)
		return doc

	def _mock_payment_entry_doc(self, **overrides):
		doc = MagicMock()
		doc.name = "ACC-PAY-2026-00012"
		doc.docstatus = 1
		for key, value in overrides.items():
			setattr(doc, key, value)
		return doc

	def test_r61_settings_json_contains_safe_execution_gates(self):
		report_path = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_settings/retailedge_settings.json"
		with open(report_path, encoding="utf-8") as handle:
			payload = json.load(handle)
		fieldnames = {field.get("fieldname") for field in payload.get("fields", [])}
		self.assertIn("enable_bank_reconciliation_bridge", fieldnames)
		self.assertIn("allow_payment_entry_reconciliation_execution", fieldnames)
		self.assertIn("require_reconciliation_preflight", fieldnames)

	def test_r61_match_doctype_tracks_reconciliation_outcome_fields(self):
		report_path = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_transaction_match/retailedge_bank_transaction_match.json"
		with open(report_path, encoding="utf-8") as handle:
			payload = json.load(handle)
		fieldnames = {field.get("fieldname") for field in payload.get("fields", [])}
		self.assertIn("reconciliation_status", fieldnames)
		self.assertIn("reconciled_on", fieldnames)
		self.assertIn("reconciled_by", fieldnames)
		self.assertIn("reconciliation_method", fieldnames)
		self.assertIn("reconciliation_target_doctype", fieldnames)
		self.assertIn("reconciliation_target", fieldnames)

	@patch("retailedge.reconciliation_bridge.get_retailedge_settings")
	def test_reconciliation_bridge_settings_default_to_safe_disabled_mode(self, mock_settings):
		mock_settings.return_value = type("Settings", (), {})()
		settings = get_reconciliation_bridge_settings()
		self.assertEqual(settings["enable_bank_reconciliation_bridge"], 0)
		self.assertEqual(settings["allow_payment_entry_reconciliation_execution"], 0)
		self.assertEqual(settings["require_reconciliation_preflight"], 1)

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

	def test_preflight_blocks_payment_entry_when_bank_transaction_account_is_unresolved(self):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				bank_account="Unmapped Bank Account",
				resolved_bank_account="",
			)
		)
		self.assertEqual(payload["status"], PREFLIGHT_NOT_READY)
		self.assertEqual(payload["preflight_bank_account_validation_status"], "bank_transaction_account_unresolved")
		self.assertIn("Account Unresolved", payload["blocking_reason"])

	@patch("retailedge.reconciliation_bridge.get_payment_entry_gl_bank_accounts", return_value={})
	def test_preflight_blocks_payment_entry_when_bank_accounts_do_not_match(self, _mock_gl_accounts):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				resolved_bank_account="Demo Bank Account - PED",
				candidate_account="Other Bank - PED",
				payment_account="Other Bank - PED",
				resolved_payment_account="Other Bank - PED",
			)
		)
		self.assertEqual(payload["status"], PREFLIGHT_NOT_READY)
		self.assertEqual(payload["preflight_bank_account_validation_status"], "payment_entry_bank_account_mismatch")
		self.assertIn("Payment Entry Bank Account Mismatch", payload["blocking_reason"])

	def test_preflight_in_execution_mode_honours_execution_settings(self):
		with patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 0,
				"allow_payment_entry_reconciliation_execution": 0,
				"require_reconciliation_preflight": 1,
			},
		):
			payload = build_reconciliation_preflight(self._ready_payment_entry_match(), execution_intent=True)
		self.assertEqual(payload["status"], PREFLIGHT_NOT_READY)
		self.assertIn("disabled in RetailEdge Settings", payload["blocking_reason"])

	@patch("retailedge.reconciliation_bridge._load_match_for_preflight")
	def test_get_reconciliation_preflight_uses_loaded_match_context(self, mock_load):
		mock_load.return_value = self._ready_payment_entry_match()
		payload = get_reconciliation_preflight("RE-BTM-2026-0006")
		self.assertEqual(payload["status"], PREFLIGHT_READY)
		mock_load.assert_called_once_with("RE-BTM-2026-0006")

	def test_dry_run_true_for_ready_payment_entry_match_is_read_only(self):
		with patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			return_value=build_reconciliation_preflight(self._ready_payment_entry_match()),
		), patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match") as mock_perm, patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=True)
		self.assertEqual(payload["status"], PREFLIGHT_READY)
		self.assertTrue(payload["dry_run"])
		self.assertFalse(payload["execution_attempted"])
		mock_perm.assert_not_called()
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_when_bridge_disabled(self):
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[
				build_reconciliation_preflight(self._ready_payment_entry_match()),
				build_reconciliation_preflight(self._ready_payment_entry_match()),
			],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 0,
				"allow_payment_entry_reconciliation_execution": 0,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._mock_match_doc()), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertIn("disabled in RetailEdge Settings", payload["blocking_reason"])
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_when_payment_entry_execution_disabled(self):
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[
				build_reconciliation_preflight(self._ready_payment_entry_match()),
				build_reconciliation_preflight(self._ready_payment_entry_match()),
			],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 0,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._mock_match_doc()), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertIn("Payment Entry reconciliation execution is disabled", payload["blocking_reason"])
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_for_unconfirmed_match(self):
		needs_review = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				decision_status="Suggested",
				review_status="Suggested",
				reconciliation_readiness_status="Needs Review",
				handoff_status="Needs Review Before Reconciliation",
				blocking_reason="Decision is not confirmed yet.",
			)
		)
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[needs_review, needs_review],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._mock_match_doc(decision_status="Suggested")), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertEqual(payload["status"], PREFLIGHT_NEEDS_REVIEW)
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_for_invoice_payment_row_match(self):
		invoice_preflight = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				suggested_document_type="Sales Invoice",
				suggested_document="ACC-SINV-2026-00023",
				candidate_doctype="Sales Invoice",
				candidate_name="ACC-SINV-2026-00023",
				candidate_category="Invoice Payment Row Match",
				payment_event_source="Invoice Payment Row",
				reconciliation_readiness_status="Ready for Reconciliation",
				handoff_status="Ready for ERPNext Reconciliation",
			)
		)
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[invoice_preflight, invoice_preflight],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._mock_match_doc(suggested_document_type="Sales Invoice", suggested_document="ACC-SINV-2026-00023")), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0009", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertEqual(payload["status"], PREFLIGHT_TARGET_AMBIGUOUS)
		self.assertIn("Payment voucher missing", payload["blocking_reason"])
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_for_target_ambiguous_or_missing(self):
		ambiguous = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				suggested_document_type="Sales Invoice",
				suggested_document="ACC-SINV-2026-00023",
				candidate_doctype="Sales Invoice",
				candidate_name="ACC-SINV-2026-00023",
				candidate_category="POS Payment Match",
				payment_event_source="POS Payment Row",
				reconciliation_readiness_status="Ready for Reconciliation",
				handoff_status="Ready for ERPNext Reconciliation",
			)
		)
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ambiguous, ambiguous],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._mock_match_doc(suggested_document_type="Sales Invoice")), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0009", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertEqual(payload["status"], PREFLIGHT_TARGET_AMBIGUOUS)
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_if_payment_entry_is_not_submitted(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc()
		bank_doc = self._mock_bank_transaction_doc()
		payment_doc = self._mock_payment_entry_doc(docstatus=0)
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc",
			side_effect=[match_doc, bank_doc, payment_doc],
		), patch("retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable") as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertEqual(payload["blocking_reason"], "Payment Entry is not submitted.")
		mock_native.assert_not_called()

	def test_dry_run_false_is_blocked_if_bank_transaction_already_reconciled(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc()
		bank_doc = self._mock_bank_transaction_doc(status="Reconciled")
		payment_doc = self._mock_payment_entry_doc()
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc",
			side_effect=[match_doc, bank_doc, payment_doc],
		), patch("retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable") as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Skipped")
		self.assertEqual(payload["blocking_reason"], "Bank Transaction is already reconciled.")
		mock_native.assert_not_called()

	def test_dry_run_false_reruns_preflight_immediately_before_execution(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc(reconciliation_status="Reconciled")
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		) as mock_preflight, patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=match_doc), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(mock_preflight.call_count, 2)
		self.assertEqual(payload["execution_status"], "Skipped")
		mock_native.assert_not_called()

	def test_execution_calls_native_reconcile_vouchers_only_for_ready_payment_entry_match(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc()
		bank_doc = self._mock_bank_transaction_doc()
		payment_doc = self._mock_payment_entry_doc()
		updated_bank_doc = self._mock_bank_transaction_doc(status="Reconciled", allocated_amount=1090, unallocated_amount=0)
		native = MagicMock(return_value=updated_bank_doc)
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc",
			side_effect=[match_doc, bank_doc, payment_doc],
		), patch(
			"retailedge.reconciliation_bridge._payment_entry_already_linked_to_other_bank_transaction",
			return_value=[],
		), patch(
			"retailedge.reconciliation_bridge._active_conflict_counts",
			return_value={
				"by_bank_transaction": {"ACC-BTN-2026-00007": 1},
				"by_candidate": {"Payment Entry::ACC-PAY-2026-00012": 1},
			},
		), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable",
			return_value=native,
		), patch(
			"retailedge.reconciliation_bridge._save_match_with_reconciliation_log"
		) as mock_log, patch(
			"retailedge.reconciliation_bridge.now_datetime",
			return_value="2026-06-04 10:00:00",
		):
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		native.assert_called_once()
		args, _kwargs = native.call_args
		self.assertEqual(args[0], "ACC-BTN-2026-00007")
		voucher_payload = json.loads(args[1])
		self.assertEqual(voucher_payload[0]["payment_doctype"], "Payment Entry")
		self.assertEqual(voucher_payload[0]["payment_name"], "ACC-PAY-2026-00012")
		self.assertEqual(payload["execution_status"], "Succeeded")
		self.assertEqual(match_doc.reconciliation_status, RECONCILIATION_STATUS_RECONCILED)
		self.assertEqual(match_doc.reconciliation_target_doctype, "Payment Entry")
		self.assertEqual(match_doc.reconciliation_target, "ACC-PAY-2026-00012")
		self.assertFalse(match_doc.save.called)
		mock_log.assert_called_once()

	def test_failed_native_reconciliation_does_not_mutate_candidate_summary(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc()
		match_doc.suggested_document_type = "Payment Entry"
		match_doc.suggested_document = "ACC-PAY-2026-00012"
		match_doc.match_confidence = "Strong Match"
		match_doc.match_score = 100
		match_doc.amount_scenario = "Submitted Payment Entry Amount"
		match_doc.party = "West View"
		match_doc.customer = "West View"
		match_doc.candidate_amount = 1090
		original = {
			"suggested_document_type": match_doc.suggested_document_type,
			"suggested_document": match_doc.suggested_document,
			"match_confidence": match_doc.match_confidence,
			"match_score": match_doc.match_score,
			"amount_scenario": match_doc.amount_scenario,
			"party": match_doc.party,
			"customer": match_doc.customer,
			"candidate_amount": match_doc.candidate_amount,
		}
		bank_doc = self._mock_bank_transaction_doc()
		payment_doc = self._mock_payment_entry_doc()
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc",
			side_effect=[match_doc, bank_doc, payment_doc],
		), patch(
			"retailedge.reconciliation_bridge._payment_entry_already_linked_to_other_bank_transaction",
			return_value=[],
		), patch(
			"retailedge.reconciliation_bridge._active_conflict_counts",
			return_value={
				"by_bank_transaction": {"ACC-BTN-2026-00007": 1},
				"by_candidate": {"Payment Entry::ACC-PAY-2026-00012": 1},
			},
		), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable",
			return_value=MagicMock(side_effect=RuntimeError("mock native failure")),
		), patch(
			"retailedge.reconciliation_bridge._save_match_with_reconciliation_log"
		) as mock_log:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Failed")
		self.assertEqual(match_doc.reconciliation_status, RECONCILIATION_STATUS_FAILED)
		self.assertEqual(match_doc.reconciliation_target_doctype, "Payment Entry")
		self.assertEqual(match_doc.reconciliation_target, "ACC-PAY-2026-00012")
		self.assertFalse(match_doc.save.called)
		mock_log.assert_called_once()
		for fieldname, expected in original.items():
			self.assertEqual(getattr(match_doc, fieldname), expected)

	def test_failed_status_dry_run_remains_inspectable(self):
		payload = build_reconciliation_preflight(
			self._ready_payment_entry_match(
				reconciliation_status="Reconciliation Failed",
				reconciliation_result_message="ERPNext native reconciliation failed: mock native failure",
			)
		)
		self.assertTrue(payload["needs_attention"])
		self.assertEqual(payload["status"], PREFLIGHT_READY)

	def test_validate_reconciliation_match_integrity_reports_safe_no_outcome(self):
		with patch("retailedge.reconciliation_bridge._load_match_for_preflight", return_value=self._ready_payment_entry_match()):
			result = validate_reconciliation_match_integrity("RE-BTM-2026-0006")
		self.assertFalse(result["mismatch_detected"])
		self.assertEqual(result["integrity_status"], "No Reconciliation Outcome")

	def test_validate_reconciliation_candidate_mismatch_payload(self):
		with patch("retailedge.reconciliation_bridge._load_match_for_preflight", return_value=self._mismatched_failed_payment_entry_match()):
			result = validate_reconciliation_match_integrity("RE-BTM-2026-0006")
		self.assertTrue(result["mismatch_detected"])
		self.assertEqual(result["integrity_status"], RECONCILIATION_INTEGRITY_MISMATCH)
		self.assertIn("ACC-PAY-2026-00004", result["mismatch_reason"])
		self.assertIn("ACC-PAY-2026-00012", result["mismatch_reason"])

	def test_dry_run_blocks_candidate_summary_mismatch(self):
		payload = build_reconciliation_preflight(self._mismatched_failed_payment_entry_match())
		self.assertEqual(payload["status"], PREFLIGHT_EXCEPTION)
		self.assertFalse(payload["execution_attempted"])
		self.assertTrue(payload["needs_attention"])
		self.assertTrue(payload["mismatch_detected"])
		self.assertEqual(payload["readiness_status"], "Not Ready")
		self.assertIn("Candidate Summary Mismatch", payload["handoff_status"])

	def test_execution_blocks_candidate_summary_mismatch_without_native_call(self):
		mismatch = build_reconciliation_preflight(self._mismatched_failed_payment_entry_match())
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[mismatch, mismatch],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc", return_value=self._mock_match_doc(reconciliation_status="Reconciliation Failed")
		), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertFalse(payload["execution_attempted"])
		self.assertIn("not match", payload["blocking_reason"])
		mock_native.assert_not_called()

	def test_reset_failed_reconciliation_preserves_candidate_fields(self):
		match_doc = self._mock_match_doc(
			reconciliation_status="Reconciliation Failed",
			reconciliation_target_doctype="Payment Entry",
			reconciliation_target="ACC-PAY-2026-00012",
			reconciliation_result_message="ERPNext native reconciliation failed: Payment Entry ACC-PAY-2026-00012 is not affecting bank account None",
			suggested_document_type="Payment Entry",
			suggested_document="ACC-PAY-2026-00004",
			payment_entry="ACC-PAY-2026-00004",
			candidate_type="Payment Entry",
			candidate_amount=15000,
			candidate_posting_date="2026-03-11",
			payment_event_source="Payment Entry",
			payment_account="Demo Bank Account - PED",
			resolved_payment_account="Demo Bank Account - PED",
			match_confidence="Weak Match",
			match_score=45,
			review_status="Confirmed",
			match_status="Weak Match",
		)
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc", return_value=match_doc
		), patch(
			"retailedge.reconciliation_bridge._save_match_with_reconciliation_log"
		) as mock_log:
			payload = retailedge_api.reset_failed_reconciliation_status("RE-BTM-2026-0006")
		self.assertEqual(payload["reconciliation_status"], "Not Reconciled")
		self.assertEqual(payload["before"]["reconciliation_target"], "ACC-PAY-2026-00012")
		self.assertIsNone(payload["after"]["reconciliation_target"])
		self.assertEqual(payload["candidate_summary_before"]["suggested_document"], "ACC-PAY-2026-00004")
		self.assertEqual(payload["candidate_summary_after"]["suggested_document"], "ACC-PAY-2026-00004")
		self.assertEqual(match_doc.suggested_document, "ACC-PAY-2026-00004")
		self.assertEqual(match_doc.payment_entry, "ACC-PAY-2026-00004")
		mock_log.assert_called_once()


	def test_api_wrapper_exposes_failed_reconciliation_reset(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._reset_failed_reconciliation_status",
			return_value={"reconciliation_status": "Not Reconciled"},
		) as mock_reset:
			payload = retailedge_api.reset_failed_reconciliation_status("RE-BTM-2026-0006")
			self.assertEqual(payload["reconciliation_status"], "Not Reconciled")
			mock_reset.assert_called_once_with("RE-BTM-2026-0006")

	def test_api_wrapper_exposes_reconciliation_integrity_validation(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._validate_reconciliation_match_integrity",
			return_value={"mismatch_detected": True, "integrity_status": RECONCILIATION_INTEGRITY_MISMATCH},
		) as mock_validate:
			payload = retailedge_api.validate_reconciliation_match_integrity("RE-BTM-2026-0006")
			self.assertTrue(payload["mismatch_detected"])
			mock_validate.assert_called_once_with("RE-BTM-2026-0006")

	def test_duplicate_rerun_reconciliation_is_blocked(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc(reconciliation_status="Reconciled")
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch("retailedge.reconciliation_bridge.frappe.get_doc", return_value=match_doc), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable"
		) as mock_native:
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Skipped")
		self.assertIn("already reconciled", payload["blocking_reason"].lower())
		mock_native.assert_not_called()

	def test_friendly_error_is_returned_if_native_method_is_unsupported(self):
		ready = build_reconciliation_preflight(self._ready_payment_entry_match())
		match_doc = self._mock_match_doc()
		bank_doc = self._mock_bank_transaction_doc()
		payment_doc = self._mock_payment_entry_doc()
		with patch("retailedge.reconciliation_bridge.assert_can_manage_bank_transaction_match"), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_preflight",
			side_effect=[ready, ready],
		), patch(
			"retailedge.reconciliation_bridge.get_reconciliation_bridge_settings",
			return_value={
				"enable_bank_reconciliation_bridge": 1,
				"allow_payment_entry_reconciliation_execution": 1,
				"require_reconciliation_preflight": 1,
			},
		), patch(
			"retailedge.reconciliation_bridge.frappe.get_doc",
			side_effect=[match_doc, bank_doc, payment_doc],
		), patch(
			"retailedge.reconciliation_bridge._payment_entry_already_linked_to_other_bank_transaction",
			return_value=[],
		), patch(
			"retailedge.reconciliation_bridge._active_conflict_counts",
			return_value={
				"by_bank_transaction": {"ACC-BTN-2026-00007": 1},
				"by_candidate": {"Payment Entry::ACC-PAY-2026-00012": 1},
			},
		), patch(
			"retailedge.reconciliation_bridge._get_native_reconcile_vouchers_callable",
			side_effect=RuntimeError("unsupported signature"),
		):
			payload = reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=False)
		self.assertEqual(payload["execution_status"], "Blocked")
		self.assertIn("unavailable or unsupported", payload["blocking_reason"])

	def test_api_wrapper_exposes_safe_preflight_output(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._get_reconciliation_preflight",
			return_value={"status": PREFLIGHT_READY, "dry_run": True},
		) as mock_preflight:
			payload = retailedge_api.get_reconciliation_preflight("RE-BTM-2026-0006")
			self.assertEqual(payload["status"], PREFLIGHT_READY)
			mock_preflight.assert_called_once_with("RE-BTM-2026-0006", execution_intent=False)

	def test_api_wrapper_exposes_guarded_reconcile_bridge(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._reconcile_confirmed_bank_match",
			return_value={"status": PREFLIGHT_READY, "dry_run": True},
		) as mock_bridge:
			payload = retailedge_api.reconcile_confirmed_bank_match("RE-BTM-2026-0006", dry_run=True)
			self.assertEqual(payload["status"], PREFLIGHT_READY)
			mock_bridge.assert_called_once_with(match_name="RE-BTM-2026-0006", dry_run=True)
