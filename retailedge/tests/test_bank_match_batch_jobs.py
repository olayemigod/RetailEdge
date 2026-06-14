from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.bank_match_batch_jobs import (
	MAX_SYNC_ROWS,
	_job_summary,
	_process_job_row,
	refresh_bank_match_batch_job_progress,
	retry_bank_match_batch_job_rows,
	cancel_bank_match_batch_job,
	background_required_response,
	create_bank_match_batch_job,
	process_bank_match_batch_job,
	should_run_background,
)
from retailedge.tests.test_bank_transaction_match_workflow import _FakeMatchDoc


class BankMatchBatchJobTests(unittest.TestCase):
	def test_background_threshold_uses_safe_sync_limit(self):
		rows = [{"bank_transaction": f"BTN-{idx}"} for idx in range(MAX_SYNC_ROWS)]
		self.assertFalse(should_run_background(rows=json.dumps(rows)))

		rows.append({"bank_transaction": "BTN-OVER-LIMIT"})
		self.assertTrue(should_run_background(rows=json.dumps(rows)))

	def test_background_required_response_is_operator_friendly(self):
		result = background_required_response("Create Review Records", MAX_SYNC_ROWS + 1)
		self.assertTrue(result["requires_background"])
		self.assertEqual(result["max_sync_rows"], MAX_SYNC_ROWS)
		self.assertIn("Run as a background job", result["message"])

	def test_batch_job_doctypes_are_standard_and_importable(self):
		self.assertTrue(frappe.db.exists("DocType", "RetailEdge Bank Match Batch Job"))
		self.assertTrue(frappe.db.exists("DocType", "RetailEdge Bank Match Batch Job Row"))

		parent_path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_match_batch_job/retailedge_bank_match_batch_job.py"
		)
		child_path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_match_batch_job_row/retailedge_bank_match_batch_job_row.py"
		)
		self.assertIn("class RetailEdgeBankMatchBatchJob", parent_path.read_text())
		self.assertIn("class RetailEdgeBankMatchBatchJobRow", child_path.read_text())

	def test_create_batch_job_preserves_exact_row_payload_without_enqueue(self):
		row = {
			"candidate_key": "BTN-1|Payment Entry|PE-1|Payment Entry Match|",
			"bank_transaction": "BTN-1",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-1",
			"candidate_category": "Payment Entry Match",
			"payment_event_source": "Payment Entry",
			"match_score": 90,
		}

		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		self.assertEqual(result["status"], "queued")

		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		self.assertEqual(job.total_rows, 1)
		self.assertEqual(job.rows[0].candidate_key, row["candidate_key"])
		self.assertEqual(json.loads(job.rows[0].input_payload_json)["suggested_document"], "PE-1")

		frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)

	def test_duplicate_active_job_prevents_second_queue_for_same_selection(self):
		row = {
			"candidate_key": "BTN-DUP|Payment Entry|PE-DUP|Payment Entry Match|",
			"bank_transaction": "BTN-DUP",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-DUP",
			"candidate_category": "Payment Entry Match",
		}
		first = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		try:
			second = create_bank_match_batch_job(
				action_type="Create Review Records",
				rows=json.dumps([row]),
				enqueue=0,
			)

			self.assertEqual(second["status"], "duplicate_active_job")
			self.assertEqual(second["batch_job"], first["batch_job"])
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", first["batch_job"], force=True)

	def test_cancelled_job_summary_is_operator_friendly(self):
		row = {
			"candidate_key": "BTN-CANCEL|Payment Entry|PE-CANCEL|Payment Entry Match|",
			"bank_transaction": "BTN-CANCEL",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-CANCEL",
			"candidate_category": "Payment Entry Match",
		}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		try:
			job.status = "Cancelled"
			job.rows[0].result_status = "Skipped"
			job.rows[0].result_message = "Job cancelled before processing."
			summary = _job_summary(job)

			self.assertEqual(summary["status"], "Cancelled")
			self.assertFalse(summary["can_cancel"])
			self.assertFalse(summary["can_retry"])
			self.assertIn("Cancelled", summary["progress_label"])
			self.assertEqual(summary["row_status_counts"]["Skipped"], 1)
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)

	def test_cancel_active_job_marks_pending_rows_cancelled(self):
		row = {
			"candidate_key": "BTN-ACTIVE-CANCEL|Payment Entry|PE-ACTIVE-CANCEL|Payment Entry Match|",
			"bank_transaction": "BTN-ACTIVE-CANCEL",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-ACTIVE-CANCEL",
			"candidate_category": "Payment Entry Match",
		}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		try:
			summary = cancel_bank_match_batch_job(result["batch_job"], reason="Operator cancelled")
			job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])

			self.assertEqual(summary["status"], "Cancelled")
			self.assertFalse(summary["can_cancel"])
			self.assertEqual(job.cancel_requested, 1)
			self.assertEqual(job.rows[0].result_status, "Skipped")
			self.assertIn("cancelled", job.rows[0].result_message.lower())
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", result["batch_job"], force=True)

	def test_cancel_terminal_job_is_denied(self):
		row = {"candidate_key": "BTN-TERMINAL-CANCEL", "bank_transaction": "BTN-TERMINAL-CANCEL"}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		try:
			job.status = "Completed"
			job.flags.ignore_links = True
			job.save(ignore_permissions=True)
			with self.assertRaises(frappe.ValidationError):
				cancel_bank_match_batch_job(job.name, reason="Too late")
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)

	def test_retry_failed_rows_only_includes_failed_rows(self):
		failed_row = {"candidate_key": "BTN-FAILED", "bank_transaction": "BTN-FAILED"}
		success_row = {"candidate_key": "BTN-SUCCESS", "bank_transaction": "BTN-SUCCESS"}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([failed_row, success_row]),
			enqueue=0,
		)
		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		try:
			job.status = "Completed With Errors"
			job.rows[0].result_status = "Failed"
			job.rows[1].result_status = "Created"
			job.flags.ignore_links = True
			job.save(ignore_permissions=True)

			with patch("retailedge.bank_match_batch_jobs.create_bank_match_batch_job") as mock_create_job:
				mock_create_job.return_value = {"status": "queued", "batch_job": "RE-BMBJ-RETRY"}
				retry_bank_match_batch_job_rows(job.name, enqueue=0)

			kwargs = mock_create_job.call_args.kwargs
			retry_rows = json.loads(kwargs["rows"])
			self.assertEqual(len(retry_rows), 1)
			self.assertEqual(retry_rows[0]["candidate_key"], "BTN-FAILED")
			self.assertNotIn("BTN-SUCCESS", json.dumps(retry_rows))
			self.assertEqual(kwargs["retry_of"], job.name)
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)

	def test_retry_active_job_is_denied(self):
		row = {"candidate_key": "BTN-ACTIVE-RETRY", "bank_transaction": "BTN-ACTIVE-RETRY"}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		try:
			with self.assertRaises(frappe.ValidationError):
				retry_bank_match_batch_job_rows(result["batch_job"], enqueue=0)
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", result["batch_job"], force=True)

	def test_refresh_summary_is_operator_friendly_and_omits_payloads(self):
		row = {
			"candidate_key": "BTN-SUMMARY|Payment Entry|PE-SUMMARY|Payment Entry Match|",
			"bank_transaction": "BTN-SUMMARY",
			"suggested_document": "PE-SUMMARY",
		}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)
		try:
			summary = refresh_bank_match_batch_job_progress(result["batch_job"])
			self.assertIn("message", summary)
			self.assertIn("rows processed", summary["message"])
			self.assertNotIn("selected_rows_json", summary)
			self.assertNotIn("filters_json", summary)
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", result["batch_job"], force=True)

	def test_batch_job_action_permission_guard_denies_without_document_access(self):
		class FakeJob:
			name = "RE-BMBJ-NOACCESS"

			def has_permission(self, permission_type):
				return False

		with patch("retailedge.bank_match_batch_jobs.frappe.get_doc", return_value=FakeJob()):
			with self.assertRaises(frappe.PermissionError):
				refresh_bank_match_batch_job_progress("RE-BMBJ-NOACCESS")

	def test_batch_job_payload_metadata_is_hidden_no_copy_and_visible_to_retailedge_roles(self):
		path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_bank_match_batch_job/retailedge_bank_match_batch_job.json"
		)
		doctype = json.loads(path.read_text())
		fields = {field["fieldname"]: field for field in doctype["fields"]}
		for fieldname in ("filters_json", "selected_keys_json", "selected_rows_json", "summary_json", "selection_fingerprint"):
			with self.subTest(fieldname=fieldname):
				self.assertEqual(fields[fieldname].get("hidden"), 1)
				self.assertEqual(fields[fieldname].get("no_copy"), 1)

		permissions = {row["role"]: row for row in doctype["permissions"]}
		self.assertEqual(permissions["RetailEdgeManager"]["read"], 1)
		self.assertEqual(permissions["RetailEdgeAuditor"]["read"], 1)
		self.assertNotEqual(permissions["RetailEdgeAuditor"].get("write"), 1)

	@patch("retailedge.bank_match_batch_jobs.create_bank_match_reviews_from_suggestions")
	def test_background_create_review_uses_existing_safe_helper(self, mock_create_reviews):
		mock_create_reviews.return_value = {
			"created_count": 1,
			"created": [{"match_record": "RE-BTM-TEST", "reason": "Created"}],
		}
		row = {
			"candidate_key": "BTN-2|Payment Entry|PE-2|Payment Entry Match|",
			"bank_transaction": "BTN-2",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "PE-2",
			"candidate_category": "Payment Entry Match",
		}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([row]),
			enqueue=0,
		)

		summary = process_bank_match_batch_job(result["batch_job"])
		self.assertEqual(summary["created_count"], 1)
		mock_create_reviews.assert_called_once()

		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		self.assertEqual(job.rows[0].result_status, "Created")
		self.assertEqual(job.rows[0].review_record, "RE-BTM-TEST")
		frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)


	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Payment Entry",
				"document_name": "ACC-PAY-2026-00012",
				"suggested_document": "ACC-PAY-2026-00012",
				"suggested_sales_invoice": "ACC-SINV-2026-00026",
				"customer": "Walk-in Customer",
				"party": "Walk-in Customer",
				"party_type": "Customer",
				"candidate_amount": 1090,
				"score": 90,
				"confidence": "Strong Match",
				"candidate_category": "payment_entry_match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"reasons": ["Selected locked candidate from report row."],
			},
			{
				"document_type": "Payment Entry",
				"document_name": "ACC-PAY-2026-00008",
				"suggested_document": "ACC-PAY-2026-00008",
				"suggested_sales_invoice": "ACC-SINV-2026-00026",
				"customer": "Walk-in Customer",
				"party": "Walk-in Customer",
				"party_type": "Customer",
				"candidate_amount": 1090,
				"score": 92,
				"confidence": "Strong Match",
				"candidate_category": "payment_entry_match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"reasons": ["Current best candidate from backend search."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_match_workflow.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-2026-00007",
			"company": "Process Edge (Demo)",
			"branch": "Airport Branch",
			"bank_account": "Moniepoint - moniepoint",
			"transaction_date": "2026-05-24",
			"amount": 1090,
			"reference": "TRF-1090",
			"description": "Selected row should stay locked",
		},
	)
	def test_background_create_review_preserves_selected_report_row_candidate(
		self,
		_mock_normalize,
		_mock_payment_candidates,
		_mock_sales_candidates,
		_mock_sales_confirmed,
		_mock_payment_confirmed,
		_mock_manage,
		_mock_access,
	):
		selected_row = {
			"candidate_key": "ACC-BTN-2026-00007|Payment Entry|ACC-PAY-2026-00012|Payment Entry Match|",
			"bank_transaction": "ACC-BTN-2026-00007",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-2026-00012",
			"payment_entry": "ACC-PAY-2026-00012",
			"suggested_sales_invoice": "ACC-SINV-2026-00026",
			"candidate_category": "Payment Entry Match",
			"payment_event_found": 1,
			"payment_event_source": "Payment Entry",
			"candidate_amount": 1090,
			"match_score": 90,
			"match_confidence": "Strong Match",
			"amount_scenario": "Exact Amount",
		}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([selected_row]),
			enqueue=0,
		)
		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		fake_doc = _FakeMatchDoc(
			doctype="RetailEdge Bank Transaction Match",
			decision_status=None,
			action_logs=[],
			synced_to_sales_invoice=0,
		)

		def fake_get_doc(payload, *args, **kwargs):
			if isinstance(payload, dict) and payload.get("doctype") == "RetailEdge Bank Transaction Match":
				return fake_doc
			if payload == "RetailEdge Bank Transaction Match" and args and args[0] == fake_doc.name:
				return fake_doc
			raise AssertionError(f"Unexpected get_doc payload during batch review creation: {payload!r}, {args!r}")

		try:
			with patch("retailedge.bank_transaction_match_workflow.frappe.get_doc", side_effect=fake_get_doc), patch(
				"retailedge.bank_transaction_match_workflow.now_datetime", return_value="2026-06-12 10:00:00"
			), patch("retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True), patch(
				"retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None
			):
				_process_job_row(job, job.rows[0])

			self.assertEqual(job.rows[0].candidate_key, selected_row["candidate_key"])
			self.assertEqual(json.loads(job.rows[0].input_payload_json)["suggested_document"], "ACC-PAY-2026-00012")
			self.assertEqual(fake_doc.suggested_document_type, "Payment Entry")
			self.assertEqual(fake_doc.suggested_document, "ACC-PAY-2026-00012")
			self.assertEqual(fake_doc.payment_entry, "ACC-PAY-2026-00012")
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)


	@patch("retailedge.bank_transaction_match_workflow.assert_can_access_bank_transaction_matching")
	@patch("retailedge.bank_transaction_match_workflow.assert_can_manage_bank_transaction_match")
	@patch("retailedge.bank_transaction_match_workflow.payment_entry_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.sales_invoice_has_active_confirmed_bank_match", return_value=False)
	@patch("retailedge.bank_transaction_match_workflow.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_match_workflow.find_payment_entry_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Payment Entry",
				"document_name": "ACC-PAY-2026-00008",
				"suggested_document": "ACC-PAY-2026-00008",
				"suggested_sales_invoice": "ACC-SINV-2026-00026",
				"customer": "Walk-in Customer",
				"party": "Walk-in Customer",
				"party_type": "Customer",
				"candidate_amount": 1090,
				"score": 92,
				"confidence": "Strong Match",
				"candidate_category": "payment_entry_match",
				"payment_event_found": 1,
				"payment_event_source": "Payment Entry",
				"reasons": ["Current best candidate from backend search."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_match_workflow.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-2026-00007",
			"company": "Process Edge (Demo)",
			"branch": "Airport Branch",
			"bank_account": "Moniepoint - moniepoint",
			"transaction_date": "2026-05-24",
			"amount": 1090,
			"reference": "TRF-1090",
			"description": "Selected row should stay locked",
		},
	)
	def test_background_create_review_missing_locked_candidate_does_not_create_alternate_review(
		self,
		_mock_normalize,
		_mock_payment_candidates,
		_mock_sales_candidates,
		_mock_sales_confirmed,
		_mock_payment_confirmed,
		_mock_manage,
		_mock_access,
	):
		selected_row = {
			"candidate_key": "ACC-BTN-2026-00007|Payment Entry|ACC-PAY-2026-00012|Payment Entry Match|",
			"bank_transaction": "ACC-BTN-2026-00007",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-2026-00012",
			"payment_entry": "ACC-PAY-2026-00012",
			"suggested_sales_invoice": "ACC-SINV-2026-00026",
			"candidate_category": "Payment Entry Match",
			"payment_event_found": 1,
			"payment_event_source": "Payment Entry",
			"candidate_amount": 1090,
			"match_score": 90,
			"match_confidence": "Strong Match",
			"amount_scenario": "Exact Amount",
		}
		result = create_bank_match_batch_job(
			action_type="Create Review Records",
			rows=json.dumps([selected_row]),
			enqueue=0,
		)
		job = frappe.get_doc("RetailEdge Bank Match Batch Job", result["batch_job"])
		created_docs = []

		def fake_get_doc(payload, *args, **kwargs):
			if isinstance(payload, dict) and payload.get("doctype") == "RetailEdge Bank Transaction Match":
				created_docs.append(payload)
				return _FakeMatchDoc(doctype="RetailEdge Bank Transaction Match", decision_status=None, action_logs=[])
			raise AssertionError(f"Unexpected get_doc payload during missing locked candidate test: {payload!r}, {args!r}")

		try:
			with patch("retailedge.bank_transaction_match_workflow.frappe.get_doc", side_effect=fake_get_doc), patch(
				"retailedge.bank_transaction_match_workflow.frappe.db.exists", return_value=True
			), patch("retailedge.bank_transaction_match_workflow.frappe.db.get_value", return_value=None):
				_process_job_row(job, job.rows[0])

			self.assertEqual(job.rows[0].result_status, "Failed")
			self.assertIn("Locked candidate was not found", job.rows[0].result_message)
			self.assertEqual(created_docs, [])
		finally:
			frappe.delete_doc("RetailEdge Bank Match Batch Job", job.name, force=True)


if __name__ == "__main__":
	unittest.main()
