from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.bank_transaction_matching import (
	candidate_document_has_active_confirmed_bank_match,
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	get_auto_match_status_for_row,
	get_amount_scenario_label,
	get_bank_transaction_field_map,
	get_bank_transaction_matching_rows,
	get_bank_transaction_matching_settings,
	normalize_bank_transaction,
	payment_entry_has_active_confirmed_bank_match,
	sales_invoice_has_active_confirmed_bank_match,
	score_bank_transaction_candidate,
	suppress_duplicate_candidate_suggestions,
	_apply_exception_classification,
	_build_payment_entry_candidate,
	_build_sales_invoice_candidates,
	_resolve_account_match_payload,
	_select_candidate_for_queue,
	_get_bank_transaction_rows,
)
from retailedge.retailedge.report.retailedge_bank_transaction_matching.retailedge_bank_transaction_matching import (
	DEFAULT_RESULT_LIMIT,
	MAX_RESULT_LIMIT,
	build_suggested_match_label,
	execute as execute_bank_transaction_matching_report,
	get_columns,
	normalize_result_limit,
)


class BankTransactionMatchingTests(unittest.TestCase):
	REPORT_JS_PATH = "/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_bank_transaction_matching/retailedge_bank_transaction_matching.js"

	def _field(self, fieldname, fieldtype="Data"):
		return SimpleNamespace(fieldname=fieldname, fieldtype=fieldtype)

	def _bank_transaction(self, **overrides):
		row = {
			"name": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"date": "2026-05-23",
			"deposit": 10000.0,
			"withdrawal": 0.0,
			"reference_number": "TRF123",
			"description": "Customer transfer INV-0001",
			"status": "Pending",
			"allocated_amount": 0.0,
			"unallocated_amount": 10000.0,
			"retailedge_branch": "Airport Branch",
		}
		row.update(overrides)
		return row

	@patch("retailedge.bank_transaction_matching.frappe.get_meta")
	def test_bank_transaction_schema_helper_works(self, mock_get_meta):
		mock_get_meta.return_value = SimpleNamespace(
			fields=[
				self._field("bank_account", "Link"),
				self._field("date", "Date"),
				self._field("deposit", "Currency"),
			]
		)
		field_map = get_bank_transaction_field_map()
		self.assertEqual(field_map["bank_account"], "bank_account")
		self.assertEqual(field_map["transaction_date"], "date")
		self.assertEqual(field_map["deposit"], "deposit")

	@patch("retailedge.bank_transaction_matching.get_retailedge_settings", return_value=None)
	def test_auto_match_settings_default_to_safe_disabled_mode(self, _mock_settings):
		settings = get_bank_transaction_matching_settings()
		self.assertEqual(settings["enable_bank_auto_match"], 0)
		self.assertEqual(settings["auto_prepare_exact_bank_matches"], 0)
		self.assertEqual(settings["auto_confirm_exact_bank_matches"], 0)
		self.assertEqual(settings["minimum_auto_match_score"], 95)
		self.assertEqual(settings["require_exact_reference_for_auto_match"], 1)
		self.assertEqual(settings["require_same_bank_account_for_auto_match"], 1)
		self.assertEqual(settings["allow_auto_match_payment_entry"], 1)
		self.assertEqual(settings["allow_auto_match_sales_invoice"], 0)

	@patch("retailedge.bank_transaction_matching.get_retailedge_settings")
	def test_minimum_auto_match_score_is_read_from_settings(self, mock_settings):
		mock_settings.return_value = SimpleNamespace(
			enable_bank_auto_match=1,
			auto_prepare_exact_bank_matches=1,
			auto_confirm_exact_bank_matches=0,
			minimum_auto_match_score=65,
			require_exact_reference_for_auto_match=1,
			require_same_bank_account_for_auto_match=1,
			require_same_branch_for_auto_match=1,
			allow_auto_match_payment_entry=1,
			allow_auto_match_sales_invoice=1,
			require_no_duplicate_candidate_for_auto_match=1,
			require_no_active_review_for_auto_match=1,
		)
		settings = get_bank_transaction_matching_settings()
		self.assertEqual(settings["minimum_auto_match_score"], 65)

	def test_score_below_auto_match_threshold_is_blocked(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 64,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 65,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Blocked from Auto-Match")
		self.assertIn("Score below auto-match threshold", status["reason"])
		self.assertIn("Match Score: 64", status["reason"])
		self.assertIn("Required Minimum: 65", status["reason"])

	def test_score_equal_to_auto_match_threshold_passes_score_gate(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 65,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 65,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Eligible for Auto-Prepare")

	def test_auto_match_disabled_blocks_even_exact_candidate(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 99,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
		}
		settings = {
			"enable_bank_auto_match": 0,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 65,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Blocked from Auto-Match")
		self.assertIn("disabled in Settings", status["reason"])

	def test_weak_reference_blocks_only_when_exact_reference_is_required(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 99,
			"amount_difference": 0,
			"reference_match_exact": 0,
			"account_match_available": 1,
			"account_match": 1,
		}
		strict_settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 65,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		loose_settings = dict(strict_settings, require_exact_reference_for_auto_match=0)
		strict_status = get_auto_match_status_for_row(row, settings=strict_settings)
		loose_status = get_auto_match_status_for_row(row, settings=loose_settings)
		self.assertEqual(strict_status["status"], "Blocked from Auto-Match")
		self.assertEqual(loose_status["status"], "Eligible for Auto-Prepare")

	def test_ratio_style_score_is_normalized_before_threshold_comparison(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 0.9,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 65,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Eligible for Auto-Prepare")

	def test_exact_sales_invoice_match_can_be_eligible_for_auto_prepare(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Sales Invoice",
			"suggested_document": "SINV-0001",
			"amount_scenario": "Exact Invoice Payment Row Amount",
			"candidate_category": "Invoice Payment Row Match",
			"match_confidence": "Strong Match",
			"match_score": 98,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
			"branch_match_available": 1,
			"branch_match": 1,
			"match_record": "",
			"decision_status": "",
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 1,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Eligible for Auto-Prepare")
		self.assertTrue(status["eligible_prepare"])
		self.assertFalse(status["eligible_confirm"])

	def test_auto_confirm_requires_explicit_setting(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 99,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 1,
			"branch_match_available": 0,
			"branch_match": 0,
			"match_record": "",
			"decision_status": "",
			"payment_entry_invoice_context": "SINV-0001",
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Eligible for Auto-Prepare")
		self.assertFalse(status["eligible_confirm"])

	def test_partial_payment_is_blocked_from_auto_match(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Sales Invoice",
			"suggested_document": "SINV-0001",
			"amount_scenario": "Partial Payment",
			"candidate_category": "Invoice Context Only",
			"match_confidence": "Possible Match",
			"match_score": 76,
			"amount_difference": 100,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 1,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Needs Manual Review")
		self.assertIn("Partial Payment", status["reason"])

	def test_account_mismatch_blocks_auto_match_when_required(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 99,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 1,
			"account_match": 0,
			"branch_match_available": 0,
			"branch_match": 0,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Blocked from Auto-Match")
		self.assertIn("Bank account mismatch", status["reason"])

	@patch("retailedge.bank_transaction_matching.frappe.db.exists", return_value=False)
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.frappe.db.get_value", return_value="Demo Bank Account - PED")
	def test_account_mapping_match_uses_canonical_ledger_account(self, mock_get_value, _mock_has_field, mock_has_doctype, _mock_exists):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Bank Account", "Account"}
		payload = _resolve_account_match_payload(
			{"bank_account": "Moniepoint - moniepoint"},
			{"account": "Demo Bank Account - PED", "payment_account": "Demo Bank Account - PED"},
		)
		self.assertEqual(payload["status"], "match_via_mapping")
		self.assertTrue(payload["matched"])
		self.assertEqual(payload["bank_canonical_account"], "Demo Bank Account - PED")
		mock_get_value.assert_called_once_with("Bank Account", "Moniepoint - moniepoint", "account")

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.frappe.db.get_value", return_value=None)
	@patch("retailedge.bank_transaction_matching.frappe.db.exists", return_value=False)
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype")
	def test_mode_of_payment_mapping_resolves_bank_transaction_account(self, mock_has_doctype, _mock_has_field, _mock_exists, _mock_get_value, mock_get_all):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Bank Account", "Account", "Mode of Payment Account"}
		mock_get_all.return_value = [{"default_account": "Demo Bank Account - PED"}]
		payload = _resolve_account_match_payload(
			{"bank_account": "Moniepoint - moniepoint", "company": "Process Edge (Demo)"},
			{"account": "Demo Bank Account - PED", "payment_account": "Demo Bank Account - PED"},
		)
		self.assertEqual(payload["status"], "match_via_mapping")
		self.assertTrue(payload["matched"])
		self.assertEqual(payload["bank_canonical_account"], "Demo Bank Account - PED")
		mock_get_all.assert_called()

	@patch("retailedge.bank_transaction_matching.frappe.db.exists", return_value=False)
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.frappe.db.get_value", return_value="Demo Bank Account - PED")
	def test_account_mapping_removes_false_account_mismatch_exception(self, _mock_get_value, _mock_has_field, mock_has_doctype, _mock_exists):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Bank Account", "Account"}
		candidate = {
			"document_type": "Payment Entry",
			"posting_date": "2026-05-21",
			"account": "Demo Bank Account - PED",
			"payment_account": "Demo Bank Account - PED",
		}
		result = _apply_exception_classification(
			{"transaction_date": "2026-05-20", "bank_account": "Moniepoint - moniepoint"},
			candidate,
			{},
			{"date_window_days": 3},
		)
		self.assertEqual(result["account_resolution_status"], "match_via_mapping")
		self.assertNotIn("exception_type", result)

	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=False)
	def test_unresolved_account_is_not_classified_as_mismatch(self, _mock_has_doctype):
		candidate = {
			"document_type": "Payment Entry",
			"posting_date": "2026-05-21",
			"account": "",
			"payment_account": "",
		}
		result = _apply_exception_classification(
			{"transaction_date": "2026-05-20", "bank_account": "Moniepoint - moniepoint"},
			candidate,
			{},
			{"date_window_days": 3},
		)
		self.assertEqual(result["exception_type"], "Account Unresolved")
		self.assertIn("Could not resolve bank/payment account mapping", result["reason"])

	def test_auto_match_requires_resolved_account_when_same_account_gate_enabled(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Payment Entry",
			"suggested_document": "ACC-PAY-0001",
			"amount_scenario": "Submitted Payment Entry Amount",
			"candidate_category": "Payment Entry Match",
			"match_confidence": "Strong Match",
			"match_score": 99,
			"amount_difference": 0,
			"reference_match_exact": 1,
			"account_match_available": 0,
			"account_match": 0,
			"account_resolution_status": "unresolved",
			"branch_match_available": 0,
			"branch_match": 0,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 1,
			"minimum_auto_match_score": 95,
			"require_exact_reference_for_auto_match": 1,
			"require_same_bank_account_for_auto_match": 1,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 0,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Blocked from Auto-Match")
		self.assertIn("Could not resolve bank/payment account mapping", status["reason"])

	def test_weak_invoice_total_similarity_is_not_auto_match_eligible(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"suggested_document_type": "Sales Invoice",
			"suggested_document": "SINV-0002",
			"amount_scenario": "Exact Invoice Amount",
			"candidate_category": "Weak Invoice Total Similarity",
			"match_confidence": "Weak Match",
			"match_score": 45,
			"amount_difference": 0,
		}
		settings = {
			"enable_bank_auto_match": 1,
			"auto_prepare_exact_bank_matches": 1,
			"auto_confirm_exact_bank_matches": 0,
			"minimum_auto_match_score": 40,
			"require_exact_reference_for_auto_match": 0,
			"require_same_bank_account_for_auto_match": 0,
			"require_same_branch_for_auto_match": 0,
			"allow_auto_match_payment_entry": 1,
			"allow_auto_match_sales_invoice": 1,
			"require_no_duplicate_candidate_for_auto_match": 1,
			"require_no_active_review_for_auto_match": 1,
		}
		status = get_auto_match_status_for_row(row, settings=settings)
		self.assertEqual(status["status"], "Needs Manual Review")
		self.assertIn("payment entry or invoice payment row evidence", status["reason"].lower())

	def test_report_columns_include_auto_match_visibility(self):
		fieldnames = [column.get("fieldname") for column in get_columns()]
		self.assertIn("auto_match_status", fieldnames)
		self.assertIn("auto_match_reason", fieldnames)


	def test_bank_matching_report_refreshes_after_actions_and_clears_selections(self):
		with open(self.REPORT_JS_PATH, encoding="utf-8") as handle:
			script = handle.read()
		self.assertIn("refreshOperationalReportView(report);", script)
		self.assertIn("clear_checked_items", script)
		self.assertIn("configureOperationalReportRefresh(report);", script)
		self.assertIn("forceOperationalPrimaryAction(report);", script)
		self.assertIn("Refresh Report", script)

	def test_operational_reports_force_ignore_prepared_report(self):
		with open(self.REPORT_JS_PATH, encoding="utf-8") as handle:
			script = handle.read()
		self.assertIn("report.ignore_prepared_report = true;", script)
		self.assertIn("report.prepared_report = false;", script)

	def test_retailedge_reports_disable_prepared_report_mode_for_normal_use(self):
		report_paths = [
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_bank_transaction_matching/retailedge_bank_transaction_matching.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_unmatched_bank_transactions/retailedge_unmatched_bank_transactions.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_unmatched_bank_payment_events/retailedge_unmatched_bank_payment_events.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_bank_match_reconciliation_readiness/retailedge_bank_match_reconciliation_readiness.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_branch_performance_summary/retailedge_branch_performance_summary.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_invoice_payment_audit/retailedge_invoice_payment_audit.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_cashier_expense_review/retailedge_cashier_expense_review.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_cash_shift_verification/retailedge_cash_shift_verification.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_daily_sales_audit_register/retailedge_daily_sales_audit_register.json",
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/pos_closing_variance_vs_expenses/pos_closing_variance_vs_expenses.json",
		]
		for report_path in report_paths:
			with self.subTest(report_path=report_path):
				with open(report_path, encoding="utf-8") as handle:
					report_json = json.load(handle)
				self.assertEqual(report_json.get("disable_prepared_report"), 1)

	def test_retailedge_settings_json_includes_bank_auto_match_guidance(self):
		import json
		from pathlib import Path

		path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/doctype/retailedge_settings/retailedge_settings.json"
		)
		data = json.loads(path.read_text())
		fields = {row.get("fieldname"): row for row in data.get("fields", [])}
		self.assertIn("bank_auto_match_mode", fields)
		self.assertIn("bank_auto_match_guidance", fields)
		self.assertIn("does not reconcile Bank Transactions", fields["enable_bank_auto_match"].get("description", ""))
		self.assertIn("does not create Payment Entries", fields["auto_confirm_exact_bank_matches"].get("description", ""))
		self.assertIn("does not mark the invoice paid", fields["allow_auto_match_sales_invoice"].get("description", ""))

	def test_queue_prefers_exact_invoice_payment_row_over_weaker_payment_entry_variance(self):
		candidates = [
			{
				"document_type": "Payment Entry",
				"document_name": "ACC-PAY-2026-00007",
				"candidate_category": "payment_entry_match",
				"amount_scenario": "Payment Entry Amount Variance",
				"match_confidence": "Possible Match",
				"score": 50,
				"amount_difference": 49190.0,
			},
			{
				"document_type": "Sales Invoice",
				"document_name": "ACC-SINV-2026-00023",
				"candidate_category": "invoice_payment_row_match",
				"amount_scenario": "Exact Invoice Payment Row Amount",
				"match_confidence": "Possible Match",
				"score": 70,
				"amount_difference": 0.0,
			},
		]
		best_candidate, selected_match = _select_candidate_for_queue(candidates, [], {})
		self.assertEqual(best_candidate["document_type"], "Sales Invoice")
		self.assertEqual(best_candidate["document_name"], "ACC-SINV-2026-00023")
		self.assertIsNone(selected_match)

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	def test_invoice_payment_row_match_is_classified_as_payment_event(self, mock_get_doc, _mock_defaults):
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"mode_of_payment": "POS",
						"account": "Demo Bank Account - PED",
						"amount": 1000,
						"base_amount": 1000,
					}
				)
			]
		)
		bank_transaction = {**self._bank_transaction(deposit=1000, bank_account="Demo Bank Account - PED"), "amount": 1000}
		invoice = {
			"name": "ACC-SINV-0001",
			"posting_date": "2026-05-23",
			"company": "Process Edge (Demo)",
			"customer": "CUST-0001",
			"customer_name": "ABC Stores",
			"grand_total": 1000,
			"outstanding_amount": 0,
			"pos_profile": "Main POS",
		}
		candidates = _build_sales_invoice_candidates(bank_transaction, invoice, {}, {"amount_tolerance": 0})
		self.assertEqual(candidates[0]["candidate_category"], "pos_payment_match")
		self.assertEqual(candidates[0]["payment_event_found"], 1)
		self.assertEqual(candidates[0]["payment_event_source"], "POS Payment Row")
		self.assertEqual(candidates[0]["payment_row_amount"], 1000)
		self.assertEqual(candidates[0]["payment_row_index"], 1)

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	def test_cash_payment_row_is_excluded_from_bank_matching_candidates(self, mock_get_doc, _mock_defaults):
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 1,
						"mode_of_payment": "Cash",
						"account": "Cash - PED",
						"amount": 1000,
						"base_amount": 1000,
					}
				)
			]
		)
		bank_transaction = {**self._bank_transaction(deposit=1000, bank_account="Demo Bank Account - PED"), "amount": 1000}
		invoice = {
			"name": "ACC-SINV-CASH",
			"posting_date": "2026-05-23",
			"company": "Process Edge (Demo)",
			"customer": "CUST-CASH",
			"customer_name": "Cash Customer",
			"grand_total": 1000,
			"outstanding_amount": 0,
			"pos_profile": "Main POS",
		}
		candidates = _build_sales_invoice_candidates(bank_transaction, invoice, {}, {"amount_tolerance": 0})
		self.assertEqual(candidates, [])

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	def test_mixed_cash_and_moniepoint_rows_keep_only_bank_matchable_row(self, mock_get_doc, _mock_defaults):
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 1,
						"mode_of_payment": "Cash",
						"account": "Cash - PED",
						"amount": 500,
						"base_amount": 500,
					}
				),
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 2,
						"mode_of_payment": "Moniepoint",
						"account": "Moniepoint - moniepoint",
						"amount": 810,
						"base_amount": 810,
					}
				),
			]
		)
		bank_transaction = {**self._bank_transaction(deposit=810, bank_account="Moniepoint - moniepoint"), "amount": 810}
		invoice = {
			"name": "ACC-SINV-MIXED",
			"posting_date": "2026-05-23",
			"company": "Process Edge (Demo)",
			"customer": "CUST-MIXED",
			"customer_name": "Mixed Customer",
			"grand_total": 1310,
			"outstanding_amount": 0,
			"pos_profile": "Main POS",
		}
		candidates = _build_sales_invoice_candidates(bank_transaction, invoice, {}, {"amount_tolerance": 0})
		self.assertEqual(len(candidates), 1)
		self.assertEqual(candidates[0]["candidate_amount"], 810)
		self.assertEqual(candidates[0]["payment_mode"], "Moniepoint")
		self.assertEqual(candidates[0]["payment_row_index"], 2)
		self.assertEqual(candidates[0]["candidate_category"], "invoice_payment_row_match")

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "POS Clearing - PED"})
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	def test_mixed_cash_and_pos_rows_keep_only_pos_row(self, mock_get_doc, _mock_defaults):
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 1,
						"mode_of_payment": "Cash",
						"account": "Cash - PED",
						"amount": 500,
						"base_amount": 500,
					}
				),
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 2,
						"mode_of_payment": "POS",
						"account": "POS Clearing - PED",
						"amount": 810,
						"base_amount": 810,
					}
				),
			]
		)
		bank_transaction = {**self._bank_transaction(deposit=810, bank_account="POS Clearing - PED"), "amount": 810}
		invoice = {
			"name": "ACC-SINV-POS",
			"posting_date": "2026-05-23",
			"company": "Process Edge (Demo)",
			"customer": "CUST-POS",
			"customer_name": "POS Customer",
			"grand_total": 1310,
			"outstanding_amount": 0,
			"pos_profile": "Main POS",
		}
		candidates = _build_sales_invoice_candidates(bank_transaction, invoice, {}, {"amount_tolerance": 0})
		self.assertEqual(len(candidates), 1)
		self.assertEqual(candidates[0]["candidate_amount"], 810)
		self.assertEqual(candidates[0]["candidate_category"], "pos_payment_match")
		self.assertEqual(candidates[0]["payment_row_index"], 2)

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	def test_mixed_cash_and_bank_transfer_rows_keep_only_bank_transfer_row(self, mock_get_doc, _mock_defaults):
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 1,
						"mode_of_payment": "Cash",
						"account": "Cash - PED",
						"amount": 500,
						"base_amount": 500,
					}
				),
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 2,
						"mode_of_payment": "Bank Transfer",
						"account": "Demo Bank Account - PED",
						"amount": 810,
						"base_amount": 810,
					}
				),
			]
		)
		bank_transaction = {**self._bank_transaction(deposit=810, bank_account="Demo Bank Account - PED"), "amount": 810}
		invoice = {
			"name": "ACC-SINV-BANK",
			"posting_date": "2026-05-23",
			"company": "Process Edge (Demo)",
			"customer": "CUST-BANK",
			"customer_name": "Bank Customer",
			"grand_total": 1310,
			"outstanding_amount": 0,
			"pos_profile": "Main POS",
		}
		candidates = _build_sales_invoice_candidates(bank_transaction, invoice, {}, {"amount_tolerance": 0})
		self.assertEqual(len(candidates), 1)
		self.assertEqual(candidates[0]["candidate_amount"], 810)
		self.assertEqual(candidates[0]["payment_mode"], "Bank Transfer")
		self.assertEqual(candidates[0]["payment_row_index"], 2)

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc", return_value=SimpleNamespace(payments=[]))
	def test_invoice_total_only_match_is_excluded_from_bank_matching_candidates(self, _mock_doc, _mock_defaults):
		bank_transaction = {**self._bank_transaction(deposit=1000), "amount": 1000}
		invoice = {
			"name": "ACC-SINV-0002",
			"posting_date": "2026-05-23",
			"company": "Process Edge (Demo)",
			"customer": "CUST-0002",
			"customer_name": "West View",
			"grand_total": 1000,
			"outstanding_amount": 0,
			"paid_amount": 1000,
		}
		candidates = _build_sales_invoice_candidates(bank_transaction, invoice, {}, {"amount_tolerance": 0})
		self.assertEqual(candidates, [])

	def test_payment_entry_match_carries_payment_basis_context(self):
		candidate = _build_payment_entry_candidate(
			self._bank_transaction(deposit=900),
			{
				"name": "ACC-PAY-0001",
				"posting_date": "2026-05-23",
				"party": "ABC Stores",
				"party_type": "Customer",
				"paid_to": "Demo Bank Account - PED",
				"paid_amount": 900,
				"received_amount": 900,
				"mode_of_payment": "Bank Transfer",
			},
			[{"reference_name": "ACC-SINV-0005", "allocated_amount": 900}],
		)
		self.assertEqual(candidate["candidate_category"], "payment_entry_match")
		self.assertEqual(candidate["payment_event_source"], "Payment Entry")
		self.assertEqual(candidate["payment_mode"], "Bank Transfer")

	@patch(
		"retailedge.bank_transaction_matching.get_bank_transaction_field_map",
		return_value={
			"bank_account": "bank_account",
			"company": "company",
			"transaction_date": "date",
			"deposit": "deposit",
			"withdrawal": "withdrawal",
			"reference_number": "reference_number",
			"description": "description",
			"status": "status",
			"allocated_amount": "allocated_amount",
			"unallocated_amount": "unallocated_amount",
			"retailedge_branch": "retailedge_branch",
		},
	)
	def test_bank_transaction_normalization_handles_deposit_inflow(self, _mock_map):
		normalized = normalize_bank_transaction(self._bank_transaction())
		self.assertEqual(normalized["direction"], "Inflow")
		self.assertEqual(normalized["amount"], 10000.0)
		self.assertEqual(normalized["normalized_reference"], "TRF123")

	@patch(
		"retailedge.bank_transaction_matching.get_bank_transaction_field_map",
		return_value={
			"bank_account": "bank_account",
			"company": "company",
			"transaction_date": "date",
			"deposit": "deposit",
			"withdrawal": "withdrawal",
			"reference_number": "reference_number",
			"description": "description",
			"status": "status",
			"allocated_amount": "allocated_amount",
			"unallocated_amount": "unallocated_amount",
			"retailedge_branch": "retailedge_branch",
		},
	)
	def test_bank_transaction_normalization_handles_withdrawal_outflow(self, _mock_map):
		normalized = normalize_bank_transaction(self._bank_transaction(deposit=0.0, withdrawal=4500.0))
		self.assertEqual(normalized["direction"], "Outflow")
		self.assertEqual(normalized["amount"], 4500.0)

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer SINV-0001",
			"branch": "Airport Branch",
		},
	)
	def test_sales_invoice_candidate_search_skips_outstanding_only_invoice_without_payment_event(
		self,
		_mock_normalize,
		_mock_doctype,
		mock_has_field,
		mock_get_all,
		_mock_defaults,
	):
		mock_has_field.return_value = True
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "CUST-001",
				"customer_name": "Customer A",
				"grand_total": 10000.0,
				"outstanding_amount": 10000.0,
				"paid_amount": 0.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			}
		]
		candidates = find_sales_invoice_candidates_for_bank_transaction("ACC-BTN-0001")
		self.assertEqual(candidates, [])

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 6000.0,
			"direction": "Inflow",
			"reference": "SINV-0001",
			"normalized_reference": "SINV0001",
			"description": "Partial transfer SINV-0001 Customer A",
			"branch": "Airport Branch",
		},
	)
	def test_sales_invoice_partial_payment_without_payment_event_is_excluded_from_candidates(
		self,
		_mock_normalize,
		_mock_doctype,
		_mock_has_field,
		mock_get_all,
		_mock_defaults,
	):
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "Customer A",
				"customer_name": "Customer A",
				"grand_total": 20000.0,
				"outstanding_amount": 10000.0,
				"paid_amount": 10000.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			}
		]
		candidates = find_sales_invoice_candidates_for_bank_transaction("ACC-BTN-0001")
		self.assertEqual(candidates, [])

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 12000.0,
			"direction": "Inflow",
			"reference": "SINV-0001",
			"normalized_reference": "SINV0001",
			"description": "Transfer SINV-0001 Customer A",
			"branch": "Airport Branch",
		},
	)
	def test_sales_invoice_overpayment_without_payment_event_is_excluded_from_candidates(
		self,
		_mock_normalize,
		_mock_doctype,
		_mock_has_field,
		mock_get_all,
		_mock_defaults,
	):
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "Customer A",
				"customer_name": "Customer A",
				"grand_total": 20000.0,
				"outstanding_amount": 10000.0,
				"paid_amount": 10000.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			}
		]
		candidates = find_sales_invoice_candidates_for_bank_transaction("ACC-BTN-0001")
		self.assertEqual(candidates, [])

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "",
			"normalized_reference": "",
			"description": "Bulk payment Customer A",
			"branch": "Airport Branch",
		},
	)
	def test_possible_multi_invoice_payment_without_payment_events_is_excluded_from_candidates(
		self,
		_mock_normalize,
		_mock_doctype,
		_mock_has_field,
		mock_get_all,
		_mock_defaults,
	):
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-22",
				"company": "Process Edge (Demo)",
				"customer": "Customer A",
				"customer_name": "Customer A",
				"grand_total": 6000.0,
				"outstanding_amount": 6000.0,
				"paid_amount": 0.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			},
			{
				"name": "SINV-0002",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "Customer A",
				"customer_name": "Customer A",
				"grand_total": 4000.0,
				"outstanding_amount": 4000.0,
				"paid_amount": 0.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			},
		]
		candidates = find_sales_invoice_candidates_for_bank_transaction("ACC-BTN-0001")
		self.assertEqual(candidates, [])

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
		},
	)
	def test_already_bank_verified_invoices_are_excluded_by_default(self, _mock_normalize, _mock_doctype, mock_has_field, mock_get_all):
		mock_has_field.return_value = True
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "CUST-001",
				"customer_name": "Customer A",
				"grand_total": 10000.0,
				"outstanding_amount": 10000.0,
				"paid_amount": 0.0,
				"retailedge_payment_verification_status": "Bank Verified",
			}
		]
		self.assertEqual(find_sales_invoice_candidates_for_bank_transaction("ACC-BTN-0001"), [])

	def test_strong_match_is_scored_correctly(self):
		bank_transaction = {
			"amount": 10000.0,
			"transaction_date": "2026-05-23",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer A paid SINV0001",
			"direction": "Inflow",
			"bank_account": "Moniepoint - moniepoint",
			"branch": "Airport Branch",
		}
		candidate = {
			"document_type": "Sales Invoice",
			"document_name": "SINV-0001",
			"suggested_sales_invoice": "SINV-0001",
			"posting_date": "2026-05-23",
			"customer": "Customer A",
			"candidate_amount": 10000.0,
			"amount_difference": 0.0,
			"reference": "TRF123",
			"expected_bank_account": "Demo Bank Account - PED",
			"branch": "Airport Branch",
			"supports_partial_match": True,
			"payment_verification_status": "Unverified",
		}
		score = score_bank_transaction_candidate(bank_transaction, candidate)
		self.assertGreaterEqual(score["score"], 80)
		self.assertEqual(score["confidence"], "Strong Match")

	def test_possible_match_is_scored_correctly_with_weaker_reference(self):
		bank_transaction = {
			"amount": 10000.0,
			"transaction_date": "2026-05-23",
			"reference": "",
			"normalized_reference": "",
			"description": "Customer A transfer",
			"direction": "Inflow",
			"bank_account": "Moniepoint - moniepoint",
			"branch": "Airport Branch",
		}
		candidate = {
			"document_type": "Sales Invoice",
			"document_name": "SINV-0001",
			"suggested_sales_invoice": "SINV-0001",
			"posting_date": "2026-05-24",
			"customer": "Customer A",
			"candidate_amount": 10000.0,
			"amount_difference": 0.0,
			"reference": "SINV-0001",
			"expected_bank_account": "Moniepoint - moniepoint",
			"branch": "Airport Branch",
			"supports_partial_match": True,
			"payment_verification_status": "Unverified",
		}
		score = score_bank_transaction_candidate(bank_transaction, candidate)
		self.assertGreaterEqual(score["score"], 50)
		self.assertLess(score["score"], 80)
		self.assertEqual(score["confidence"], "Possible Match")

	def test_no_match_is_returned_when_amount_and_date_do_not_align(self):
		bank_transaction = {
			"amount": 10000.0,
			"transaction_date": "2026-05-23",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Transfer",
			"direction": "Inflow",
			"bank_account": "Moniepoint - moniepoint",
		}
		candidate = {
			"document_type": "Sales Invoice",
			"document_name": "SINV-0009",
			"suggested_sales_invoice": "SINV-0009",
			"posting_date": "2026-04-01",
			"customer": "Customer Z",
			"candidate_amount": 4500.0,
			"amount_difference": 5500.0,
			"reference": "SINV-0009",
			"supports_partial_match": False,
		}
		score = score_bank_transaction_candidate(bank_transaction, candidate)
		self.assertEqual(score["confidence"], "No Match")

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "PE-TRF-001",
			"normalized_reference": "PETRF001",
			"description": "Payment Entry PE-0001",
			"branch": "Airport Branch",
		},
	)
	def test_payment_entry_candidate_search_works_where_payment_entry_reference_exists(
		self,
		_mock_normalize,
		mock_has_doctype,
		mock_has_field,
		mock_get_all,
	):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Payment Entry", "Payment Entry Reference"}
		mock_has_field.return_value = True
		mock_get_all.side_effect = [
			[
				{
					"name": "PE-0001",
					"posting_date": "2026-05-23",
					"company": "Process Edge (Demo)",
					"party": "Customer A",
					"party_type": "Customer",
					"paid_from": "Debtors - PED",
					"paid_to": "Demo Bank Account - PED",
					"paid_amount": 10000.0,
					"received_amount": 10000.0,
					"reference_no": "PE-TRF-001",
					"remarks": "Settlement",
					"retailedge_branch": "Airport Branch",
				}
			],
			[
				{
					"parent": "PE-0001",
					"reference_name": "SINV-0001",
					"allocated_amount": 10000.0,
				}
			],
		]
		candidates = find_payment_entry_candidates_for_bank_transaction("ACC-BTN-0001")
		self.assertEqual(candidates[0]["document_name"], "PE-0001")
		self.assertEqual(candidates[0]["suggested_sales_invoice"], "SINV-0001")
		self.assertEqual(candidates[0]["amount_scenario"], "Submitted Payment Entry Amount")
		self.assertEqual(candidates[0]["payment_entry_invoice_context"], "SINV-0001")

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Demo Bank Account - PED",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 9500.0,
			"direction": "Inflow",
			"reference": "PE-TRF-001",
			"normalized_reference": "PETRF001",
			"description": "Payment Entry PE-0001 variance",
			"branch": "Airport Branch",
		},
	)
	def test_payment_entry_amount_variance_requires_review(
		self,
		_mock_normalize,
		mock_has_doctype,
		_mock_has_field,
		mock_get_all,
	):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Payment Entry", "Payment Entry Reference"}
		mock_get_all.side_effect = [
			[
				{
					"name": "PE-0001",
					"posting_date": "2026-05-23",
					"company": "Process Edge (Demo)",
					"party": "Customer A",
					"party_type": "Customer",
					"paid_from": "Debtors - PED",
					"paid_to": "Demo Bank Account - PED",
					"paid_amount": 10000.0,
					"received_amount": 10000.0,
					"reference_no": "PE-TRF-001",
					"remarks": "Settlement",
					"retailedge_branch": "Airport Branch",
				}
			],
			[{"parent": "PE-0001", "reference_name": "SINV-0001", "allocated_amount": 10000.0}],
		]
		candidates = find_payment_entry_candidates_for_bank_transaction("ACC-BTN-0001")
		self.assertEqual(candidates[0]["amount_scenario"], "Payment Entry Amount Variance")
		self.assertNotEqual(candidates[0]["confidence"], "Strong Match")
		self.assertIn("Amount Variance requires manual review.", candidates[0]["reasons"])

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-2026-00002",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Different Demo Bank Account - PED",
			"transaction_date": "2025-05-19",
			"amount": 900.0,
			"direction": "Inflow",
			"reference": "3456tyt",
			"normalized_reference": "3456TYT",
			"description": "3456tyt",
			"branch": None,
		},
	)
	def test_payment_entry_date_and_account_exception_is_hidden_by_default(
		self,
		_mock_normalize,
		mock_has_doctype,
		_mock_has_field,
		mock_get_all,
	):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Payment Entry", "Payment Entry Reference"}
		mock_get_all.side_effect = [
			[],
			[],
		]
		candidates = find_payment_entry_candidates_for_bank_transaction("ACC-BTN-2026-00002")
		self.assertEqual(candidates, [])

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field", return_value=True)
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-2026-00002",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Different Demo Bank Account - PED",
			"transaction_date": "2025-05-19",
			"amount": 900.0,
			"direction": "Inflow",
			"reference": "3456tyt",
			"normalized_reference": "3456TYT",
			"description": "3456tyt",
			"branch": None,
		},
	)
	def test_payment_entry_date_and_account_exception_is_visible_when_requested(
		self,
		_mock_normalize,
		mock_has_doctype,
		_mock_has_field,
		mock_get_all,
	):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Payment Entry", "Payment Entry Reference"}
		mock_get_all.side_effect = [
			[
				{
					"name": "ACC-PAY-2026-00009",
					"posting_date": "2026-05-25",
					"company": "Process Edge (Demo)",
					"party": "Palmer Productions Ltd.",
					"party_type": "Customer",
					"paid_from": "Debtors - PED",
					"paid_to": "Demo Bank Account - PED",
					"paid_amount": 900.0,
					"received_amount": 900.0,
					"reference_no": "3456tyt",
					"remarks": "Amount against Sales Invoice ACC-SINV-2026-00027",
					"retailedge_branch": "HQ",
				}
			],
			[
				{
					"parent": "ACC-PAY-2026-00009",
					"reference_name": "ACC-SINV-2026-00027",
					"allocated_amount": 900.0,
				}
			],
		]
		candidates = find_payment_entry_candidates_for_bank_transaction(
			"ACC-BTN-2026-00002",
			filters={"include_exception_candidates": 1},
		)
		self.assertEqual(candidates[0]["document_name"], "ACC-PAY-2026-00009")
		self.assertEqual(candidates[0]["amount_scenario"], "Date + Account Mismatch")
		self.assertEqual(candidates[0]["amount_scenario_label"], "Date + Account Mismatch")
		self.assertEqual(candidates[0]["exception_only"], 1)
		self.assertIn("outside the normal matching window", candidates[0]["reason"])
		self.assertIn("Bank transaction resolved account differs from payment account", candidates[0]["reason"])

	def test_report_execution_uses_default_result_limit(self):
		self.assertEqual(normalize_result_limit({}), DEFAULT_RESULT_LIMIT)
		with patch(
			"retailedge.retailedge.report.retailedge_bank_transaction_matching.retailedge_bank_transaction_matching.get_bank_transaction_matching_rows",
			return_value=[],
		) as mock_rows:
			execute_bank_transaction_matching_report({})
		self.assertEqual(mock_rows.call_args.kwargs["limit"], DEFAULT_RESULT_LIMIT)

	def test_report_execution_clamps_excessive_result_limit(self):
		self.assertEqual(normalize_result_limit({"result_limit": 9999}), MAX_RESULT_LIMIT)
		with patch(
			"retailedge.retailedge.report.retailedge_bank_transaction_matching.retailedge_bank_transaction_matching.get_bank_transaction_matching_rows",
			return_value=[{"bank_transaction": f"BT-{idx}", "match_confidence": "Strong Match"} for idx in range(MAX_RESULT_LIMIT)],
		) as mock_rows:
			_columns, data, message, _chart, _summary = execute_bank_transaction_matching_report({"result_limit": 9999})
		self.assertEqual(mock_rows.call_args.kwargs["limit"], MAX_RESULT_LIMIT)
		self.assertEqual(len(data), MAX_RESULT_LIMIT)
		self.assertIn(str(MAX_RESULT_LIMIT), message)

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.get_bank_transaction_field_map")
	def test_bank_transaction_rows_apply_keyword_before_candidate_resolution(self, mock_field_map, mock_get_all):
		mock_field_map.return_value = {
			"bank_account": "bank_account",
			"company": "company",
			"transaction_date": "date",
			"deposit": "deposit",
			"withdrawal": "withdrawal",
			"description": "description",
			"reference_number": "reference_number",
			"transaction_id": "transaction_id",
			"party": "party",
			"status": "status",
		}
		mock_get_all.return_value = []
		_get_bank_transaction_rows(
			frappe._dict({"reference_search": "RE-LIVE-BATCH-TEST", "from_date": "2026-06-01", "to_date": "2026-06-16"}),
			limit=50,
		)
		kwargs = mock_get_all.call_args.kwargs
		self.assertEqual(kwargs["limit_page_length"], 50)
		self.assertIn(["reference_number", "like", "%RE-LIVE-BATCH-TEST%"], kwargs["or_filters"])
		self.assertIn(["description", "like", "%RE-LIVE-BATCH-TEST%"], kwargs["or_filters"])
		self.assertEqual(kwargs["filters"]["date"], ["between", ["2026-06-01", "2026-06-16"]])


	@patch("retailedge.retailedge.report.retailedge_bank_transaction_matching.retailedge_bank_transaction_matching.get_bank_transaction_matching_rows")
	def test_report_execute_works_with_filters_none(self, mock_rows):
		mock_rows.return_value = []
		columns, data, message, _, summary = execute_bank_transaction_matching_report(None)
		self.assertTrue(columns)
		self.assertEqual(data, [])
		self.assertIn("No matching bank transactions", message)
		self.assertTrue(summary)

	@patch("retailedge.retailedge.report.retailedge_bank_transaction_matching.retailedge_bank_transaction_matching.get_bank_transaction_matching_rows")
	def test_report_execute_works_with_company_date_filters(self, mock_rows):
		mock_rows.return_value = [
			{
				"bank_transaction": "ACC-BTN-0001",
				"transaction_date": "2026-05-23",
				"branch": "Airport Branch",
				"bank_account": "Moniepoint - moniepoint",
				"reference": "TRF123",
				"narration": "Customer transfer",
				"amount": 10000.0,
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"customer": "Customer A",
				"suggested_document_type": "Sales Invoice",
				"suggested_document": "SINV-0001",
				"suggested_sales_invoice": "SINV-0001",
				"match_confidence": "Strong Match",
				"match_score": 90,
				"match_reason": "Exact amount match.",
				"action_status": "Suggested",
			}
		]
		columns, data, _, _, summary = execute_bank_transaction_matching_report(
			{
				"company": "Process Edge (Demo)",
				"from_date": "2026-05-01",
				"to_date": "2026-05-31",
			}
		)
		self.assertTrue(columns)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["bank_transaction"], "ACC-BTN-0001")
		self.assertEqual(data[0]["suggested_match"], "SINV-0001 — Customer A")
		self.assertTrue(summary)

	def test_report_columns_put_decision_fields_first(self):
		labels = [column["label"] for column in get_columns()[:13]]
		self.assertEqual(
			labels,
			[
				"Date",
				"Branch",
				"Bank Amount",
				"SI/PE Amount",
				"Difference",
				"Action Status",
				"Exception Type",
				"Action",
				"Customer / Party",
				"Suggested Match",
				"Match Confidence",
				"Match Score",
				"Issue / Reason",
			],
		)

	def test_matching_row_exposes_action_fields_needed_by_report_js(self):
		row = {
			"bank_transaction": "ACC-BTN-0001",
			"amount": 10000.0,
			"suggested_document_type": "Sales Invoice",
			"suggested_document": "SINV-0001",
			"suggested_sales_invoice": "SINV-0001",
			"candidate_amount": 10000.0,
			"customer": "Customer A",
			"match_record": "RE-BTM-2026-0001",
			"decision_status": "Suggested",
			"match_confidence": "Strong Match",
			"match_score": 90,
			"action_status": "Suggested",
			"action": "Review",
		}
		for fieldname in (
			"bank_transaction",
			"amount",
			"suggested_document_type",
			"suggested_document",
			"suggested_sales_invoice",
			"candidate_amount",
			"customer",
			"match_record",
			"decision_status",
			"match_confidence",
			"match_score",
			"action_status",
			"action",
		):
			self.assertIn(fieldname, row)

	def test_report_js_exposes_create_review_records_button(self):
		from pathlib import Path

		path = Path(
			"/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/report/retailedge_bank_transaction_matching/retailedge_bank_transaction_matching.js"
		)
		source = path.read_text()
		self.assertIn("Create Review Records", source)
		self.assertIn("create_bank_match_reviews_from_suggestions", source)
		self.assertIn("This creates RetailEdge Bank Match Review records only", source)
		self.assertIn("duplicate_candidate_status", source)
		self.assertIn("already_reviewed_status", source)
		self.assertIn("include_exception_candidates", source)
		self.assertIn("Exception Only", source)

	def test_build_suggested_match_label_prefers_human_readable_text(self):
		self.assertEqual(
			build_suggested_match_label(
				{
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "ACC-SINV-2026-00012",
					"customer": "ABC Stores",
				}
			),
			"ACC-SINV-2026-00012 — ABC Stores",
		)
		self.assertIn(
			"Outstanding:",
			build_suggested_match_label(
				{
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "ACC-SINV-2026-00012",
					"customer": "ABC Stores",
					"sales_invoice_outstanding_amount": 25000,
					"sales_invoice_grand_total": 40000,
				}
			),
		)
		self.assertEqual(
			build_suggested_match_label(
				{
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-00045",
				}
			),
			"Payment Entry PE-00045",
		)
		self.assertIn(
			"Allocated:",
			build_suggested_match_label(
				{
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-00045",
					"customer": "ABC Stores",
					"payment_entry_paid_amount": 25000,
					"payment_entry_allocated_amount": 20000,
				}
			),
		)

	def test_amount_scenario_labels_are_friendly(self):
		self.assertEqual(get_amount_scenario_label("exact_outstanding_match"), "Exact Outstanding Match")
		self.assertEqual(get_amount_scenario_label("Partial Payment"), "Partial Payment")
		self.assertEqual(get_amount_scenario_label("payment_entry_allocated"), "Payment Entry with Invoice Allocation")
		self.assertEqual(get_amount_scenario_label("Date + Account Mismatch"), "Date + Account Mismatch")

	def test_duplicate_candidate_suppression_keeps_best_ranked_row(self):
		rows = suppress_duplicate_candidate_suggestions(
			[
				{
					"bank_transaction": "BT-LOW",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"amount_scenario": "Partial Payment",
					"match_confidence": "Possible Match",
					"match_score": 70,
					"amount_difference": 500,
				},
				{
					"bank_transaction": "BT-BEST",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"amount_scenario": "Exact Outstanding Amount",
					"match_confidence": "Strong Match",
					"match_score": 90,
					"amount_difference": 0,
				},
			]
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["bank_transaction"], "BT-BEST")

	def test_duplicate_candidate_marking_shows_winning_bank_transaction(self):
		rows = suppress_duplicate_candidate_suggestions(
			[
				{
					"bank_transaction": "BT-LOW",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"amount_scenario": "Partial Payment",
					"match_confidence": "Possible Match",
					"match_score": 70,
					"amount_difference": 500,
				},
				{
					"bank_transaction": "BT-BEST",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"amount_scenario": "Exact Outstanding Amount",
					"match_confidence": "Strong Match",
					"match_score": 90,
					"amount_difference": 0,
				},
			],
			mark_duplicates=True,
		)
		duplicate = [row for row in rows if row.get("action_status") == "Duplicate Candidate"][0]
		self.assertEqual(duplicate["duplicate_candidate_winner_bank_transaction"], "BT-BEST")
		self.assertIn("BT-BEST", duplicate["match_reason"])

	def test_duplicate_payment_entry_suppression_keeps_best_ranked_row(self):
		rows = suppress_duplicate_candidate_suggestions(
			[
				{
					"bank_transaction": "BT-LOW",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-0001",
					"amount_scenario": "Payment Entry Amount Variance",
					"match_confidence": "Possible Match",
					"match_score": 65,
					"amount_difference": 1000,
				},
				{
					"bank_transaction": "BT-BEST",
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-0001",
					"amount_scenario": "Submitted Payment Entry Amount",
					"match_confidence": "Strong Match",
					"match_score": 88,
					"amount_difference": 0,
				},
			]
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["bank_transaction"], "BT-BEST")

	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch("retailedge.bank_transaction_matching.frappe.db.exists")
	def test_confirmed_sales_invoice_helper_detects_only_active_confirmed_matches(self, mock_exists, _mock_doctype):
		mock_exists.side_effect = [True, False, False]
		self.assertTrue(sales_invoice_has_active_confirmed_bank_match("SINV-0001"))
		self.assertFalse(payment_entry_has_active_confirmed_bank_match("PE-0001"))
		self.assertFalse(candidate_document_has_active_confirmed_bank_match("Customer", "CUST-0001"))
		mock_exists.assert_any_call(
			"RetailEdge Bank Transaction Match",
			{"sales_invoice": "SINV-0001", "decision_status": "Confirmed"},
		)

	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch("retailedge.bank_transaction_matching.frappe.db.exists", return_value=False)
	def test_reopened_rejected_and_cancelled_matches_do_not_block_candidate_reuse(self, mock_exists, _mock_doctype):
		self.assertFalse(sales_invoice_has_active_confirmed_bank_match("SINV-REOPENED"))
		self.assertFalse(payment_entry_has_active_confirmed_bank_match("PE-CANCELLED"))
		for call_args in mock_exists.call_args_list:
			_doctype, filters = call_args.args
			self.assertEqual(filters["decision_status"], "Confirmed")

	@patch("retailedge.bank_transaction_matching.frappe.new_doc")
	@patch("retailedge.bank_transaction_matching.frappe.db.set_value")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching.get_bank_transaction_field_map", return_value={"transaction_date": "date"})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	def test_matching_rows_do_not_mutate_documents(
		self,
		mock_get_all,
		_mock_map,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_set_value,
		mock_new_doc,
	):
		mock_get_all.return_value = [self._bank_transaction()]
		rows = get_bank_transaction_matching_rows({"company": "Process Edge (Demo)"}, limit=20)
		self.assertEqual(rows, [])
		mock_new_doc.assert_not_called()
		mock_set_value.assert_not_called()

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction", return_value={})
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-EMPTY",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"transaction_date": "2026-05-23",
			"amount": 810.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "No payment event match",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_grid_excludes_transactions_without_bank_matchable_payment_candidates(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		_mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction(name="ACC-BTN-EMPTY")]
		rows = get_bank_transaction_matching_rows({"company": "Process Edge (Demo)"}, limit=20)
		self.assertEqual(rows, [])

	@patch("retailedge.bank_transaction_matching.sales_invoice_has_active_confirmed_bank_match", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching._active_review_match_for_candidate",
		return_value={"name": "RE-BTM-0001", "decision_status": "Confirmed"},
	)
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
		},
	)
	def test_confirmed_sales_invoice_candidate_is_excluded_by_default(
		self,
		_mock_normalize,
		_mock_doctype,
		mock_has_field,
		mock_get_all,
		_mock_defaults,
		mock_get_doc,
		_mock_active_review,
		_mock_confirmed,
	):
		mock_has_field.return_value = True
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 1,
						"mode_of_payment": "Bank Transfer",
						"account": "Demo Bank Account - PED",
						"amount": 10000.0,
						"base_amount": 10000.0,
					}
				)
			]
		)
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "CUST-001",
				"customer_name": "Customer A",
				"grand_total": 10000.0,
				"outstanding_amount": 10000.0,
				"paid_amount": 0.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			}
		]
		self.assertEqual(find_sales_invoice_candidates_for_bank_transaction("ACC-BTN-0001"), [])

	@patch("retailedge.bank_transaction_matching.sales_invoice_has_active_confirmed_bank_match", return_value=True)
	@patch("retailedge.bank_transaction_matching._get_sales_invoice_doc")
	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Demo Bank Account - PED"})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer SINV-0001",
			"branch": "Airport Branch",
		},
	)
	def test_confirmed_sales_invoice_candidate_can_show_for_audit_when_requested(
		self,
		_mock_normalize,
		_mock_doctype,
		mock_has_field,
		mock_get_all,
		_mock_defaults,
		mock_get_doc,
		_mock_confirmed,
	):
		mock_has_field.return_value = True
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				SimpleNamespace(
					as_dict=lambda: {
						"idx": 1,
						"mode_of_payment": "Bank Transfer",
						"account": "Demo Bank Account - PED",
						"amount": 10000.0,
						"base_amount": 10000.0,
					}
				)
			]
		)
		mock_get_all.return_value = [
			{
				"name": "SINV-0001",
				"posting_date": "2026-05-23",
				"company": "Process Edge (Demo)",
				"customer": "CUST-001",
				"customer_name": "Customer A",
				"grand_total": 10000.0,
				"outstanding_amount": 10000.0,
				"paid_amount": 0.0,
				"retailedge_branch": "Airport Branch",
				"retailedge_payment_verification_status": "Unverified",
			}
		]
		candidates = find_sales_invoice_candidates_for_bank_transaction(
			"ACC-BTN-0001",
			filters={"include_confirmed_matches": 1, "review_queue_status": "Confirmed"},
		)
		self.assertEqual(candidates[0]["action_status"], "Existing Active Review")
		self.assertEqual(candidates[0]["match_record"], "SINV-0001")

	@patch("retailedge.bank_transaction_matching.payment_entry_has_active_confirmed_bank_match", return_value=True)
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype")
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "PE-TRF-001",
			"normalized_reference": "PETRF001",
			"description": "Payment Entry PE-0001",
			"branch": "Airport Branch",
		},
	)
	def test_confirmed_payment_entry_candidate_is_excluded_by_default(
		self,
		_mock_normalize,
		mock_has_doctype,
		mock_has_field,
		mock_get_all,
		_mock_confirmed,
	):
		mock_has_doctype.side_effect = lambda doctype: doctype in {"Payment Entry", "Payment Entry Reference"}
		mock_has_field.return_value = True
		mock_get_all.side_effect = [
			[
				{
					"name": "PE-0001",
					"posting_date": "2026-05-23",
					"company": "Process Edge (Demo)",
					"party": "Customer A",
					"party_type": "Customer",
					"paid_from": "Debtors - PED",
					"paid_to": "Moniepoint - moniepoint",
					"paid_amount": 10000.0,
					"received_amount": 10000.0,
					"reference_no": "PE-TRF-001",
					"remarks": "Settlement",
					"retailedge_branch": "Airport Branch",
				}
			],
			[],
		]
		self.assertEqual(find_payment_entry_candidates_for_bank_transaction("ACC-BTN-0001"), [])

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch("retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_report_hides_confirmed_matches_by_default(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction()]
		mock_existing_matches.return_value = {
			"ACC-BTN-0001": [{"name": "RE-BTM-0001", "decision_status": "Confirmed", "bank_transaction": "ACC-BTN-0001"}]
		}
		self.assertEqual(get_bank_transaction_matching_rows({"company": "Process Edge (Demo)"}, limit=20), [])

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-REJECTED",
				"suggested_sales_invoice": "SINV-REJECTED",
				"customer_display": "Customer A",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Strong Match",
				"score": 95,
				"reasons": ["Exact amount match."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_rejected_exact_pair_can_show_in_rejected_queue(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction()]
		mock_existing_matches.return_value = {
			"ACC-BTN-0001": [
				{
					"name": "RE-BTM-0001",
					"decision_status": "Rejected",
					"bank_transaction": "ACC-BTN-0001",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-REJECTED",
					"sales_invoice": "SINV-REJECTED",
				}
			]
		}
		rows = get_bank_transaction_matching_rows(
			{"company": "Process Edge (Demo)", "review_queue_status": "Rejected"},
			limit=20,
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["action_status"], "Rejected")
		self.assertIn("Previously rejected match pair.", rows[0]["match_reason"])

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction", return_value={"ACC-BTN-0001": [{"name": "RE-BTM-0001", "decision_status": "Rejected", "bank_transaction": "ACC-BTN-0001", "suggested_document_type": "Payment Entry", "suggested_document": "PE-0001", "payment_entry": "PE-0001"}]})
	@patch(
		"retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Payment Entry",
				"document_name": "PE-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer_display": "Customer A",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Strong Match",
				"score": 95,
				"reasons": ["Exact amount match."],
			}
		],
	)
	@patch("retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0002",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-24",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF456",
			"normalized_reference": "TRF456",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_same_candidate_can_match_different_bank_transaction_after_other_pair_rejected(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		_mock_existing_matches,
	):
		mock_bank_transactions.return_value = [{"name": "ACC-BTN-0002"}]
		rows = get_bank_transaction_matching_rows({"company": "Process Edge (Demo)"}, limit=20)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["bank_transaction"], "ACC-BTN-0002")
		self.assertEqual(rows[0]["suggested_document"], "PE-0001")

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer_display": "Customer A",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Strong Match",
				"score": 95,
				"reasons": ["Exact amount match."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_report_shows_confirmed_matches_only_when_requested(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction()]
		mock_existing_matches.return_value = {
			"ACC-BTN-0001": [
				{
					"name": "RE-BTM-0001",
					"decision_status": "Confirmed",
					"bank_transaction": "ACC-BTN-0001",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"sales_invoice": "SINV-0001",
					"candidate_amount": 10000.0,
				}
			]
		}
		rows = get_bank_transaction_matching_rows(
			{"company": "Process Edge (Demo)", "include_confirmed_matches": 1, "review_queue_status": "Confirmed"},
			limit=20,
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["action_status"], "Already Confirmed")
		self.assertEqual(rows[0]["decision_status"], "Confirmed")

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-REJECTED",
				"suggested_sales_invoice": "SINV-REJECTED",
				"customer_display": "Customer A",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Strong Match",
				"score": 95,
				"reasons": ["Exact amount match."],
			},
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-ALTERNATIVE",
				"suggested_sales_invoice": "SINV-ALTERNATIVE",
				"customer_display": "Customer B",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Possible Match",
				"score": 80,
				"reasons": ["Alternative candidate."],
			},
		],
	)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_rejected_candidate_is_hidden_but_alternative_candidate_can_show(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction()]
		mock_existing_matches.return_value = {
			"ACC-BTN-0001": [
				{
					"name": "RE-BTM-0001",
					"decision_status": "Rejected",
					"bank_transaction": "ACC-BTN-0001",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-REJECTED",
					"sales_invoice": "SINV-REJECTED",
				}
			]
		}
		rows = get_bank_transaction_matching_rows({"company": "Process Edge (Demo)"}, limit=20)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["suggested_document"], "SINV-ALTERNATIVE")

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer_display": "Customer A",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Strong Match",
				"score": 95,
				"reasons": ["Exact amount match."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_active_review_candidates_are_hidden_by_default_queue(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction()]
		mock_existing_matches.return_value = {
			"ACC-BTN-0001": [
				{
					"name": "RE-BTM-0001",
					"decision_status": "Needs Review",
					"bank_transaction": "ACC-BTN-0001",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"sales_invoice": "SINV-0001",
				}
			]
		}
		rows = get_bank_transaction_matching_rows({"company": "Process Edge (Demo)"}, limit=20)
		self.assertEqual(rows, [])

	@patch("retailedge.bank_transaction_matching._get_existing_matches_by_bank_transaction")
	@patch("retailedge.bank_transaction_matching.find_payment_entry_candidates_for_bank_transaction", return_value=[])
	@patch(
		"retailedge.bank_transaction_matching.find_sales_invoice_candidates_for_bank_transaction",
		return_value=[
			{
				"document_type": "Sales Invoice",
				"document_name": "SINV-0001",
				"suggested_sales_invoice": "SINV-0001",
				"customer_display": "Customer A",
				"candidate_amount": 10000.0,
				"amount_difference": 0.0,
				"confidence": "Strong Match",
				"score": 95,
				"reasons": ["Exact amount match."],
			}
		],
	)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"ledger_account": "Demo Bank Account - PED",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer",
			"branch": "Airport Branch",
			"is_reconciled": False,
		},
	)
	@patch("retailedge.bank_transaction_matching._get_bank_transaction_rows")
	def test_active_review_candidates_show_only_in_already_in_review_mode(
		self,
		mock_bank_transactions,
		_mock_normalize,
		_mock_invoice_candidates,
		_mock_payment_candidates,
		mock_existing_matches,
	):
		mock_bank_transactions.return_value = [self._bank_transaction()]
		mock_existing_matches.return_value = {
			"ACC-BTN-0001": [
				{
					"name": "RE-BTM-0001",
					"decision_status": "Needs Review",
					"bank_transaction": "ACC-BTN-0001",
					"suggested_document_type": "Sales Invoice",
					"suggested_document": "SINV-0001",
					"sales_invoice": "SINV-0001",
				}
			]
		}
		rows = get_bank_transaction_matching_rows(
			{"company": "Process Edge (Demo)", "review_queue_status": "Already In Review"},
			limit=20,
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["match_record"], "RE-BTM-0001")
		self.assertEqual(rows[0]["decision_status"], "Needs Review")


class BankTransactionReferenceMatchingTests(unittest.TestCase):
	def test_exact_reference_match_sets_exact_flag(self):
		bank_transaction = {
			"amount": 1000,
			"reference": "TRF-12345",
			"normalized_reference": "trf12345",
			"description": "Payment received",
			"transaction_date": "2026-05-21",
			"direction": "Inflow",
		}
		candidate = {
			"document_type": "Payment Entry",
			"document_name": "ACC-PAY-0001",
			"candidate_amount": 1000,
			"posting_date": "2026-05-21",
			"reference": "TRF12345",
			"candidate_category": "payment_entry_match",
			"amount_scenario": "Submitted Payment Entry Amount",
			"reason": "Matched submitted Payment Entry.",
		}
		with patch("retailedge.bank_transaction_matching.get_bank_transaction_matching_settings", return_value={"amount_tolerance": 0, "strong_match_score": 80, "minimum_possible_score": 50, "date_window_days": 3}):
			payload = score_bank_transaction_candidate(bank_transaction, candidate)
		self.assertEqual(payload["reference_match_exact"], 1)
		self.assertEqual(payload["reference_match_strength"], "exact")

	def test_reference_contains_match_is_strong_but_not_exact(self):
		bank_transaction = {
			"amount": 1000,
			"reference": "MONIEPOINT",
			"normalized_reference": "moniepoint",
			"description": "Settlement REF 34567 from West View",
			"transaction_date": "2026-05-21",
			"direction": "Inflow",
		}
		candidate = {
			"document_type": "Payment Entry",
			"document_name": "ACC-PAY-0008",
			"candidate_amount": 1000,
			"posting_date": "2026-05-21",
			"reference": "34567",
			"candidate_category": "payment_entry_match",
			"amount_scenario": "Submitted Payment Entry Amount",
			"reason": "Matched submitted Payment Entry.",
		}
		with patch("retailedge.bank_transaction_matching.get_bank_transaction_matching_settings", return_value={"amount_tolerance": 0, "strong_match_score": 80, "minimum_possible_score": 50, "date_window_days": 3}):
			payload = score_bank_transaction_candidate(bank_transaction, candidate)
		self.assertEqual(payload["reference_match_exact"], 0)
		self.assertEqual(payload["reference_match_strength"], "contains")

	def test_customer_name_only_is_weak_support(self):
		bank_transaction = {
			"amount": 1000,
			"reference": "MONIEPOINT",
			"normalized_reference": "moniepoint",
			"description": "Settlement from West View Software Ltd",
			"transaction_date": "2026-05-21",
			"direction": "Inflow",
		}
		candidate = {
			"document_type": "Payment Entry",
			"document_name": "ACC-PAY-0008",
			"candidate_amount": 1000,
			"posting_date": "2026-05-21",
			"reference": "",
			"customer": "West View Software Ltd",
			"candidate_category": "payment_entry_match",
			"amount_scenario": "Submitted Payment Entry Amount",
			"reason": "Matched submitted Payment Entry.",
		}
		with patch("retailedge.bank_transaction_matching.get_bank_transaction_matching_settings", return_value={"amount_tolerance": 0, "strong_match_score": 80, "minimum_possible_score": 50, "date_window_days": 3}):
			payload = score_bank_transaction_candidate(bank_transaction, candidate)
		self.assertEqual(payload["reference_match_exact"], 0)
		self.assertEqual(payload["reference_match_strength"], "weak")
