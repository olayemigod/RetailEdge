from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]
SELLING_UI = APP_ROOT / "public" / "js" / "professional_selling"


class TestSalesReturnCreditNoteUIContract(TestCase):
	def test_professional_invoice_dialog_adds_return_as_one_native_source_mode(self):
		component = (SELLING_UI / "ProfessionalSalesInvoiceDialog.vue").read_text()

		self.assertIn('{ key: "new", label: "New Invoice" }', component)
		self.assertIn('{ key: "quotation", label: "From Quotation" }', component)
		self.assertIn('{ key: "sales-order", label: "From Sales Order" }', component)
		self.assertIn('{ key: "delivery-note", label: "From Delivery Note" }', component)
		self.assertIn('{ key: "return", label: "Return / Credit Note" }', component)
		self.assertIn('return: "Submitted Sales Invoice"', component)
		self.assertIn("Prepare Draft Return / Credit Note", component)
		self.assertIn("create_sales_return_credit_note_draft", component)
		self.assertIn('if (this.mode === "return") { method = CREATE_RETURN; args = { sales_invoice: this.sourceDocument }; }', component)
		self.assertIn("no refund or Payment Entry is created automatically", component)

	def test_return_mode_reuses_existing_edgesuite_source_pattern(self):
		component = (SELLING_UI / "ProfessionalSalesInvoiceDialog.vue").read_text()

		self.assertIn(':searcher="searchSource"', component)
		self.assertIn("callMethod(SOURCE_SEARCH, { source: this.mode", component)
		self.assertIn("CustomerCreditSummary", component)
		self.assertEqual(component.count("<CustomerCreditSummary"), 1)
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("window.EdgeUI", component)

	def test_backend_delegates_return_truth_to_erpnext_and_stays_draft_first(self):
		source = (APP_ROOT / "professional_sales_invoice.py").read_text()

		self.assertIn("make_sales_return as erpnext_make_sales_return", source)
		self.assertIn("erpnext_make_sales_return(source.name)", source)
		self.assertIn('if not cint(target.get("is_return")):', source)
		self.assertIn('if str(target.get("return_against") or "") != source.name:', source)
		self.assertIn("_validate_invoice_stock_context(", source)
		self.assertIn("target.insert()", source)
		self.assertIn('"posting_status": "Draft"', source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn('frappe.new_doc("Payment Entry")', source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)

	def test_c9_does_not_replace_pos_or_add_a_custom_refund_editor(self):
		component = (SELLING_UI / "ProfessionalSalesInvoiceDialog.vue").read_text()
		backend = (APP_ROOT / "professional_sales_invoice.py").read_text()

		self.assertIn("Use the native POS return workflow", backend)
		self.assertIn('"is_consolidated": 1', backend)
		self.assertIn('"is_pos": 1', backend)
		self.assertNotIn("RefundDialog", component)
		self.assertNotIn("refund_amount", component)
		self.assertNotIn("store_credit", component.lower())
		self.assertNotIn("wallet", component.lower())


if __name__ == "__main__":
	import unittest

	unittest.main()
