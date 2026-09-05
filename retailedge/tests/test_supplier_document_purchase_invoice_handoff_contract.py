from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSupplierDocumentPurchaseInvoiceHandoffContract(unittest.TestCase):
	def test_handoff_reuses_erpnext_purchase_order_mapper_and_is_draft_only(self):
		source = (APP_ROOT / "supplier_document_review.py").read_text()
		self.assertIn("from erpnext.buying.doctype.purchase_order.mapper import make_purchase_invoice", source)
		self.assertIn("purchase_invoice = make_purchase_invoice(po.name)", source)
		self.assertIn("purchase_invoice.insert()", source)
		self.assertIn("purchase_invoice.docstatus != 0", source)
		self.assertNotIn("purchase_invoice.submit()", source)
		self.assertNotIn('frappe.new_doc("GL Entry")', source)
		self.assertNotIn('frappe.new_doc("Stock Ledger Entry")', source)
		self.assertNotIn('frappe.new_doc("Payment Entry")', source)

	def test_supplier_company_and_po_authority_are_server_derived(self):
		source = (APP_ROOT / "supplier_document_review.py").read_text()
		self.assertIn('intake = frappe.get_doc("Supplier Document Intake", extraction.supplier_document_intake)', source)
		self.assertIn('po = frappe.get_doc("Purchase Order", intake.purchase_order)', source)
		self.assertIn("po.supplier != intake.supplier or po.company != intake.company", source)
		self.assertIn("extraction.purchase_order != po.name", source)
		self.assertNotIn('frappe.form_dict.get("supplier")', source)
		self.assertNotIn('frappe.form_dict.get("company")', source)
		self.assertNotIn('frappe.form_dict.get("purchase_order")', source)

	def test_both_source_document_and_extraction_must_be_accepted(self):
		source = (APP_ROOT / "supplier_document_review.py").read_text()
		self.assertIn('review_rows[0].decision != "Accepted"', source)
		self.assertIn('intake.review_status != "Accepted"', source)
		self.assertIn('intake.document_type != "Supplier Invoice"', source)
		self.assertIn("Accept the latest extraction evidence before accepting the supplier document.", source)

	def test_extracted_amounts_are_advisory_and_currency_mismatch_fails_closed(self):
		source = (APP_ROOT / "supplier_document_review.py").read_text()
		self.assertIn("extraction_is_advisory", source)
		self.assertIn("Extracted currency {0} does not match the ERPNext Purchase Order currency {1}.", source)
		self.assertIn("mapped_total = flt(purchase_invoice.grand_total)", source)
		self.assertNotIn("purchase_invoice.grand_total =", source)
		self.assertNotIn("purchase_invoice.total =", source)
		self.assertNotIn("purchase_invoice.taxes =", source)

	def test_handoff_is_internal_immutable_and_unique_per_extraction(self):
		controller = (APP_ROOT / "retailedge" / "doctype" / "supplier_document_purchase_invoice_handoff" / "supplier_document_purchase_invoice_handoff.py").read_text()
		schema = (APP_ROOT / "retailedge" / "doctype" / "supplier_document_purchase_invoice_handoff" / "supplier_document_purchase_invoice_handoff.json").read_text()
		self.assertIn("handoff history is immutable", controller)
		self.assertIn("retained for audit history", controller)
		self.assertIn('"fieldname":"extraction"', schema)
		self.assertIn('"unique":1', schema)
		self.assertNotIn('"role":"Supplier"', schema)
		self.assertNotIn('"create":1', schema)
		self.assertNotIn('"write":1', schema)

	def test_repeat_handoff_is_idempotent(self):
		source = (APP_ROOT / "supplier_document_review.py").read_text()
		self.assertIn("existing = _existing_handoff(extraction.name)", source)
		self.assertIn('"idempotent": True', source)
		self.assertIn("Record a new extraction before preparing another draft.", source)


if __name__ == "__main__":
	unittest.main()
