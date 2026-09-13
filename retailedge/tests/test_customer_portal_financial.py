from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]
FINANCIAL = APP_ROOT / "customer_portal_financial.py"
PORTAL_PAGE = APP_ROOT / "www" / "customer_portal.py"
STATEMENT_PAGE = APP_ROOT / "www" / "customer_account_statement.py"
STATEMENT_HTML = APP_ROOT / "www" / "customer_account_statement.html"


class TestCustomerPortalFinancial(TestCase):
	def setUp(self):
		self.financial = FINANCIAL.read_text(encoding="utf-8")
		self.portal_page = PORTAL_PAGE.read_text(encoding="utf-8")
		self.statement_page = STATEMENT_PAGE.read_text(encoding="utf-8")
		self.statement_html = STATEMENT_HTML.read_text(encoding="utf-8")

	def test_available_advance_uses_native_submitted_unallocated_customer_receipts(self):
		self.assertIn('frappe.get_all(\n\t\t"Payment Entry"', self.financial)
		self.assertIn('"docstatus": 1', self.financial)
		self.assertIn('"payment_type": "Receive"', self.financial)
		self.assertIn('"party_type": "Customer"', self.financial)
		self.assertIn('"party": ["in", customers]', self.financial)
		self.assertIn('"unallocated_amount": [">", 0]', self.financial)
		self.assertIn('"paid_from_account_currency"', self.financial)
		self.assertIn('"source_of_truth": "Payment Entry.unallocated_amount"', self.financial)
		self.assertIn("are not a wallet balance", self.financial)

	def test_advance_balances_are_grouped_by_company_and_currency_not_globally_summed(self):
		self.assertIn('key = (company, currency)', self.financial)
		self.assertIn('balance["available_advance"] += flt(row.unallocated_amount)', self.financial)
		self.assertIn('key=lambda item: (item["company"], item["currency"])', self.financial)
		self.assertNotIn('"total_available_advance"', self.financial)

	def test_statement_company_options_are_derived_from_customer_receivable_ledger(self):
		self.assertIn('frappe.get_all(\n\t\t"Payment Ledger Entry"', self.financial)
		self.assertIn('"account_type": "Receivable"', self.financial)
		self.assertIn('"party_type": "Customer"', self.financial)
		self.assertIn('"party": ["in", customers]', self.financial)
		self.assertIn('"delinked": 0', self.financial)
		self.assertIn("if company not in companies:", self.financial)
		self.assertIn("This Company is not linked to your customer account.", self.financial)

	def test_statement_uses_payment_ledger_signed_amounts_and_query_builder_opening_balance(self):
		self.assertIn('frappe.qb.DocType("Payment Ledger Entry")', self.financial)
		self.assertIn('Sum(ple.amount).as_("balance")', self.financial)
		self.assertIn("ple.party.isin(customers)", self.financial)
		self.assertIn("ple.posting_date < resolved_from", self.financial)
		self.assertIn('amount = flt(row.amount)', self.financial)
		self.assertIn("debit = amount if amount > 0 else 0.0", self.financial)
		self.assertIn("credit = abs(amount) if amount < 0 else 0.0", self.financial)
		self.assertIn("running_balance += amount", self.financial)
		self.assertIn('"source_of_truth": "Payment Ledger Entry"', self.financial)

	def test_statement_is_bounded_and_read_only(self):
		self.assertIn("MAX_ADVANCE_ROWS = 200", self.financial)
		self.assertIn("MAX_STATEMENT_ROWS = 500", self.financial)
		self.assertIn("MAX_STATEMENT_DAYS = 366", self.financial)
		self.assertIn("limit_page_length=MAX_ADVANCE_ROWS + 1", self.financial)
		self.assertIn("limit_page_length=MAX_STATEMENT_ROWS + 1", self.financial)
		self.assertIn("date_diff(resolved_to, resolved_from) >= MAX_STATEMENT_DAYS", self.financial)
		for forbidden in (
			"frappe.new_doc(",
			".insert(",
			".submit()",
			"frappe.db.set_value",
			"frappe.db.commit",
			"update `tab",
			"delete from `tab",
		):
			self.assertNotIn(forbidden, self.financial)

	def test_statement_page_accepts_only_company_and_date_filters_not_customer_identity(self):
		self.assertIn('frappe.form_dict.get("company")', self.statement_page)
		self.assertIn('frappe.form_dict.get("from_date")', self.statement_page)
		self.assertIn('frappe.form_dict.get("to_date")', self.statement_page)
		self.assertNotIn('frappe.form_dict.get("customer")', self.statement_page)
		self.assertIn("get_customer_account_statement", self.statement_page)
		self.assertIn('action="/customer_account_statement"', self.statement_html)
		self.assertNotIn('name="customer"', self.statement_html)

	def test_portal_exposes_advance_balances_through_existing_section_renderer(self):
		self.assertIn("get_customer_advance_summary", self.portal_page)
		self.assertIn('"label": "Advances & Statements"', self.portal_page)
		self.assertIn('"route": "/customer_account_statement"', self.portal_page)
		self.assertIn('"Available Advance"', self.portal_page)
		self.assertIn("quote(company, safe='')", self.portal_page)

	def test_customer_facing_financial_copy_is_product_neutral(self):
		for source in (self.statement_html, self.statement_page):
			self.assertNotIn("RetailEdge", source)
			self.assertNotIn("ProcessEdge", source)
			self.assertNotIn("Powered by", source)
		self.assertIn("ERPNext Payment Ledger Entry receivable activity", self.statement_html)
		self.assertIn("does not create, reconcile or change", self.statement_html)


if __name__ == "__main__":
	import unittest

	unittest.main()
