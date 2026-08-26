from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestDocumentOutput(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_registry_covers_customer_facing_sales_documents(self):
		source = self.read("document_output.py")
		for contract in (
			'"doctype": "Quotation"',
			'"doctype": "Sales Order"',
			'"doctype": "Delivery Note"',
			'"doctype": "Sales Invoice"',
			'"print_engine": "erpnext_native"',
			'"print_formats": "erpnext_native"',
			'"letterhead": "erpnext_native"',
		):
			self.assertIn(contract, source)

	def test_search_is_permission_aware_context_filtered_and_bounded(self):
		source = self.read("document_output.py")
		for contract in (
			"MAX_LINK_RESULTS = 20",
			"search_output_documents",
			"get_operating_context",
			"BRANCH_FIELD_CANDIDATES",
			"search_link(",
			"page_length=limit",
			'_permission(doctype, "read")',
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_pdf_uses_native_print_engine_and_remains_private(self):
		source = self.read("document_output.py")
		for contract in (
			"download_document_pdf",
			'_assert_document_permission(doctype, name, "print")',
			"_validate_print_format",
			"frappe.get_print(",
			"as_pdf=True",
			'frappe.local.response.type = "download"',
			'"public_pdf_links": False',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"is_private=0",
			"public/files",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)

	def test_email_uses_frappe_transport_and_document_permissions(self):
		source = self.read("document_output.py")
		for contract in (
			"send_document_email",
			'_assert_document_permission(doctype, name, "email")',
			"validate_email_address(recipient, throw=True)",
			"frappe.sendmail(",
			"reference_doctype=doctype",
			"reference_name=name",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"doc.save(",
			"doc.submit(",
			"frappe.db.set_value",
		):
			self.assertNotIn(forbidden, source)

	def test_whatsapp_is_user_initiated_without_public_document_link(self):
		source = self.read("document_output.py")
		for contract in (
			"get_whatsapp_handoff",
			'"requires_manual_attachment": True',
			'"public_pdf_link": False',
			'"whatsapp": "user_initiated_handoff"',
		):
			self.assertIn(contract, source)
		self.assertNotIn("graph.facebook.com", source)
		self.assertNotIn("api.whatsapp", source)


if __name__ == "__main__":
	unittest.main()
