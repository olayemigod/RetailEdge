from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from retailedge.invoice_payment_audit import (
	audit_sales_invoice_payment,
	classify_payment_method,
	get_expected_payment_account_for_invoice,
	get_invoice_payment_audit_list,
	get_invoice_payment_audit_summary,
	get_payment_entries_for_sales_invoice,
	get_sales_invoice_payment_rows,
)
from retailedge.retailedge.report.retailedge_invoice_payment_audit.retailedge_invoice_payment_audit import (
	execute as execute_invoice_payment_audit_report,
)


class _PaymentRow(SimpleNamespace):
	def as_dict(self):
		return dict(self.__dict__)


class InvoicePaymentAuditTests(unittest.TestCase):
	def _invoice(self, **kwargs):
		defaults = dict(
			doctype="Sales Invoice",
			name="SINV-0001",
			company="Process Edge (Demo)",
			customer="Customer A",
			posting_date="2026-05-18",
			grand_total=1000.0,
			rounded_total=1000.0,
			paid_amount=0.0,
			outstanding_amount=1000.0,
			docstatus=1,
			status="Unpaid",
			is_pos=1,
			retailedge_branch="HQ",
			branch=None,
			pos_profile="Testing",
			owner="cashier@example.com",
			payments=[],
		)
		defaults.update(kwargs)
		return SimpleNamespace(**defaults)

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_audit_sales_invoice_payment_returns_structured_result(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice()
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["invoice"], "SINV-0001")
		self.assertEqual(result["branch"], "HQ")
		self.assertEqual(result["source"], "read_only")
		self.assertIn("payment_audit_status", result)

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_credit_invoice_is_classified_as_credit(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(paid_amount=0.0, outstanding_amount=1000.0, status="Unpaid")
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Credit")
		self.assertEqual(result["payment_risk_level"], "Low")

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_partially_paid_invoice_is_classified_as_partial(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(paid_amount=400.0, outstanding_amount=600.0, status="Partly Paid")
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Partially Paid")
		self.assertEqual(result["payment_risk_level"], "Medium")

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_fully_paid_invoice_with_rows_is_ready_for_verification(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(
			paid_amount=1000.0,
			outstanding_amount=0.0,
			status="Paid",
			payments=[_PaymentRow(mode_of_payment="Cash", account="Cash - PED", amount=1000.0, base_amount=1000.0)],
		)
		with patch("retailedge.invoice_payment_audit.get_branch_profile_defaults", return_value={"default_cash_account": "Cash - PED"}):
			result = audit_sales_invoice_payment("SINV-0001")
		self.assertIn(result["payment_audit_status"], {"Ready for Verification", "Fully Paid Pending Audit"})

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_missing_payment_rows_are_detected(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(paid_amount=1000.0, outstanding_amount=0.0, status="Paid", payments=[])
		with patch("retailedge.invoice_payment_audit.get_payment_entries_for_sales_invoice", return_value=[]):
			result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Payment Rows Missing")

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_payment_row_total_mismatch_is_detected(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(
			paid_amount=1000.0,
			outstanding_amount=0.0,
			status="Paid",
			payments=[_PaymentRow(mode_of_payment="Cash", account="Cash - PED", amount=700.0, base_amount=700.0)],
		)
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Payment Amount Mismatch")

	@patch("retailedge.invoice_payment_audit.get_branch_profile_defaults", return_value={"default_cash_account": "Cash - PED"})
	def test_payment_account_mismatch_is_detected(self, _mock_defaults):
		rows = get_sales_invoice_payment_rows(
			self._invoice(paid_amount=1000.0, outstanding_amount=0.0, payments=[_PaymentRow(mode_of_payment="Cash", account="Cash - OTHER", amount=1000.0, base_amount=1000.0)])
		)
		self.assertFalse(rows[0]["account_matches_expected"])

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_split_payment_is_detected(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(
			paid_amount=1000.0,
			outstanding_amount=0.0,
			status="Paid",
			payments=[
				_PaymentRow(mode_of_payment="Cash", account="Cash - PED", amount=400.0, base_amount=400.0),
				_PaymentRow(mode_of_payment="Bank Transfer", account="Bank - PED", amount=600.0, base_amount=600.0),
			],
		)
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Split Payment")

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_overpaid_invoice_is_detected(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(
			paid_amount=1200.0,
			outstanding_amount=0.0,
			status="Paid",
			payments=[_PaymentRow(mode_of_payment="Cash", account="Cash - PED", amount=1200.0, base_amount=1200.0)],
		)
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Overpaid")

	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_doc")
	def test_underpaid_invoice_is_detected(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._invoice(
			paid_amount=300.0,
			outstanding_amount=700.0,
			status="Partly Paid",
			payments=[_PaymentRow(mode_of_payment="Cash", account="Cash - PED", amount=300.0, base_amount=300.0)],
		)
		result = audit_sales_invoice_payment("SINV-0001")
		self.assertEqual(result["payment_audit_status"], "Partially Paid")

	@patch("retailedge.invoice_payment_audit.has_doctype", side_effect=lambda doctype: doctype in {"Payment Entry", "Payment Entry Reference"})
	@patch("retailedge.invoice_payment_audit.frappe.get_all")
	def test_payment_entry_references_are_read_without_mutation(self, mock_get_all, _mock_has_doctype):
		def _fake_get_all(doctype, filters=None, fields=None, **kwargs):
			if doctype == "Payment Entry Reference":
				return [{"parent": "PAY-0001", "allocated_amount": 500.0}]
			if doctype == "Payment Entry":
				return [
					{
						"name": "PAY-0001",
						"posting_date": "2026-05-18",
						"party": "Customer A",
						"paid_amount": 500.0,
						"received_amount": 500.0,
						"paid_from": None,
						"paid_to": "Cash - PED",
						"mode_of_payment": "Cash",
						"docstatus": 1,
					}
				]
			return []

		mock_get_all.side_effect = _fake_get_all
		rows = get_payment_entries_for_sales_invoice("SINV-0001")
		self.assertEqual(rows[0]["payment_entry"], "PAY-0001")
		self.assertEqual(rows[0]["reference_allocated_amount"], 500.0)

	def test_classify_payment_method_uses_keywords(self):
		self.assertEqual(classify_payment_method(mode_of_payment="Cash")["category"], "Cash")
		self.assertEqual(classify_payment_method(account="Bank Transfer - PED")["category"], "Bank Transfer")
		self.assertEqual(classify_payment_method(mode_of_payment="POS Terminal")["category"], "Card / POS")

	@patch("retailedge.invoice_payment_audit.get_branch_profile_defaults", return_value={"default_bank_account": "Bank - PED"})
	def test_branch_profile_expected_accounts_are_used(self, _mock_defaults):
		result = get_expected_payment_account_for_invoice(self._invoice(), payment_category="Bank Transfer")
		self.assertEqual(result["account"], "Bank - PED")

	@patch("retailedge.invoice_payment_audit.get_invoice_payment_audit_list")
	def test_invoice_payment_audit_summary_counts_statuses(self, mock_list):
		mock_list.return_value = [
			{"grand_total": 1000.0, "payment_audit_status": "Credit", "payment_classification": "Credit", "payment_risk_level": "Low"},
			{"grand_total": 1000.0, "payment_audit_status": "Payment Amount Mismatch", "payment_classification": "Variance Found", "payment_risk_level": "High"},
		]
		summary = get_invoice_payment_audit_summary({"company": "Process Edge (Demo)"})
		self.assertEqual(summary["total_invoice_count"], 2)
		self.assertEqual(summary["credit_count"], 1)
		self.assertEqual(summary["payment_amount_mismatch_count"], 1)
		self.assertEqual(summary["high_risk_count"], 1)

	@patch("retailedge.invoice_payment_audit.audit_sales_invoice_payment")
	@patch("retailedge.invoice_payment_audit.get_retailedge_settings", return_value=SimpleNamespace())
	@patch("retailedge.invoice_payment_audit.frappe.get_all")
	@patch("retailedge.invoice_payment_audit.has_field", return_value=True)
	@patch("retailedge.invoice_payment_audit.has_doctype", return_value=True)
	def test_invoice_payment_audit_list_respects_branch_filter(
		self, _mock_has_doctype, _mock_has_field, mock_get_all, _mock_settings, mock_audit
	):
		mock_get_all.return_value = [{"name": "SINV-0001", "company": "Process Edge (Demo)", "retailedge_branch": "HQ"}]
		mock_audit.return_value = {
			"invoice": "SINV-0001",
			"branch": "HQ",
			"payment_audit_status": "Credit",
			"payment_risk_level": "Low",
			"payment_classification": "Credit",
			"payment_method_summary": {"Cash": 0.0},
			"account_summary": {"actual_accounts": [], "expected_accounts": []},
			"issues": [],
			"grand_total": 1000.0,
			"paid_amount": 0.0,
			"outstanding_amount": 1000.0,
			"net_payment_row_amount": 0.0,
			"payment_entry_amount": 0.0,
			"payment_difference": -1000.0,
			"company": "Process Edge (Demo)",
			"customer": "Customer A",
			"posting_date": "2026-05-18",
			"erp_status": "Unpaid",
			"branch_source": "Sales Invoice.retailedge_branch",
		}
		rows = get_invoice_payment_audit_list({"branch": "HQ"}, limit=20)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["branch"], "HQ")

	@patch("retailedge.retailedge.report.retailedge_invoice_payment_audit.retailedge_invoice_payment_audit.get_invoice_payment_audit_summary")
	@patch("retailedge.retailedge.report.retailedge_invoice_payment_audit.retailedge_invoice_payment_audit.get_invoice_payment_audit_list")
	def test_invoice_payment_audit_report_executes(self, mock_list, mock_summary):
		mock_list.return_value = [
			{
				"sales_invoice": "SINV-0001",
				"posting_date": "2026-05-18",
				"company": "Process Edge (Demo)",
				"branch": "HQ",
				"customer": "Customer A",
				"grand_total": 1000.0,
				"paid_amount": 1000.0,
				"outstanding_amount": 0.0,
				"payment_row_amount": 1000.0,
				"payment_entry_amount": 0.0,
				"difference": 0.0,
				"erp_status": "Paid",
				"payment_audit_status": "Ready for Verification",
				"payment_risk_level": "Low",
				"payment_classification": "Ready for Verification",
				"payment_methods": "Cash",
				"accounts_used": "Cash - PED",
				"expected_accounts": "Cash - PED",
				"issues": "",
				"branch_source": "Sales Invoice.retailedge_branch",
			}
		]
		mock_summary.return_value = {
			"total_invoice_count": 1,
			"payment_rows_missing_count": 0,
			"payment_account_mismatch_count": 0,
			"high_risk_count": 0,
		}
		columns, data, _, _, summary = execute_invoice_payment_audit_report({"branch": "HQ"})
		self.assertTrue(columns)
		self.assertEqual(len(data), 1)
		self.assertTrue(summary)
