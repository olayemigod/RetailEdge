from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
SELLING_UI = APP_ROOT / "public" / "js" / "professional_selling"


class TestCustomerCreditVisibilityUIContract(TestCase):
	def test_shared_credit_summary_uses_governed_edgesuite_and_read_only_server_adapter(self):
		component = (SELLING_UI / "CustomerCreditSummary.vue").read_text()

		self.assertIn("retailedge.customer_credit_visibility.get_customer_credit_visibility", component)
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertNotIn("window.EdgeUI", component)
		self.assertIn('props: {\n\t\tcustomer:', component)
		self.assertIn('company: { type: String, default: "" }', component)
		self.assertIn("Company-level ERPNext credit exposure is shown for guidance only", component)
		self.assertIn("Final Sales Order / Sales Invoice submission remains governed by ERPNext", component)
		self.assertIn("token !== this.requestToken", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("override", component.lower())

	def test_new_sales_order_and_invoice_share_the_same_credit_summary(self):
		order = (SELLING_UI / "ProfessionalSalesOrderDialog.vue").read_text()
		invoice = (SELLING_UI / "ProfessionalSalesInvoiceDialog.vue").read_text()

		for source in (order, invoice):
			self.assertIn('import CustomerCreditSummary from "./CustomerCreditSummary.vue";', source)
			self.assertEqual(source.count("<CustomerCreditSummary"), 1)
			self.assertIn(':customer="values.customer"', source)
			self.assertIn(':company="values.company"', source)
			self.assertIn("CustomerCreditSummary }", source)

		# Existing native source-document conversion paths remain present and are not
		# replaced by RetailEdge credit logic.
		self.assertIn("create_sales_order_from_quotation", order)
		self.assertIn("MAP_METHOD", order)
		self.assertIn("create_sales_invoice_from_quotation", invoice)
		self.assertIn("create_sales_invoice_from_sales_order", invoice)
		self.assertIn("create_sales_invoice_from_delivery_note", invoice)

	def test_backend_reuses_erpnext_credit_truth_without_writes_or_submission_controls(self):
		source = (APP_ROOT / "customer_credit_visibility.py").read_text()

		for helper in (
			"get_credit_limit",
			"get_customer_outstanding",
			"get_customer_overdue_amount",
			"get_overdue_billing_threshold",
		):
			self.assertIn(helper, source)
		self.assertIn('"source_of_truth": "ERPNext customer credit helpers and Customer Credit Limit configuration"', source)
		self.assertIn('"advisory_only": True', source)
		self.assertIn('"final_enforcement": "ERPNext Sales Order / Sales Invoice submission controls"', source)
		self.assertNotIn(".submit(", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("frappe.db.set_value", source)
		self.assertNotIn("frappe.db.sql(", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertNotIn("ignore_permissions=True", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
