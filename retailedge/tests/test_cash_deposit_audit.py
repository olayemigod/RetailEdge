from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.cash_deposit_audit import apply_submitted_deposits_to_daily_sales_audit

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCashDepositAudit(unittest.TestCase):
	def test_submitted_deposits_reduce_expected_physical_cash(self):
		doc = SimpleNamespace(
			pos_opening_shift="POS-OPEN-0001",
			company="Retail Company",
			opening_cash_amount=50000,
			cash_sales_amount=300000,
			cashier_expense_amount=20000,
			actual_closing_cash_amount=30000,
			variance_tolerance_used=0,
		)
		with patch("retailedge.cash_deposit_audit.get_submitted_deposit_total", return_value=300000):
			deposit_amount = apply_submitted_deposits_to_daily_sales_audit(doc)

		self.assertEqual(deposit_amount, 300000)
		self.assertEqual(doc.expected_cash_amount, 30000)
		self.assertEqual(doc.cash_variance_amount, 0)
		self.assertEqual(doc.net_variance_amount, 0)
		self.assertEqual(doc.shortage_amount, 0)
		self.assertEqual(doc.overage_amount, 0)
		self.assertEqual(doc.variance_within_tolerance, 1)

	@patch("retailedge.daily_sales_audit.get_daily_sales_audit_settings", return_value={"variance_tolerance": 0})
	@patch("retailedge.cash_deposit_audit.get_submitted_deposit_total", return_value=2000)
	def test_review_recalculation_keeps_submitted_deposit_and_balanced_classification(self, deposit, _settings):
		from retailedge.daily_sales_audit import (
			calculate_daily_sales_audit_variance,
			refresh_daily_sales_audit_review_summary,
		)

		doc = SimpleNamespace(
			pos_opening_shift="OPEN-1", company="Retail Company", audit_status="Draft",
			opening_cash_amount=0, cash_sales_amount=63000, cashier_expense_amount=10000,
			actual_closing_cash_amount=51000, clarification_required=0,
			cashier_expense_lines=[], invoice_lines=[], payment_lines=[],
		)
		for _ in range(2):
			result = calculate_daily_sales_audit_variance(doc)
			self.assertEqual(result["expected_cash_amount"], 51000)
			self.assertEqual(result["net_variance_amount"], 0)
			self.assertEqual(result["audit_result"], "Balanced")
			summary = refresh_daily_sales_audit_review_summary(doc)
			self.assertEqual(doc.expected_cash_amount, 51000)
			self.assertEqual(doc.variance_classification, "Balanced")
			self.assertEqual(summary["variance_status"], "Balanced")
			self.assertEqual(summary["exception_count"], 0)
		deposit.assert_called_with("OPEN-1", company="Retail Company")
		deposit.return_value = 0
		result = calculate_daily_sales_audit_variance(doc)
		self.assertEqual(result["expected_cash_amount"], 53000)
		self.assertEqual(result["net_variance_amount"], -2000)
		self.assertEqual(result["audit_result"], "Shortage")

	def test_reports_show_cash_deposits_and_batch_totals(self):
		register = (
			APP_ROOT
			/ "retailedge"
			/ "report"
			/ "retailedge_daily_sales_audit_register"
			/ "retailedge_daily_sales_audit_register.py"
		).read_text(encoding="utf-8")
		shift = (
			APP_ROOT
			/ "retailedge"
			/ "report"
			/ "retailedge_cash_shift_verification"
			/ "retailedge_cash_shift_verification.py"
		).read_text(encoding="utf-8")
		for source in (register, shift):
			self.assertIn('_("Cash Deposits")', source)
			self.assertIn("get_submitted_deposit_totals", source)
			self.assertIn("- deposit_amount", source) if source is register else self.assertIn("- cash_deposits", source)

	def test_deposit_totals_query_only_submitted_internal_transfers(self):
		source = (APP_ROOT / "cash_deposit_audit.py").read_text(encoding="utf-8")
		for contract in (
			'"docstatus": 1',
			'"payment_type": "Internal Transfer"',
			'"retailedge_cash_custody_type": CASH_DEPOSIT_TYPE',
			'"retailedge_pos_opening_shift": ["in", shifts]',
		):
			self.assertIn(contract, source)
		self.assertNotIn('"docstatus": ["in",', source)


if __name__ == "__main__":
	unittest.main()
