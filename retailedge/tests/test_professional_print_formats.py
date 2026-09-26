from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.document_output import _available_print_formats
from retailedge.professional_print_formats import (
	MANAGED_MARKER,
	MANAGED_PRINT_FORMATS,
	PROFESSIONAL_PRINT_FORMATS,
	RECEIPT_PRINT_FORMATS,
	SALES_INVOICE_STYLE_FORMATS,
	_format_values,
	get_preferred_print_format,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalPrintFormats(unittest.TestCase):
	def test_professional_catalog_uses_explicit_pedge_names(self):
		catalog = {row["doctype"]: row["name"] for row in PROFESSIONAL_PRINT_FORMATS}
		self.assertEqual(
			catalog,
			{
				"Quotation": "PEdge Professional Quotation",
				"Sales Order": "PEdge Professional Sales Order",
				"Delivery Note": "PEdge Professional Delivery Note",
				"Sales Invoice": "PEdge Professional Sales Invoice",
			},
		)
		for doctype, name in catalog.items():
			self.assertEqual(get_preferred_print_format(doctype), name)
			self.assertTrue(name.startswith("PEdge "))
			self.assertNotIn("RetailEdge", name)

	def test_sales_invoice_template_pack_exposes_five_distinct_selectable_styles(self):
		names = [row["name"] for row in SALES_INVOICE_STYLE_FORMATS]
		self.assertEqual(
			names,
			["PEdge Invoice Classic", "PEdge Invoice Modern", "PEdge Invoice Compact", "PEdge Invoice Minimal", "PEdge Invoice Executive"],
		)
		self.assertEqual(len({ _format_values(row)["css"] for row in SALES_INVOICE_STYLE_FORMATS }), 5)
		for row in SALES_INVOICE_STYLE_FORMATS:
			self.assertEqual(row["doctype"], "Sales Invoice")
			self.assertNotIn("RetailEdge", row["name"])
			self.assertTrue(row["name"].startswith("PEdge "))

	def test_sales_invoice_has_at_least_five_document_templates_plus_thermal_receipts(self):
		document_templates = [
			row for row in MANAGED_PRINT_FORMATS
			if row["doctype"] == "Sales Invoice" and not row["kind"].startswith("receipt-")
		]
		receipts = [
			row for row in MANAGED_PRINT_FORMATS
			if row["doctype"] == "Sales Invoice" and row["kind"].startswith("receipt-")
		]
		self.assertGreaterEqual(len(document_templates), 5)
		self.assertEqual({row["kind"] for row in receipts}, {"receipt-80", "receipt-58"})

	def test_receipt_catalog_covers_sales_and_pos_in_80mm_and_58mm(self):
		catalog = {(row["doctype"], row["kind"]): row["name"] for row in RECEIPT_PRINT_FORMATS}
		self.assertEqual(catalog[("Sales Invoice", "receipt-80")], "PEdge Sales Receipt 80mm")
		self.assertEqual(catalog[("Sales Invoice", "receipt-58")], "PEdge Sales Receipt 58mm")
		self.assertEqual(catalog[("POS Invoice", "receipt-80")], "PEdge POS Receipt 80mm")
		self.assertEqual(catalog[("POS Invoice", "receipt-58")], "PEdge POS Receipt 58mm")
		for name in catalog.values():
			self.assertTrue(name.startswith("PEdge "))
			self.assertNotIn("RetailEdge", name)

	def test_all_managed_formats_are_white_label_and_customer_safe(self):
		for spec in MANAGED_PRINT_FORMATS:
			values = _format_values(spec)
			self.assertEqual(values["print_format_for"], "DocType")
			self.assertEqual(values["doc_type"], spec["doctype"])
			self.assertEqual(values["module"], "RetailEdge")  # internal module identity only
			self.assertEqual(values["standard"], "No")
			self.assertEqual(values["custom_format"], 1)
			self.assertEqual(values["print_format_type"], "Jinja")
			self.assertIn(MANAGED_MARKER, values["html"])
			self.assertNotIn("retailedge-managed-print-format", values["html"])
			self.assertNotIn("ProcessEdge Solutions", values["html"])
			self.assertNotIn("processedge.com.ng", values["html"])
			self.assertNotIn("retailedge", values["html"].lower())
			self.assertNotIn("processedge", values["html"].lower())
			self.assertNotIn("valuation_rate", values["html"])
			self.assertNotIn("incoming_rate", values["html"])
			self.assertNotIn("buying_rate", values["html"])
			self.assertNotIn("gross_profit", values["html"])

	def test_receipts_use_client_company_profile_as_visible_identity(self):
		for spec in RECEIPT_PRINT_FORMATS:
			html = _format_values(spec)["html"]
			self.assertIn("get_business_print_context(doc)", html)
			self.assertIn("output.display_name or output.company", html)
			self.assertIn("output.show_logo and output.logo", html)
			self.assertNotIn("retailedge", html.lower())
			self.assertNotIn("ProcessEdge Solutions", html)
			self.assertNotIn("processedge.com.ng", html)
			self.assertNotIn("Powered by", html)

	def test_receipts_use_thermal_page_widths_and_no_page_number(self):
		for spec in RECEIPT_PRINT_FORMATS:
			values = _format_values(spec)
			self.assertEqual(values["page_number"], "Hide")
			self.assertEqual(values["margin_left"], 3)
			self.assertEqual(values["margin_right"], 3)
			if spec["kind"] == "receipt-80":
				self.assertIn("80mm", values["css"])
			elif spec["kind"] == "receipt-58":
				self.assertIn("58mm", values["css"])
			self.assertIn("Thank you for your business.", values["html"])
			self.assertIn('doc.get_formatted("grand_total")', values["html"])
			self.assertIn('class="receipt-items"', values["html"])
			self.assertIn("Unit Price", values["html"])
			self.assertIn("output.include_qr and output.qr_data_uri", values["html"])
			self.assertIn('class="receipt-logo"', values["html"])

	def test_all_managed_templates_support_company_logo_and_optional_document_qr(self):
		for spec in MANAGED_PRINT_FORMATS:
			html = _format_values(spec)["html"]
			self.assertIn("get_business_print_context(doc)", html)
			self.assertIn("output.show_logo and output.logo", html)
			self.assertIn("output.include_qr and output.qr_data_uri", html)
			self.assertNotIn("RetailEdge Payment Verification", html)

	def test_formal_templates_follow_logo_left_document_title_right_reference_layout(self):
		html = _format_values(PROFESSIONAL_PRINT_FORMATS[3])["html"]
		css = _format_values(PROFESSIONAL_PRINT_FORMATS[3])["css"]
		for contract in (
			'class="pe-brand"',
			'class="pe-logo"',
			'class="pe-title-block"',
			'class="pe-document-no"',
			'class="pe-party-grid"',
			'class="pe-items"',
			'class="pe-summary"',
			'class="pe-balance"',
		):
			self.assertIn(contract, html)
		self.assertIn(".pe-title-block{text-align:right", css)
		self.assertIn(".pe-items th{", css)


	def test_document_format_uses_native_totals_not_recalculated_accounting(self):
		html = _format_values(PROFESSIONAL_PRINT_FORMATS[0])["html"]
		self.assertIn('doc.get_formatted("net_total")', html)
		self.assertIn('doc.get_formatted("grand_total")', html)
		self.assertIn('doc.get_formatted("total_taxes_and_charges")', html)
		self.assertNotIn("shipping_amount +", html)
		self.assertNotIn("grand_total =", html)

	@patch("retailedge.document_output._permission", return_value=True)
	@patch("retailedge.document_output.frappe.db.exists", return_value=False)
	@patch("retailedge.document_output.frappe.get_list")
	def test_document_output_prioritizes_professional_format_without_hiding_others(self, mock_get_list, _mock_exists, _mock_permission):
		mock_get_list.return_value = [
			frappe._dict(name="Customer Custom Invoice"),
			frappe._dict(name="PEdge Professional Sales Invoice"),
			frappe._dict(name="PEdge Sales Receipt 80mm"),
		]
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats[0], "PEdge Professional Sales Invoice")
		self.assertIn("Standard", formats)
		self.assertIn("Customer Custom Invoice", formats)
		self.assertIn("PEdge Sales Receipt 80mm", formats)

	@patch("retailedge.document_output._permission", return_value=True)
	@patch("retailedge.document_output.frappe.db.exists", return_value=False)
	@patch("retailedge.document_output.frappe.get_list")
	def test_document_output_falls_back_to_standard_when_preferred_format_missing(self, mock_get_list, _mock_exists, _mock_permission):
		mock_get_list.return_value = [frappe._dict(name="Customer Custom Invoice")]
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats, ["Standard", "Customer Custom Invoice"])

	@patch("retailedge.document_output._permission", return_value=False)
	@patch("retailedge.document_output.frappe.db.get_value")
	@patch("retailedge.document_output.frappe.db.exists")
	def test_managed_invoice_templates_remain_selectable_without_print_format_master_access(self, mock_exists, mock_get_value, _mock_permission):
		managed_names = {row["name"] for row in MANAGED_PRINT_FORMATS if row["doctype"] == "Sales Invoice"}
		mock_exists.side_effect = lambda doctype, name=None: doctype == "Print Format" and name in managed_names
		mock_get_value.return_value = frappe._dict(disabled=0, html=MANAGED_MARKER)
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats[0], "PEdge Professional Sales Invoice")
		for name in managed_names:
			self.assertIn(name, formats)


	def test_output_registry_exposes_pos_receipt_without_product_brand_label(self):
		source = (APP_ROOT / "document_output.py").read_text()
		self.assertIn('"key": "pos-receipt"', source)
		self.assertIn('"doctype": "POS Invoice"', source)
		self.assertIn('"label": "POS Receipt"', source)
		self.assertNotIn("secure RetailEdge download", source)

	def test_output_workspace_is_edgesuite_ui_strict_and_visible_copy_is_neutral(self):
		component = (APP_ROOT / "public" / "js" / "document_output_sharing" / "DocumentOutputSharing.vue").read_text()
		for name in ("EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeStatusBadge"):
			self.assertIn(name, component)
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertNotIn("window.EdgeUI", component)
		self.assertIn('product="retailedge"', component)
		self.assertNotIn('product="RetailEdge"', component)
		self.assertNotIn('product="Retail"', component)
		self.assertNotIn("RetailEdge does not publish", component)

	def test_output_workspace_consumes_server_company_identity_and_recommended_format(self):
		component = (APP_ROOT / "public" / "js" / "document_output_sharing" / "DocumentOutputSharing.vue").read_text()
		self.assertIn("this.details.recommended_print_format", component)
		self.assertIn("this.details.default_email_subject", component)
		self.assertIn("this.details.default_email_message", component)
		self.assertIn("this.details.default_use_letterhead", component)
		self.assertIn("this.details.default_show_logo", component)
		self.assertIn("this.details.default_include_qr", component)
		self.assertNotIn("Please find attached ${this.selectedDefinition", component)

	def test_installer_is_registered_and_collision_safe(self):
		patches = (APP_ROOT / "patches.txt").read_text()
		source = (APP_ROOT / "professional_print_formats.py").read_text()
		self.assertIn("retailedge.patches.install_professional_print_formats", patches)
		self.assertIn("retailedge.patches.install_output_print_template_pack_v3", patches)
		self.assertIn("retailedge.patches.install_output_print_template_pack_v4", patches)
		self.assertIn("retailedge.patches.install_pedge_print_formats_v5", patches)
		self.assertIn("if not owned:", source)
		self.assertIn("Skipping non-managed Print Format name collision", source)
		self.assertIn("LEGACY_PRINT_FORMAT_ALIASES", source)
		self.assertIn("Skipping non-managed legacy Print Format collision", source)
		self.assertIn("legacy_doc.disabled = 1", source)
		self.assertNotIn("frappe.db.delete", source)
		self.assertNotIn("delete_doc", source)
		self.assertNotIn("ignore_permissions=True", source)


if __name__ == "__main__":
	unittest.main()
