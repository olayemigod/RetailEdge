from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge import api as retailedge_api
from retailedge.reconciliation_bridge import (
	ERPNext_NATIVE_RECONCILIATION_METHOD,
	PREFLIGHT_ALREADY_RECONCILED,
	PREFLIGHT_EXCEPTION,
	PREFLIGHT_NEEDS_REVIEW,
	PREFLIGHT_NOT_READY,
	PREFLIGHT_READY,
	PREFLIGHT_TARGET_AMBIGUOUS,
	TARGET_AMBIGUOUS,
	TARGET_AVAILABLE,
	TARGET_MISSING,
	TARGET_MANUAL_REVIEW,
	build_reconciliation_preflight,
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
		self.assertFalse(payload["native_execution_supported"])

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

