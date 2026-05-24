from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.bank_transaction_matching import (
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	get_bank_transaction_field_map,
	get_bank_transaction_matching_rows,
	normalize_bank_transaction,
	score_bank_transaction_candidate,
)
from retailedge.retailedge.report.retailedge_bank_transaction_matching.retailedge_bank_transaction_matching import (
	build_suggested_match_label,
	execute as execute_bank_transaction_matching_report,
	get_columns,
)


class BankTransactionMatchingTests(unittest.TestCase):
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

	@patch("retailedge.bank_transaction_matching.get_branch_profile_defaults", return_value={"default_bank_account": "Moniepoint - moniepoint"})
	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
			"transaction_date": "2026-05-23",
			"amount": 10000.0,
			"direction": "Inflow",
			"reference": "TRF123",
			"normalized_reference": "TRF123",
			"description": "Customer transfer SINV-0001",
			"branch": "Airport Branch",
		},
	)
	def test_sales_invoice_candidate_search_returns_matching_invoice(
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
		self.assertEqual(candidates[0]["document_name"], "SINV-0001")
		self.assertEqual(candidates[0]["confidence"], "Strong Match")

	@patch("retailedge.bank_transaction_matching.frappe.get_all")
	@patch("retailedge.bank_transaction_matching.has_field")
	@patch("retailedge.bank_transaction_matching.has_doctype", return_value=True)
	@patch(
		"retailedge.bank_transaction_matching.normalize_bank_transaction",
		return_value={
			"bank_transaction": "ACC-BTN-0001",
			"company": "Process Edge (Demo)",
			"bank_account": "Moniepoint - moniepoint",
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
			"expected_bank_account": "Moniepoint - moniepoint",
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
			"bank_account": "Moniepoint - moniepoint",
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
					"paid_to": "Bank - PED",
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
		labels = [column["label"] for column in get_columns()[:11]]
		self.assertEqual(
			labels,
			[
				"Date",
				"Branch",
				"Bank Amount",
				"SI/PE Amount",
				"Difference",
				"Customer / Party",
				"Suggested Match",
				"Match Confidence",
				"Match Score",
				"Issue / Reason",
				"Action Status",
			],
		)

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
		self.assertEqual(
			build_suggested_match_label(
				{
					"suggested_document_type": "Payment Entry",
					"suggested_document": "PE-00045",
				}
			),
			"Payment Entry PE-00045",
		)

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
		self.assertEqual(len(rows), 1)
		mock_new_doc.assert_not_called()
		mock_set_value.assert_not_called()
