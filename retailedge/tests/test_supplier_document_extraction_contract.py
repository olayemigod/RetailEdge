from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSupplierDocumentExtractionContract(unittest.TestCase):
	def test_manual_extraction_reuses_intake_authority_and_private_file(self):
		source = (APP_ROOT / "supplier_document_extraction.py").read_text()
		self.assertIn("_assert_internal_extraction_user()", source)
		self.assertIn('_load_intake(intake_name, lock=True)', source)
		self.assertIn('"attached_to_doctype": "Supplier Document Intake"', source)
		self.assertIn('"attached_to_name": intake.name', source)
		self.assertIn('"is_private": 1', source)
		self.assertIn('"supplier": intake.supplier', source)
		self.assertIn('"company": intake.company', source)
		self.assertIn('"purchase_order": intake.purchase_order', source)
		self.assertNotIn('frappe.form_dict.get("supplier")', source)
		self.assertNotIn('frappe.form_dict.get("company")', source)

	def test_manual_api_is_structured_assistance_not_buying_document_creation(self):
		source = (APP_ROOT / "supplier_document_extraction.py").read_text()
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("def record_manual_extraction(", source)
		self.assertIn('extraction_method="Manual"', source)
		self.assertIn('"native_buying_document_created": False', source)
		self.assertIn('"accounting_mutated": False', source)
		for forbidden in (
			'frappe.new_doc("Purchase Invoice")',
			'frappe.new_doc("Purchase Order")',
			'frappe.new_doc("Payment Entry")',
			'frappe.new_doc("GL Entry")',
			'frappe.new_doc("Stock Ledger Entry")',
		):
			self.assertNotIn(forbidden, source)

	def test_provider_boundary_is_not_browser_whitelisted_or_hard_wired(self):
		source = (APP_ROOT / "supplier_document_extraction.py").read_text()
		provider_pos = source.index("def record_provider_extraction(")
		prefix = source[max(0, provider_pos - 80):provider_pos]
		self.assertNotIn("@frappe.whitelist", prefix)
		self.assertIn("provider-neutral", source.lower())
		self.assertNotIn("openai", source.lower())
		self.assertNotIn("google vision", source.lower())
		self.assertNotIn("aws textract", source.lower())
		self.assertNotIn("azure", source.lower())

	def test_extraction_evidence_and_reviews_are_immutable_and_internal(self):
		extraction_controller = (
			APP_ROOT / "retailedge" / "doctype" / "supplier_document_extraction" / "supplier_document_extraction.py"
		).read_text()
		extraction_schema = (
			APP_ROOT / "retailedge" / "doctype" / "supplier_document_extraction" / "supplier_document_extraction.json"
		).read_text()
		review_controller = (
			APP_ROOT / "retailedge" / "doctype" / "supplier_document_extraction_review" / "supplier_document_extraction_review.py"
		).read_text()
		review_schema = (
			APP_ROOT / "retailedge" / "doctype" / "supplier_document_extraction_review" / "supplier_document_extraction_review.json"
		).read_text()
		self.assertIn("extraction evidence is immutable", extraction_controller)
		self.assertIn("private file attached to its intake record", extraction_controller)
		self.assertIn("extraction reviews are immutable", review_controller)
		self.assertIn("already has a final review", review_controller)
		self.assertNotIn('"role":"Supplier"', extraction_schema)
		self.assertNotIn('"role":"Supplier"', review_schema)
		self.assertNotIn('"create":1', extraction_schema)
		self.assertNotIn('"write":1', extraction_schema)
		self.assertNotIn('"create":1', review_schema)
		self.assertNotIn('"write":1', review_schema)

	def test_corrections_require_new_extraction_and_review_is_append_only(self):
		source = (APP_ROOT / "supplier_document_extraction.py").read_text()
		self.assertIn("This extraction already has a final review. Record a new extraction to correct values.", source)
		self.assertIn('frappe.new_doc("Supplier Document Extraction Review")', source)
		self.assertNotIn("db_set(", source)
		self.assertNotIn("set_value(", source)

	def test_desk_ui_only_sends_intake_identity_and_extracted_suggestions(self):
		intake_js = (
			APP_ROOT / "retailedge" / "doctype" / "supplier_document_intake" / "supplier_document_intake.js"
		).read_text()
		extraction_js = (
			APP_ROOT / "retailedge" / "doctype" / "supplier_document_extraction" / "supplier_document_extraction.js"
		).read_text()
		self.assertIn("record_manual_extraction", intake_js)
		self.assertIn("intake_name: frm.doc.name", intake_js)
		self.assertNotIn("supplier:", intake_js)
		self.assertNotIn("company:", intake_js)
		self.assertIn("record_extraction_review", extraction_js)
		self.assertIn("Accept Extraction", extraction_js)
		self.assertIn("Reject Extraction", extraction_js)


if __name__ == "__main__":
	unittest.main()
