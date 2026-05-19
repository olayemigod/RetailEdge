from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe

from retailedge.branch_performance import (
	get_branch_payment_breakdown,
	get_branch_performance_summary,
	get_branch_sales_summary,
	get_branch_stock_activity_summary,
	get_branch_variance_summary,
)
from retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary import (
	execute as execute_branch_performance_report,
)


class _PaymentRow(SimpleNamespace):
	def as_dict(self):
		return dict(self.__dict__)


class BranchPerformanceTests(unittest.TestCase):
	@patch("retailedge.branch_performance.resolve_retailedge_branch_context", return_value={"branch": "HQ", "messages": []})
	@patch("retailedge.branch_performance.frappe.get_all")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_get_branch_sales_summary_uses_submitted_sales_invoices_only(
		self,
		_mock_has_doctype,
		mock_has_field,
		mock_get_all,
		_mock_resolve,
	):
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname in {
			"company",
			"is_pos",
			"pos_profile",
			"posting_date",
			"paid_amount",
			"retailedge_branch",
		}

		def _fake_get_all(doctype, filters=None, fields=None, **kwargs):
			self.assertEqual(doctype, "Sales Invoice")
			self.assertEqual(filters.get("docstatus"), 1)
			return [
				{
					"name": "SINV-001",
					"company": "Process Edge (Demo)",
					"grand_total": 1000.0,
					"outstanding_amount": 0.0,
					"paid_amount": 1000.0,
					"retailedge_branch": "HQ",
				},
				{
					"name": "SINV-002",
					"company": "Process Edge (Demo)",
					"grand_total": 500.0,
					"outstanding_amount": 500.0,
					"paid_amount": 0.0,
					"retailedge_branch": "HQ",
				},
			]

		mock_get_all.side_effect = _fake_get_all

		summary = get_branch_sales_summary({"company": "Process Edge (Demo)", "branch": "HQ"})
		self.assertEqual(summary["sales_invoice_count"], 2)
		self.assertEqual(summary["paid_invoice_count"], 1)
		self.assertEqual(summary["unpaid_invoice_count"], 1)
		self.assertEqual(summary["partially_paid_invoice_count"], 0)
		self.assertEqual(summary["total_sales_amount"], 1500.0)
		self.assertEqual(summary["credit_sales_amount"], 500.0)

	@patch(
		"retailedge.branch_performance._get_matching_sales_invoices",
		return_value=([{"name": "SINV-003", "grand_total": 5000.0}], []),
	)
	@patch("retailedge.branch_performance.frappe.get_doc")
	def test_get_branch_payment_breakdown_uses_payment_rows_not_grand_total(self, mock_get_doc, _mock_matching_invoices):
		mock_get_doc.return_value = SimpleNamespace(
			payments=[
				_PaymentRow(mode_of_payment="Cash", amount=1000.0, account="Cash - PED"),
				_PaymentRow(mode_of_payment="Bank Transfer", amount=500.0, account="Bank - PED"),
			]
		)

		breakdown = get_branch_payment_breakdown({"branch": "HQ"})
		self.assertEqual(breakdown["Cash"], 1000.0)
		self.assertEqual(breakdown["Bank Transfer"], 500.0)
		self.assertEqual(breakdown["Card / POS"], 0.0)
		self.assertNotEqual(breakdown["Cash"], 5000.0)

	@patch("retailedge.branch_performance.get_cashier_expenses_for_daily_audit")
	@patch("retailedge.branch_performance.get_invoice_payment_audit_summary")
	@patch("retailedge.branch_performance.get_branch_stock_activity_summary")
	@patch("retailedge.branch_performance.get_branch_variance_summary")
	@patch("retailedge.branch_performance.get_branch_payment_breakdown")
	@patch("retailedge.branch_performance.get_branch_sales_summary")
	@patch(
		"retailedge.branch_performance.get_branch_query_filters",
		return_value={"filters": {}, "messages": [], "branch": "HQ", "allowed_branches": []},
	)
	def test_get_branch_performance_summary_excludes_cancelled_expenses(
		self,
		_mock_scope,
		mock_sales,
		mock_payments,
		mock_variance,
		mock_stock,
		mock_invoice_audit,
		mock_expenses,
	):
		mock_sales.return_value = {
			"total_sales_amount": 1000.0,
			"sales_invoice_count": 1,
			"paid_invoice_count": 1,
			"unpaid_invoice_count": 0,
			"partially_paid_invoice_count": 0,
			"credit_sales_amount": 0.0,
			"messages": [],
		}
		mock_payments.return_value = {
			"Cash": 1000.0,
			"Bank Transfer": 0.0,
			"Card / POS": 0.0,
			"Mobile Money": 0.0,
			"Other": 0.0,
			"messages": [],
		}
		mock_variance.return_value = {
			"expected_cash_amount": 1000.0,
			"actual_closing_cash_amount": 1000.0,
			"cash_variance_amount": 0.0,
			"daily_audit_count": 1,
			"daily_audit_pending_count": 0,
			"daily_audit_approved_count": 1,
			"daily_audit_variance_count": 0,
			"messages": [],
		}
		mock_stock.return_value = {"material_request_count": 0, "stock_entry_count": 0, "messages": []}
		mock_invoice_audit.return_value = {
			"payment_account_mismatch_count": 1,
			"payment_amount_mismatch_count": 0,
			"payment_rows_missing_count": 1,
			"ready_for_verification_count": 2,
			"credit_count": 0,
			"high_risk_count": 1,
		}
		mock_expenses.return_value = [
			{"name": "RE-CE-001", "amount": 150.0, "expense_status": "Submitted"},
			{"name": "RE-CE-002", "amount": 75.0, "expense_status": "Cancelled"},
		]

		summary = get_branch_performance_summary({"company": "Process Edge (Demo)"})
		self.assertEqual(summary["branch"], "HQ")
		self.assertEqual(summary["cashier_expense_amount"], 150.0)
		self.assertEqual(summary["cashier_expense_count"], 1)
		self.assertEqual(summary["invoice_payment_audit_issue_count"], 2)
		self.assertEqual(summary["high_risk_invoice_count"], 1)

	@patch("retailedge.branch_performance._get_matching_daily_sales_audits")
	def test_get_branch_variance_summary_counts_statuses(self, mock_audits):
		mock_audits.return_value = [
			{
				"audit_status": "Approved",
				"audit_result": "Balanced",
				"expected_cash_amount": 1000.0,
				"actual_closing_cash_amount": 1000.0,
				"cash_variance_amount": 0.0,
			},
			{
				"audit_status": "Variance Found",
				"audit_result": "Overage",
				"expected_cash_amount": 1000.0,
				"actual_closing_cash_amount": 1200.0,
				"cash_variance_amount": 200.0,
			},
			{
				"audit_status": "In Review",
				"audit_result": "Not Checked",
				"expected_cash_amount": 500.0,
				"actual_closing_cash_amount": 400.0,
				"cash_variance_amount": -100.0,
			},
		]

		summary = get_branch_variance_summary({"branch": "HQ"})
		self.assertEqual(summary["daily_audit_count"], 3)
		self.assertEqual(summary["daily_audit_approved_count"], 1)
		self.assertEqual(summary["daily_audit_pending_count"], 1)
		self.assertEqual(summary["daily_audit_variance_count"], 1)
		self.assertEqual(summary["cash_variance_amount"], 100.0)

	@patch("retailedge.branch_performance.resolve_retailedge_branch_context", return_value={"branch": "HQ", "messages": []})
	@patch("retailedge.branch_performance.frappe.get_all")
	@patch("retailedge.branch_performance.has_field")
	@patch("retailedge.branch_performance.has_doctype", return_value=True)
	def test_get_branch_stock_activity_summary_uses_branch_attribution_where_available(
		self,
		_mock_has_doctype,
		mock_has_field,
		mock_get_all,
		_mock_resolve,
	):
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname in {"company", "posting_date", "retailedge_branch"}

		def _fake_get_all(doctype, filters=None, fields=None, **kwargs):
			if doctype == "Material Request":
				return [
					{"name": "MAT-001", "retailedge_branch": "HQ"},
					{"name": "MAT-002", "retailedge_branch": "Airport Branch"},
				]
			if doctype == "Stock Entry":
				return [{"name": "STE-001", "retailedge_branch": "HQ"}]
			return []

		mock_get_all.side_effect = _fake_get_all
		summary = get_branch_stock_activity_summary({"branch": "HQ"})
		self.assertEqual(summary["material_request_count"], 1)
		self.assertEqual(summary["stock_entry_count"], 1)

	@patch("retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_branch_performance_summary")
	@patch(
		"retailedge.retailedge.report.retailedge_branch_performance_summary.retailedge_branch_performance_summary.get_candidate_branches",
		return_value=["HQ"],
	)
	def test_branch_performance_report_executes(self, _mock_branches, mock_summary):
		mock_summary.return_value = {
			"branch": "HQ",
			"total_sales_amount": 1200.0,
			"sales_invoice_count": 2,
			"paid_invoice_count": 1,
			"unpaid_invoice_count": 1,
			"partially_paid_invoice_count": 0,
			"credit_sales_amount": 200.0,
			"cash_sales_amount": 1000.0,
			"bank_transfer_amount": 200.0,
			"card_pos_amount": 0.0,
			"mobile_money_amount": 0.0,
			"other_payment_amount": 0.0,
			"cashier_expense_amount": 100.0,
			"expected_cash_amount": 900.0,
			"actual_closing_cash_amount": 950.0,
			"cash_variance_amount": 50.0,
			"daily_audit_count": 1,
			"daily_audit_pending_count": 0,
			"daily_audit_approved_count": 1,
			"daily_audit_variance_count": 0,
			"material_request_count": 1,
			"stock_entry_count": 1,
			"exception_count": 1,
		}

		columns, data, _, _, summary = execute_branch_performance_report({"branch": "HQ"})
		self.assertTrue(columns)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["branch"], "HQ")
		self.assertTrue(summary)
