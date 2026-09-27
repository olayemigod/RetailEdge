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
			'"doctype": "POS Invoice"',
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

	def test_share_defaults_use_document_company_not_product_brand(self):
		source = self.read("document_output.py")
		for contract in (
			"def _default_share_copy",
			'company = str(summary.get("company") or "").strip()',
			'"default_email_subject": share_copy["subject"]',
			'"default_email_message": share_copy["message"]',
			'"visible_identity": "document_company_and_letterhead"',
			'identity = company or _("Your supplier")',
		):
			self.assertIn(contract, source)
		self.assertNotIn("from RetailEdge", source)
		self.assertNotIn("from ProcessEdge", source)
		self.assertNotIn("secure RetailEdge", source)

	def test_preview_pdf_and_email_share_one_request_scoped_render_contract(self):
		source = self.read("document_output.py")
		for contract in (
			"def _output_render_options(",
			"frappe.flags.retailedge_output_options",
			"def _render_document(",
			"render_document_preview",
			"show_logo: int = 1",
			"include_qr: int = 0",
			"no_letterhead: int = 1",
			"pdf = _render_document(",
		):
			self.assertIn(contract, source)

	def test_email_readiness_is_checked_before_queueing(self):
		source = self.read("document_output.py")
		component = self.read("public/js/document_output_sharing/DocumentOutputSharing.vue")
		for contract in (
			"EmailAccount.find_default_outgoing()",
			'"email_configured": _outgoing_email_ready()',
			"if not _outgoing_email_ready():",
			"frappe.OutgoingEmailError",
		):
			self.assertIn(contract, source)
		for contract in (
			"this.details?.email_configured",
			"Outgoing email is not configured.",
			'{{ sendingEmail ? "Queueing..." : "Email PDF" }}',
			"this.sendingEmail = false;",
		):
			self.assertIn(contract, component)

	def test_output_page_is_preview_driven_and_letterhead_defaults_off(self):
		component = self.read("public/js/document_output_sharing/DocumentOutputSharing.vue")
		for contract in (
			'PREVIEW_METHOD = "retailedge.document_output.render_document_preview"',
			'ref="documentPreview"',
			':srcdoc="previewHtml"',
			'this.useLetterhead = Boolean(this.details.default_use_letterhead);',
			"useLetterhead: false",
			"showLogo: true",
			"includeQr: false",
			"Include company logo",
			"Include document QR",
			"Download PDF",
		):
			self.assertIn(contract, component)
		self.assertNotIn("/printview?", component)


	def test_whatsapp_is_user_initiated_without_public_document_link(self):
		source = self.read("document_output.py")
		for contract in (
			"get_whatsapp_handoff",
			'"requires_manual_attachment": True',
			'"public_pdf_link": False',
			'"whatsapp": "user_initiated_handoff"',
			'"company": company',
		):
			self.assertIn(contract, source)
		self.assertNotIn("graph.facebook.com", source)
		self.assertNotIn("api.whatsapp", source)

	def test_context_uses_frappe_v16_fullname_helper(self):
		source = self.read("document_output.py")
		self.assertIn("from frappe.utils.user import get_user_fullname", source)
		self.assertIn("get_user_fullname(frappe.session.user)", source)
		self.assertNotIn("frappe.get_user().get_fullname()", source)


if __name__ == "__main__":
	unittest.main()
