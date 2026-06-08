from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from retailedge import api as retailedge_api

from retailedge.reconciliation_handoff import (
	HANDOFF_ALREADY_RECONCILED,
	HANDOFF_EXCEPTION,
	HANDOFF_NOT_ELIGIBLE,
	HANDOFF_READY,
	classify_reconciliation_handoff,
	get_reconciliation_handoff_for_match,
	get_reconciliation_handoff_summary,
)
from retailedge.retailedge.report.retailedge_reconciliation_handoff.retailedge_reconciliation_handoff import (
	execute as execute_handoff_report,
	get_columns,
)


class ReconciliationHandoffTests(unittest.TestCase):
	def test_r54_report_json_disables_prepared_report_mode(self):
		report_path = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_reconciliation_handoff/retailedge_reconciliation_handoff.json"
		with open(report_path, encoding="utf-8") as handle:
			report_json = json.load(handle)
		self.assertEqual(report_json.get("disable_prepared_report"), 1)
		self.assertEqual(report_json.get("prepared_report"), 0)

	def test_r54_report_js_forces_live_refresh_behavior(self):
		report_path = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_reconciliation_handoff/retailedge_reconciliation_handoff.js"
		script = open(report_path, encoding="utf-8").read()
		self.assertIn("report.ignore_prepared_report = true;", script)
		self.assertIn("report.prepared_report = false;", script)
		self.assertIn('__("Refresh Report")', script)

	def test_classify_ready_payment_entry_handoff(self):
		status, priority, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00008",
				"bank_transaction": "ACC-BTN-2026-00008",
				"candidate_type": "Payment Entry Match",
				"reconciliation_readiness_status": "Ready for Reconciliation",
				"account_resolution_status": "match_via_mapping",
				"amount_scenario": "Submitted Payment Entry Amount",
			}
		)
		self.assertEqual(status, HANDOFF_READY)
		self.assertEqual(priority, "High")
		self.assertIn("Ready", reason)

	def test_cash_or_context_only_candidate_is_not_eligible(self):
		status, _, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "ACC-SINV-2026-00006",
				"bank_transaction": "ACC-BTN-2026-00001",
				"candidate_type": "cash",
				"reconciliation_readiness_status": "Not Ready",
			}
		)
		self.assertEqual(status, HANDOFF_NOT_ELIGIBLE)
		self.assertIn("not a bank-matchable payment event", reason)

	def test_account_mismatch_becomes_exception(self):
		status, _, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00012",
				"bank_transaction": "ACC-BTN-2026-00007",
				"candidate_type": "Payment Entry Match",
				"reconciliation_readiness_status": "Exception",
				"account_resolution_status": "mismatch",
			}
		)
		self.assertEqual(status, HANDOFF_EXCEPTION)
		self.assertIn("accounts do not align", reason)

	def test_amount_variance_becomes_exception(self):
		status, _, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00007",
				"bank_transaction": "ACC-BTN-2026-00005",
				"candidate_type": "Payment Entry Match",
				"reconciliation_readiness_status": "Not Ready",
				"account_resolution_status": "match",
				"amount_scenario": "Amount Variance",
			}
		)
		self.assertEqual(status, HANDOFF_EXCEPTION)
		self.assertIn("requires manual investigation", reason)

	def test_already_reconciled_is_classified_separately(self):
		status, _, _reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00008",
				"bank_transaction": "ACC-BTN-2026-00008",
				"reconciliation_readiness_status": "Already Reconciled",
			}
		)
		self.assertEqual(status, HANDOFF_ALREADY_RECONCILED)

	def test_duplicate_confirmed_candidate_is_exception(self):
		status, _, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00008",
				"bank_transaction": "ACC-BTN-2026-00008",
				"candidate_type": "Payment Entry Match",
				"reconciliation_readiness_status": "Ready for Reconciliation",
				"account_resolution_status": "match",
				"amount_scenario": "Submitted Payment Entry Amount",
			},
			conflict_counts={"by_bank_transaction": {}, "by_candidate": {"Payment Entry::ACC-PAY-2026-00008": 2}},
		)
		self.assertEqual(status, HANDOFF_EXCEPTION)
		self.assertIn("multiple active or confirmed matches", reason)

	@patch("retailedge.reconciliation_handoff.get_bank_match_reconciliation_readiness_rows")
	@patch("retailedge.reconciliation_handoff.get_payment_event_reconciliation_context")
	@patch("retailedge.reconciliation_handoff.get_bank_transaction_reconciliation_context")
	def test_rejected_matches_are_hidden_by_default(self, mock_bank_ctx, mock_payment_ctx, mock_readiness):
		mock_readiness.return_value = [
			{
				"bank_match_review": "RE-BTM-0010",
				"bank_transaction": "ACC-BTN-2026-00005",
				"review_status": "Rejected",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00007",
				"candidate_type": "Payment Entry Match",
				"reconciliation_readiness_status": "Not Ready",
				"account_resolution_status": "match",
				"amount_scenario": "Submitted Payment Entry Amount",
			}
		]
		mock_payment_ctx.return_value = {"candidate_doctype": "Payment Entry", "candidate_name": "ACC-PAY-2026-00007"}
		mock_bank_ctx.return_value = {"bank_transaction": "ACC-BTN-2026-00005"}
		result = get_reconciliation_handoff_summary({"from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(result["rows"], [])

	def test_failed_reconciliation_is_classified_as_exception(self):
		status, priority, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00012",
				"bank_transaction": "ACC-BTN-2026-00007",
				"reconciliation_readiness_status": "Not Ready",
				"reconciliation_status": "Reconciliation Failed",
				"reconciliation_result_message": "ERPNext native reconciliation failed: mock native failure",
			}
		)
		self.assertEqual(status, HANDOFF_EXCEPTION)
		self.assertEqual(priority, "High")
		self.assertIn("failed", reason.lower())

	def test_candidate_summary_mismatch_is_classified_as_exception(self):
		status, priority, reason = classify_reconciliation_handoff(
			{
				"review_status": "Confirmed",
				"suggested_document_type": "Payment Entry",
				"suggested_document": "ACC-PAY-2026-00004",
				"payment_entry": "ACC-PAY-2026-00004",
				"bank_transaction": "ACC-BTN-2026-00007",
				"reconciliation_readiness_status": "Not Ready",
				"reconciliation_status": "Reconciliation Failed",
				"reconciliation_integrity_status": "Candidate Summary Mismatch",
				"reconciliation_integrity_reason": "Current Payment Entry candidate ACC-PAY-2026-00004 does not match failed reconciliation target ACC-PAY-2026-00012.",
			}
		)
		self.assertEqual(status, HANDOFF_EXCEPTION)
		self.assertEqual(priority, "High")
		self.assertIn("ACC-PAY-2026-00012", reason)


	@patch("retailedge.reconciliation_handoff.get_reconciliation_handoff_summary")
	def test_api_returns_safe_user_friendly_output(self, mock_summary):
		mock_summary.return_value = {
			"rows": [
				{
					"bank_match_review": "RE-BTM-0001",
					"handoff_status": HANDOFF_READY,
					"handoff_priority": "High",
					"recommended_action": "Open ERPNext Bank Reconciliation...",
					"reviewer_message": "Ready",
					"blocking_reason": "",
					"erpnext_reconciliation_target": "ACC-BTN-2026-00008",
					"erpnext_reconciliation_notes": "Use Payment Entry ACC-PAY-2026-00008",
					"bank_transaction": "ACC-BTN-2026-00008",
					"candidate_doctype": "Payment Entry",
					"candidate_name": "ACC-PAY-2026-00008",
					"match_type": "Payment Entry Match",
					"match_status": "Confirmed",
					"readiness_status": "Ready for Reconciliation",
				}
			]
		}
		payload = get_reconciliation_handoff_for_match("RE-BTM-0001")
		self.assertEqual(payload["handoff_status"], HANDOFF_READY)
		self.assertNotIn("details_json", payload)

	def test_api_wrapper_exposes_safe_handoff_output(self):
		with patch("retailedge.api._assert_can_access_bank_transaction_matching"), patch(
			"retailedge.api._get_reconciliation_handoff_for_match",
			return_value={"handoff_status": HANDOFF_READY, "recommended_action": "Open ERPNext Bank Reconciliation..."},
		) as mock_handoff:
			payload = retailedge_api.get_reconciliation_handoff_for_match("RE-BTM-0001")
			self.assertEqual(payload["handoff_status"], HANDOFF_READY)
			mock_handoff.assert_called_once_with("RE-BTM-0001")

	@patch("retailedge.retailedge.report.retailedge_reconciliation_handoff.retailedge_reconciliation_handoff.get_reconciliation_handoff_summary")
	def test_report_executes_from_current_helper_data(self, mock_summary):
		mock_summary.return_value = {"rows": [{"bank_transaction": "ACC-BTN-2026-00008"}], "summary": {"ready": 1, "needs_review": 0, "exception": 0}}
		_columns, rows, _message, _chart, summary = execute_handoff_report({"from_date": "2026-05-01", "to_date": "2026-05-31"})
		self.assertEqual(rows, [{"bank_transaction": "ACC-BTN-2026-00008"}])
		self.assertEqual(summary[0]["value"], 1)

	def test_report_returns_safe_columns_only(self):
		column_names = {column["fieldname"] for column in get_columns()}
		self.assertIn("recommended_action", column_names)
		self.assertNotIn("details_json", column_names)
