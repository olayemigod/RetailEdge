from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe

from retailedge.payment_evidence_matching import (
	_match_against_bank_transactions,
	build_evidence_fingerprint,
	detect_duplicate_evidence,
	get_payment_evidence_match_list,
	get_payment_evidence_match_summary,
	invoice_has_active_payment_evidence_match,
	match_payment_evidence_for_invoice,
	normalize_payment_reference,
	normalize_statement_row,
)
from retailedge.retailedge.report.retailedge_payment_evidence_matching.retailedge_payment_evidence_matching import (
	execute as execute_payment_evidence_matching_report,
)


class PaymentEvidenceMatchingTests(unittest.TestCase):
	def _invoice(self, **kwargs):
		defaults = dict(
			doctype="Sales Invoice",
			name="SINV-0001",
			company="Process Edge (Demo)",
			customer="Customer A",
			posting_date="2026-05-18",
			grand_total=1000.0,
			rounded_total=1000.0,
			paid_amount=1000.0,
			outstanding_amount=0.0,
			docstatus=1,
			status="Paid",
			is_pos=1,
			retailedge_branch="HQ",
			branch=None,
			pos_profile="Testing",
			owner="cashier@example.com",
		)
		defaults.update(kwargs)
		return SimpleNamespace(**defaults)

	def test_reference_normalization_handles_case_spacing_and_separators(self):
		self.assertEqual(normalize_payment_reference("TRF-123 456")["normalized_reference"], "TRF123456")
		self.assertEqual(normalize_payment_reference(" trf/123/456 ")["normalized_reference"], "TRF123456")
		self.assertEqual(normalize_payment_reference("POS_0099.88")["normalized_reference"], "POS009988")

	def test_reference_normalization_can_fall_back_to_narration(self):
		result = normalize_payment_reference("", "Bank transfer TRF-555-999")
		self.assertEqual(result["source"], "narration")
		self.assertIn("TRF555999", result["normalized_reference"])

	def test_same_basis_creates_same_fingerprint(self):
		first = build_evidence_fingerprint(
			company="Process Edge (Demo)",
			account="Bank - PED",
			transaction_date="2026-05-19",
			amount=50000,
			reference="TRF-123 456",
			payment_category="Bank Transfer",
		)
		second = build_evidence_fingerprint(
			company="Process Edge (Demo)",
			account="Bank - PED",
			transaction_date="2026-05-19",
			amount=50000.0,
			reference=" trf/123/456 ",
			payment_category="Bank Transfer",
		)
		self.assertEqual(first["fingerprint"], second["fingerprint"])

	@patch("retailedge.payment_evidence_matching.has_doctype", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_exact_previously_imported_fingerprint_is_rejected_duplicate(self, mock_get_all, _mock_has_doctype):
		mock_get_all.return_value = [
			{
				"name": "RE-PEV-0001",
				"company": "Process Edge (Demo)",
				"account": "Bank - PED",
				"evidence_date": "2026-05-19",
				"amount": 50000,
				"evidence_reference": "TRF-123 456",
				"narration": "Transfer",
				"payment_category": "Bank Transfer",
				"normalized_reference": "TRF123456",
				"evidence_fingerprint": build_evidence_fingerprint(
					company="Process Edge (Demo)",
					account="Bank - PED",
					transaction_date="2026-05-19",
					amount=50000,
					reference="TRF-123 456",
					payment_category="Bank Transfer",
				)["fingerprint"],
			}
		]
		result = detect_duplicate_evidence(
			company="Process Edge (Demo)",
			account="Bank - PED",
			transaction_date="2026-05-19",
			amount=50000,
			reference=" trf/123/456 ",
			payment_category="Bank Transfer",
		)
		self.assertEqual(result["duplicate_status"], "Rejected Duplicate")

	@patch("retailedge.payment_evidence_matching.has_doctype", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_partial_duplicate_is_flagged(self, mock_get_all, _mock_has_doctype):
		mock_get_all.return_value = [
			{
				"name": "ROW-0001",
				"company": "Process Edge (Demo)",
				"account": "Bank - PED",
				"transaction_date": "2026-05-20",
				"amount": 50000,
				"reference": "TRF-123 456",
				"narration": "Transfer",
				"payment_category": "Bank Transfer",
				"normalized_reference": "TRF123456",
				"evidence_fingerprint": "other",
			}
		]
		result = detect_duplicate_evidence(
			company="Process Edge (Demo)",
			account="Bank - PED",
			transaction_date="2026-05-19",
			amount=50000,
			reference="TRF123456",
			payment_category="Bank Transfer",
		)
		self.assertEqual(result["duplicate_status"], "Duplicate Suspected")

	@patch("retailedge.payment_evidence_matching.get_active_payment_evidence_match")
	@patch("retailedge.payment_evidence_matching.get_payment_evidence_matching_settings")
	def test_already_actively_matched_invoice_is_excluded_by_default(self, mock_settings, mock_active):
		mock_active.return_value = {"name": "RE-PEM-0001", "match_status": "Strong Candidate"}
		mock_settings.return_value = {
			"match_against_payment_entries": 0,
			"match_against_bank_transactions": 0,
			"match_against_statement_import_rows": 0,
			"match_against_manual_evidence": 0,
			"payment_evidence_amount_tolerance": 0,
			"payment_evidence_date_window_days": 3,
			"require_reference_for_strong_match": 0,
		}
		result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertIn("already has an active evidence match", result["messages"][0])

	@patch("retailedge.payment_evidence_matching.has_doctype", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_inactive_match_allows_invoice_to_appear_again(self, mock_get_all, _mock_has_doctype):
		mock_get_all.return_value = []
		self.assertFalse(invoice_has_active_payment_evidence_match("SINV-0001"))

	@patch("retailedge.payment_evidence_matching.user_has_any_role", return_value=False)
	@patch("retailedge.payment_evidence_matching.get_active_payment_evidence_match")
	def test_force_rematch_requires_manager_role(self, mock_active, mock_roles):
		mock_active.return_value = {"name": "RE-PEM-0001", "match_status": "Strong Candidate"}
		with self.assertRaises(frappe.PermissionError):
			match_payment_evidence_for_invoice("SINV-0001", force_rematch=True)

	def test_normalize_statement_row_handles_separate_debit_credit_columns(self):
		row = {
			"Tran Date": "2026-05-19",
			"Narration": "POS settlement",
			"Ref": "POS-001",
			"Credit": 1500,
			"Debit": 0,
		}
		template = {
			"company": "Process Edge (Demo)",
			"statement_type": "Card / POS Settlement",
			"payment_category": "Card / POS",
			"date_column": "Tran Date",
			"reference_column": "Ref",
			"narration_column": "Narration",
			"credit_column": "Credit",
			"debit_column": "Debit",
			"debit_credit_mode": "Separate Debit/Credit Columns",
		}
		result = normalize_statement_row(row, template)
		self.assertEqual(result["amount"], 1500)
		self.assertEqual(result["direction"], "Credit")

	def test_normalize_statement_row_handles_signed_amount_column(self):
		row = {"Date": "2026-05-19", "Description": "Transfer", "Amount": -250}
		template = {
			"company": "Process Edge (Demo)",
			"statement_type": "Bank Transfer",
			"payment_category": "Bank Transfer",
			"date_column": "Date",
			"narration_column": "Description",
			"amount_column": "Amount",
			"debit_credit_mode": "Signed Amount Column",
		}
		result = normalize_statement_row(row, template)
		self.assertEqual(result["amount"], 250)
		self.assertEqual(result["direction"], "Debit")

	def test_normalize_statement_row_handles_credit_only_amount_column(self):
		row = {"Date": "2026-05-19", "Amount": 300}
		template = {
			"company": "Process Edge (Demo)",
			"statement_type": "Mobile Money",
			"payment_category": "Mobile Money",
			"date_column": "Date",
			"amount_column": "Amount",
			"debit_credit_mode": "Credit Only Amount Column",
		}
		result = normalize_statement_row(row, template)
		self.assertEqual(result["direction"], "Credit")
		self.assertEqual(result["amount"], 300)

	def test_missing_required_mapped_columns_returns_user_safe_error(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_statement_row(
				{"Description": "Transfer", "Amount": 200},
				{
					"company": "Process Edge (Demo)",
					"statement_type": "Bank Transfer",
					"payment_category": "Bank Transfer",
					"date_column": "Date",
					"amount_column": "Amount",
					"debit_credit_mode": "Signed Amount Column",
				},
			)

	@patch("retailedge.payment_evidence_matching.has_doctype", return_value=True)
	@patch("retailedge.payment_evidence_matching.has_field", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_cash_rows_are_excluded_from_bank_statement_matching(self, mock_get_all, _mock_has_field, _mock_has_doctype):
		rows = _match_against_bank_transactions(
			self._invoice(),
			{"company": "Process Edge (Demo)", "posting_date": "2026-05-18"},
			[{"payment_category": "Cash", "base_amount": 1000.0, "account": "Cash - PED"}],
			[],
			{"payment_evidence_date_window_days": 3, "payment_evidence_amount_tolerance": 0, "require_reference_for_strong_match": 0},
			[],
			{},
		)
		mock_get_all.assert_not_called()
		self.assertEqual(rows, [])

	@patch("retailedge.payment_evidence_matching.has_doctype", return_value=False)
	@patch("retailedge.payment_evidence_matching.match_payment_evidence_for_invoice")
	def test_bank_transaction_absence_does_not_crash(self, mock_match, _mock_has_doctype):
		mock_match.return_value = {
			"invoice": "SINV-0001",
			"company": "Process Edge (Demo)",
			"branch": "HQ",
			"customer": "Customer A",
			"posting_date": "2026-05-18",
			"matches": [],
			"unmatched_payments": [{"payment_category": "Cash", "payment_amount": 1000.0}],
		}
		rows = get_payment_evidence_match_list({"company": "Process Edge (Demo)"}, limit=20)
		self.assertEqual(rows[0]["match_status"], "No Match")

	@patch("retailedge.payment_evidence_matching.get_active_payment_evidence_match", return_value=None)
	@patch("retailedge.payment_evidence_matching.get_payment_evidence_matching_settings")
	@patch("retailedge.payment_evidence_matching.get_payment_entries_for_sales_invoice")
	@patch("retailedge.payment_evidence_matching.get_sales_invoice_payment_rows")
	@patch("retailedge.payment_evidence_matching.audit_sales_invoice_payment")
	@patch("retailedge.payment_evidence_matching.frappe.get_doc")
	@patch("retailedge.payment_evidence_matching.has_doctype", side_effect=lambda doctype: doctype == "RetailEdge Payment Evidence")
	@patch("retailedge.payment_evidence_matching.has_field", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_manual_payment_evidence_can_match_linked_invoice(
		self,
		mock_get_all,
		_mock_has_field,
		_mock_has_doctype,
		mock_get_doc,
		mock_invoice_audit,
		mock_payment_rows,
		mock_payment_entries,
		mock_settings,
		_mock_active,
	):
		mock_get_doc.return_value = self._invoice()
		mock_invoice_audit.return_value = {
			"invoice": "SINV-0001",
			"company": "Process Edge (Demo)",
			"branch": "HQ",
			"customer": "Customer A",
			"posting_date": "2026-05-18",
			"grand_total": 1000.0,
			"paid_amount": 1000.0,
			"outstanding_amount": 0.0,
			"payment_audit_status": "Ready for Verification",
			"payment_risk_level": "Low",
			"messages": [],
		}
		mock_payment_rows.return_value = [{"payment_category": "Bank Transfer", "amount": 1000.0, "base_amount": 1000.0, "account": "Bank - PED"}]
		mock_payment_entries.return_value = []
		mock_settings.return_value = {
			"match_against_payment_entries": 0,
			"match_against_bank_transactions": 0,
			"match_against_statement_import_rows": 0,
			"match_against_manual_evidence": 1,
			"payment_evidence_amount_tolerance": 0,
			"payment_evidence_date_window_days": 3,
			"require_reference_for_strong_match": 0,
		}
		mock_get_all.return_value = [
			{
				"name": "RE-PEV-2026-0001",
				"company": "Process Edge (Demo)",
				"branch": "HQ",
				"evidence_date": "2026-05-18",
				"payment_category": "Bank Transfer",
				"evidence_reference": "TRF-001",
				"normalized_reference": "TRF001",
				"party": "Customer A",
				"party_type": "Customer",
				"amount": 1000.0,
				"account": "Bank - PED",
				"payment_entry": None,
				"sales_invoice": "SINV-0001",
				"evidence_status": "Unmatched",
				"duplicate_status": "Unique",
				"duplicate_of": None,
				"duplicate_reason": "",
				"evidence_fingerprint": "fp-1",
			}
		]
		with patch("retailedge.payment_evidence_matching.get_expected_payment_account_for_invoice", return_value={"account": "Bank - PED"}):
			result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertEqual(result["matches"][0]["evidence_type"], "RetailEdge Payment Evidence")
		self.assertEqual(result["matches"][0]["match_status"], "Strong Candidate")

	@patch("retailedge.payment_evidence_matching.get_active_payment_evidence_match", return_value=None)
	@patch("retailedge.payment_evidence_matching.get_payment_evidence_matching_settings")
	@patch("retailedge.payment_evidence_matching.get_payment_entries_for_sales_invoice")
	@patch("retailedge.payment_evidence_matching.get_sales_invoice_payment_rows")
	@patch("retailedge.payment_evidence_matching.audit_sales_invoice_payment")
	@patch("retailedge.payment_evidence_matching.frappe.get_doc")
	@patch("retailedge.payment_evidence_matching.has_doctype", side_effect=lambda doctype: doctype == "RetailEdge Statement Import Row")
	@patch("retailedge.payment_evidence_matching.has_field", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_rejected_duplicate_statement_row_is_not_strong_candidate(
		self,
		mock_get_all,
		_mock_has_field,
		_mock_has_doctype,
		mock_get_doc,
		mock_invoice_audit,
		mock_payment_rows,
		mock_payment_entries,
		mock_settings,
		_mock_active,
	):
		mock_get_doc.return_value = self._invoice()
		mock_invoice_audit.return_value = {
			"invoice": "SINV-0001",
			"company": "Process Edge (Demo)",
			"branch": "HQ",
			"customer": "Customer A",
			"posting_date": "2026-05-18",
			"grand_total": 1000.0,
			"paid_amount": 1000.0,
			"outstanding_amount": 0.0,
			"payment_audit_status": "Ready for Verification",
			"payment_risk_level": "Low",
			"messages": [],
		}
		mock_payment_rows.return_value = [{"payment_category": "Bank Transfer", "amount": 1000.0, "base_amount": 1000.0, "account": "Bank - PED"}]
		mock_payment_entries.return_value = []
		mock_settings.return_value = {
			"match_against_payment_entries": 0,
			"match_against_statement_import_rows": 1,
			"match_against_bank_transactions": 0,
			"match_against_manual_evidence": 0,
			"payment_evidence_amount_tolerance": 0,
			"payment_evidence_date_window_days": 3,
			"require_reference_for_strong_match": 0,
		}
		mock_get_all.return_value = [
			{
				"name": "ROW-0001",
				"parent": "RE-PSI-2026-0001",
				"transaction_date": "2026-05-18",
				"payment_category": "Bank Transfer",
				"reference": "TRF-001",
				"normalized_reference": "TRF001",
				"narration": "Customer A transfer SINV-0001",
				"party": "Customer A",
				"amount": 1000.0,
				"account": "Bank - PED",
				"payment_entry": None,
				"sales_invoice": "SINV-0001",
				"match_status": "Pending",
				"duplicate_status": "Rejected Duplicate",
				"duplicate_of": "ROW-OLD",
				"duplicate_reason": "Earlier upload already exists.",
				"evidence_fingerprint": "fp-dup",
				"direction": "Credit",
				"mapping_template": "Template A",
			}
		]
		with patch("retailedge.payment_evidence_matching.get_expected_payment_account_for_invoice", return_value={"account": "Bank - PED"}):
			result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertEqual(result["matches"][0]["match_status"], "Duplicate Suspected")

	@patch("retailedge.payment_evidence_matching.match_payment_evidence_for_invoice")
	@patch("retailedge.payment_evidence_matching._get_candidate_invoices")
	def test_duplicate_reference_suspicion_is_detected(self, mock_invoices, mock_match):
		mock_invoices.return_value = [{"name": "SINV-0001"}, {"name": "SINV-0002"}]
		mock_match.side_effect = [
			{
				"invoice": "SINV-0001",
				"posting_date": "2026-05-18",
				"company": "Process Edge (Demo)",
				"branch": "HQ",
				"customer": "Customer A",
				"matches": [
					{
						"evidence_type": "Payment Entry",
						"evidence_name": "PAY-0001",
						"payment_category": "Bank Transfer",
						"payment_amount": 1000.0,
						"evidence_amount": 1000.0,
						"amount_difference": 0.0,
						"reference_match": True,
						"amount_match": True,
						"date_match": True,
						"account_match": True,
						"party_match": True,
						"match_score": 100,
						"match_confidence": "High",
						"match_status": "Strong Candidate",
						"issue_summary": "",
						"reference": "PAY-0001",
						"evidence_date": "2026-05-18",
						"evidence_fingerprint": "fp-dup",
						"duplicate_status": "Unique",
					}
				],
				"unmatched_payments": [],
			},
			{
				"invoice": "SINV-0002",
				"posting_date": "2026-05-18",
				"company": "Process Edge (Demo)",
				"branch": "HQ",
				"customer": "Customer B",
				"matches": [
					{
						"evidence_type": "Payment Entry",
						"evidence_name": "PAY-0001",
						"payment_category": "Bank Transfer",
						"payment_amount": 1000.0,
						"evidence_amount": 1000.0,
						"amount_difference": 0.0,
						"reference_match": True,
						"amount_match": True,
						"date_match": True,
						"account_match": True,
						"party_match": True,
						"match_score": 100,
						"match_confidence": "High",
						"match_status": "Strong Candidate",
						"issue_summary": "",
						"reference": "PAY-0001",
						"evidence_date": "2026-05-18",
						"evidence_fingerprint": "fp-dup",
						"duplicate_status": "Unique",
					}
				],
				"unmatched_payments": [],
			},
		]
		rows = get_payment_evidence_match_list({"company": "Process Edge (Demo)", "include_already_matched": 1}, limit=20)
		self.assertEqual(rows[0]["match_status"], "Duplicate Suspected")
		self.assertEqual(rows[1]["match_status"], "Duplicate Suspected")

	@patch("retailedge.payment_evidence_matching.get_payment_evidence_match_list")
	def test_payment_evidence_match_summary_counts_rows(self, mock_list):
		mock_list.return_value = [
			{"sales_invoice": "SINV-0001", "match_status": "Strong Candidate", "match_confidence": "High", "evidence_type": "Payment Entry"},
			{"sales_invoice": "SINV-0002", "match_status": "Duplicate Suspected", "match_confidence": "Medium", "evidence_type": "RetailEdge Payment Evidence"},
			{"sales_invoice": "SINV-0003", "match_status": "No Match", "match_confidence": "Low", "evidence_type": None},
		]
		summary = get_payment_evidence_match_summary({"company": "Process Edge (Demo)"})
		self.assertEqual(summary["invoice_count"], 3)
		self.assertEqual(summary["matched_invoice_count"], 2)
		self.assertEqual(summary["duplicate_suspected_count"], 1)
		self.assertEqual(summary["manual_evidence_match_count"], 1)

	@patch("retailedge.retailedge.report.retailedge_payment_evidence_matching.retailedge_payment_evidence_matching.get_payment_evidence_match_summary")
	@patch("retailedge.retailedge.report.retailedge_payment_evidence_matching.retailedge_payment_evidence_matching.get_payment_evidence_match_list")
	def test_payment_evidence_matching_report_executes(self, mock_list, mock_summary):
		mock_list.return_value = [
			{
				"sales_invoice": "SINV-0001",
				"posting_date": "2026-05-18",
				"company": "Process Edge (Demo)",
				"branch": "HQ",
				"customer": "Customer A",
				"payment_category": "Bank Transfer",
				"payment_amount": 1000.0,
				"evidence_type": "Payment Entry",
				"evidence_document": "PAY-0001",
				"statement_import": None,
				"statement_import_row": None,
				"mapping_template": None,
				"evidence_amount": 1000.0,
				"amount_difference": 0.0,
				"normalized_reference": "PAY0001",
				"evidence_fingerprint": "fp-1",
				"reference_match": 1,
				"amount_match": 1,
				"date_match": 1,
				"account_match": 1,
				"party_match": 1,
				"match_score": 100,
				"match_confidence": "High",
				"match_status": "Strong Candidate",
				"duplicate_status": "Unique",
				"duplicate_of": None,
				"already_matched_invoice": 0,
				"issue_summary": "",
			}
		]
		mock_summary.return_value = {
			"invoice_count": 1,
			"matched_invoice_count": 1,
			"unmatched_invoice_count": 0,
			"duplicate_suspected_count": 0,
		}
		columns, data, _, _, summary = execute_payment_evidence_matching_report({"company": "Process Edge (Demo)"})
		self.assertTrue(columns)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["sales_invoice"], "SINV-0001")
		self.assertTrue(summary)
