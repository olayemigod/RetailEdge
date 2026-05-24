from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification import (
	execute,
	get_cash_status,
)


class CashShiftVerificationTests(unittest.TestCase):
	def test_cash_shift_verification_status_handles_balanced_shortage_and_overage(self):
		self.assertEqual(
			get_cash_status({"opening_shift": "OPEN-1", "closing_shift": "CLOSE-1", "cash_variance": 0}),
			"Balanced",
		)
		self.assertEqual(
			get_cash_status({"opening_shift": "OPEN-1", "closing_shift": "CLOSE-1", "cash_variance": -50}),
			"Shortage",
		)
		self.assertEqual(
			get_cash_status({"opening_shift": "OPEN-1", "closing_shift": "CLOSE-1", "cash_variance": 75}),
			"Overage",
		)

	def test_cash_shift_verification_status_handles_missing_shifts(self):
		self.assertEqual(get_cash_status({"opening_shift": None, "closing_shift": "CLOSE-1", "cash_variance": 0}), "Missing Opening Shift")
		self.assertEqual(get_cash_status({"opening_shift": "OPEN-1", "closing_shift": None, "cash_variance": 0}), "Missing Closing Shift")

	@patch("retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification.get_cash_invoice_sync_counts", return_value=(2, 1))
	@patch("retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification.has_doctype", return_value=True)
	@patch("retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification.get_branch_query_filters")
	@patch("retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification.frappe.get_all")
	def test_cash_shift_verification_executes_and_uses_expected_cash_formula(self, mock_get_all, mock_branch_filters, _mock_has_doctype, _mock_sync_counts):
		mock_branch_filters.return_value = {"filters": {}}
		mock_get_all.return_value = [
			{
				"name": "RE-DSA-0001",
				"audit_date": "2026-05-20",
				"company": "Process Edge (Demo)",
				"branch": "HQ",
				"pos_profile": "Main POS",
				"cashier": "cashier@example.com",
				"pos_opening_shift": "OPEN-1",
				"pos_closing_shift": "CLOSE-1",
				"opening_cash_amount": 1000.0,
				"cash_sales_amount": 700.0,
				"cashier_expense_amount": 200.0,
				"expected_cash_amount": 1500.0,
				"actual_closing_cash_amount": 1400.0,
				"cash_variance_amount": -100.0,
				"audit_status": "In Review",
			}
		]
		columns, rows, _, _, summary = execute({"company": "Process Edge (Demo)"})
		self.assertTrue(columns)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["expected_cash"], 1500.0)
		self.assertEqual(rows[0]["cash_variance"], -100.0)
		self.assertEqual(rows[0]["cash_status"], "Shortage")
		self.assertEqual(rows[0]["eligible_cash_invoices"], 2)
		self.assertEqual(rows[0]["synced_cash_invoices"], 1)
		self.assertTrue(summary)
