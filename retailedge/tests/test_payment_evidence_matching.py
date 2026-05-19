from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retailedge.payment_evidence_matching import (
	_match_against_bank_transactions,
	get_payment_evidence_match_list,
	get_payment_evidence_match_summary,
	match_payment_evidence_for_invoice,
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

	@patch("retailedge.payment_evidence_matching.get_payment_evidence_matching_settings")
	@patch("retailedge.payment_evidence_matching.get_payment_entries_for_sales_invoice")
	@patch("retailedge.payment_evidence_matching.get_sales_invoice_payment_rows")
	@patch("retailedge.payment_evidence_matching.audit_sales_invoice_payment")
	@patch("retailedge.payment_evidence_matching.frappe.get_doc")
	def test_match_payment_evidence_for_invoice_returns_structured_result(
		self,
		mock_get_doc,
		mock_invoice_audit,
		mock_payment_rows,
		mock_payment_entries,
		mock_settings,
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
		mock_payment_rows.return_value = [{"payment_category": "Cash", "amount": 1000.0, "base_amount": 1000.0, "account": "Cash - PED"}]
		mock_payment_entries.return_value = [
			{
				"payment_entry": "PAY-0001",
				"posting_date": "2026-05-18",
				"party": "Customer A",
				"paid_amount": 1000.0,
				"received_amount": 1000.0,
				"paid_to": "Cash - PED",
				"mode_of_payment": "Cash",
				"reference_allocated_amount": 1000.0,
			}
		]
		mock_settings.return_value = {
			"match_against_payment_entries": 1,
			"match_against_bank_transactions": 0,
			"match_against_manual_evidence": 0,
			"payment_evidence_amount_tolerance": 0,
			"payment_evidence_date_window_days": 3,
			"require_reference_for_strong_match": 0,
		}
		with patch("retailedge.payment_evidence_matching.get_expected_payment_account_for_invoice", return_value={"account": "Cash - PED"}):
			result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertEqual(result["invoice"], "SINV-0001")
		self.assertTrue(result["matches"])
		self.assertEqual(result["matches"][0]["match_status"], "Strong Candidate")

	@patch("retailedge.payment_evidence_matching.get_payment_evidence_matching_settings")
	@patch("retailedge.payment_evidence_matching.get_payment_entries_for_sales_invoice")
	@patch("retailedge.payment_evidence_matching.get_sales_invoice_payment_rows")
	@patch("retailedge.payment_evidence_matching.audit_sales_invoice_payment")
	@patch("retailedge.payment_evidence_matching.frappe.get_doc")
	def test_amount_mismatch_lowers_match_confidence(
		self,
		mock_get_doc,
		mock_invoice_audit,
		mock_payment_rows,
		mock_payment_entries,
		mock_settings,
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
		mock_payment_rows.return_value = [{"payment_category": "Cash", "amount": 1000.0, "base_amount": 1000.0, "account": "Cash - PED"}]
		mock_payment_entries.return_value = [
			{
				"payment_entry": "PAY-0001",
				"posting_date": "2026-05-18",
				"party": "Customer A",
				"paid_amount": 900.0,
				"received_amount": 900.0,
				"paid_to": "Cash - PED",
				"mode_of_payment": "Cash",
				"reference_allocated_amount": 900.0,
			}
		]
		mock_settings.return_value = {
			"match_against_payment_entries": 1,
			"match_against_bank_transactions": 0,
			"match_against_manual_evidence": 0,
			"payment_evidence_amount_tolerance": 0,
			"payment_evidence_date_window_days": 3,
			"require_reference_for_strong_match": 0,
		}
		with patch("retailedge.payment_evidence_matching.get_expected_payment_account_for_invoice", return_value={"account": "Cash - PED"}):
			result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertIn(result["matches"][0]["match_confidence"], {"Medium", "Low"})
		self.assertFalse(result["matches"][0]["amount_match"])

	@patch("retailedge.payment_evidence_matching.has_doctype", return_value=True)
	@patch("retailedge.payment_evidence_matching.has_field", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_cash_rows_are_excluded_from_bank_statement_matching(self, mock_get_all, _mock_has_field, _mock_has_doctype):
		rows = _match_against_bank_transactions(
			self._invoice(),
			{"company": "Process Edge (Demo)", "posting_date": "2026-05-18"},
			[{"payment_category": "Cash", "base_amount": 1000.0, "account": "Cash - PED"}],
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
				"party": "Customer A",
				"party_type": "Customer",
				"amount": 1000.0,
				"account": "Bank - PED",
				"payment_entry": None,
				"sales_invoice": "SINV-0001",
				"evidence_status": "Unmatched",
			}
		]
		with patch("retailedge.payment_evidence_matching.get_expected_payment_account_for_invoice", return_value={"account": "Bank - PED"}):
			result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertEqual(result["matches"][0]["evidence_type"], "RetailEdge Payment Evidence")
		self.assertEqual(result["matches"][0]["match_status"], "Strong Candidate")

	@patch("retailedge.payment_evidence_matching.get_payment_evidence_matching_settings")
	@patch("retailedge.payment_evidence_matching.get_payment_entries_for_sales_invoice")
	@patch("retailedge.payment_evidence_matching.get_sales_invoice_payment_rows")
	@patch("retailedge.payment_evidence_matching.audit_sales_invoice_payment")
	@patch("retailedge.payment_evidence_matching.frappe.get_doc")
	@patch("retailedge.payment_evidence_matching.has_doctype", side_effect=lambda doctype: doctype == "RetailEdge Statement Import Row")
	@patch("retailedge.payment_evidence_matching.has_field", return_value=True)
	@patch("retailedge.payment_evidence_matching.frappe.get_all")
	def test_statement_import_row_can_match_non_cash_invoice(
		self,
		mock_get_all,
		_mock_has_field,
		_mock_has_doctype,
		mock_get_doc,
		mock_invoice_audit,
		mock_payment_rows,
		mock_payment_entries,
		mock_settings,
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
				"narration": "Customer A transfer SINV-0001",
				"party": "Customer A",
				"amount": 1000.0,
				"account": "Bank - PED",
				"payment_entry": None,
				"sales_invoice": "SINV-0001",
				"match_status": "Pending",
			}
		]
		with patch("retailedge.payment_evidence_matching.get_expected_payment_account_for_invoice", return_value={"account": "Bank - PED"}):
			result = match_payment_evidence_for_invoice("SINV-0001")
		self.assertEqual(result["matches"][0]["evidence_type"], "Statement Import Row")
		self.assertEqual(result["matches"][0]["match_status"], "Strong Candidate")

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
						"payment_category": "Cash",
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
						"payment_category": "Cash",
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
					}
				],
				"unmatched_payments": [],
			},
		]
		rows = get_payment_evidence_match_list({"company": "Process Edge (Demo)"}, limit=20)
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
				"payment_category": "Cash",
				"payment_amount": 1000.0,
				"evidence_type": "Payment Entry",
				"evidence_document": "PAY-0001",
				"evidence_amount": 1000.0,
				"amount_difference": 0.0,
				"reference_match": 1,
				"amount_match": 1,
				"date_match": 1,
				"account_match": 1,
				"party_match": 1,
				"match_score": 100,
				"match_confidence": "High",
				"match_status": "Strong Candidate",
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
