from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSupplierDocumentIntakeContract(unittest.TestCase):
	def test_upload_boundary_rederives_supplier_and_purchase_order_authority(self):
		source = (APP_ROOT / "supplier_document_intake.py").read_text()
		self.assertIn("_assert_supplier_portal_user()", source)
		self.assertIn('frappe.get_doc("Purchase Order", purchase_order_name)', source)
		self.assertIn("purchase_order.supplier not in suppliers", source)
		self.assertIn("has_website_permission", source)
		self.assertIn("purchase_order.docstatus != 1", source)
		self.assertNotIn('frappe.form_dict.get("supplier")', source)
		self.assertNotIn('frappe.form_dict.get("company")', source)

	def test_upload_uses_private_file_and_namespaced_review_queue_only(self):
		source = (APP_ROOT / "supplier_document_intake.py").read_text()
		self.assertIn('frappe.whitelist(methods=["POST"])', source)
		self.assertIn("frappe.local", source)
		self.assertIn("ALLOWED_MIMETYPES", source)
		self.assertIn('frappe.new_doc("Supplier Document Intake")', source)
		self.assertIn("is_private=1", source)
		self.assertIn('"native_buying_document_created": False', source)
		self.assertNotIn('frappe.new_doc("Purchase Invoice")', source)
		self.assertNotIn('frappe.new_doc("Purchase Order")', source)
		self.assertNotIn("GL Entry", source)
		self.assertNotIn("Stock Ledger Entry", source)
		self.assertNotIn("Payment Entry", source)

	def test_intake_doctype_is_not_supplier_writable_and_preserves_source_identity(self):
		controller = (
			APP_ROOT
			/ "retailedge"
			/ "doctype"
			/ "supplier_document_intake"
			/ "supplier_document_intake.py"
		).read_text()
		schema = (
			APP_ROOT
			/ "retailedge"
			/ "doctype"
			/ "supplier_document_intake"
			/ "supplier_document_intake.json"
		).read_text()
		self.assertIn("supplier_document_intake_api_write", controller)
		self.assertIn("IMMUTABLE_FIELDS", controller)
		self.assertIn("Accepted or rejected supplier documents cannot be reopened.", controller)
		self.assertIn("Supplier document intake records are retained for review history.", controller)
		self.assertNotIn('"role":"Supplier"', schema)
		self.assertIn('"Purchase Manager"', schema)
		self.assertIn('"Accounts Manager"', schema)
		self.assertIn('"track_changes": 1', schema)

	def test_supplier_document_page_uses_native_upload_handler_without_generic_doctype_write(self):
		template = (APP_ROOT / "www" / "supplier_documents.html").read_text()
		self.assertIn('fetch("/api/method/upload_file"', template)
		self.assertIn('body.append("is_private", "1")', template)
		self.assertIn(
			'body.append("method", "retailedge.supplier_document_intake.upload_supplier_document")',
			template,
		)
		self.assertIn('body.append("purchase_order_name", purchaseOrder)', template)
		self.assertNotIn('body.append("supplier"', template)
		self.assertNotIn('body.append("company"', template)
		self.assertNotIn('body.append("doctype"', template)
		self.assertIn("Human review only — no automatic posting", template)
		self.assertNotIn("RetailEdge", template)
		self.assertNotIn("ProcessEdge", template)

	def test_recent_intakes_are_supplier_scoped_and_menu_is_additive(self):
		source = (APP_ROOT / "supplier_document_intake.py").read_text()
		setup = (APP_ROOT / "supplier_document_intake_setup.py").read_text()
		patches = (APP_ROOT / "patches.txt").read_text()
		self.assertIn('filters={"supplier": ["in", suppliers]}', source)
		self.assertIn('SUPPLIER_DOCUMENTS_ROUTE = "/supplier_documents"', setup)
		self.assertIn('"role": "Supplier"', setup)
		self.assertIn("settings.append(", setup)
		self.assertNotIn('settings.set("menu"', setup)
		self.assertIn("retailedge.patches.install_supplier_document_intake_menu", patches)


if __name__ == "__main__":
	unittest.main()
