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
	_format_values,
	get_preferred_print_format,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalPrintFormats(unittest.TestCase):
	def test_professional_catalog_uses_neutral_user_facing_names(self):
		catalog = {row["doctype"]: row["name"] for row in PROFESSIONAL_PRINT_FORMATS}
		self.assertEqual(
			catalog,
			{
				"Quotation": "Professional Quotation",
				"Sales Order": "Professional Sales Order",
				"Delivery Note": "Professional Delivery Note",
				"Sales Invoice": "Professional Sales Invoice",
			},
		)
		for doctype, name in catalog.items():
			self.assertEqual(get_preferred_print_format(doctype), name)
			self.assertNotIn("RetailEdge", name)

	def test_receipt_catalog_covers_sales_and_pos_in_80mm_and_58mm(self):
		catalog = {(row["doctype"], row["kind"]): row["name"] for row in RECEIPT_PRINT_FORMATS}
		self.assertEqual(catalog[("Sales Invoice", "receipt-80")], "Sales Receipt 80mm")
		self.assertEqual(catalog[("Sales Invoice", "receipt-58")], "Sales Receipt 58mm")
		self.assertEqual(catalog[("POS Invoice", "receipt-80")], "POS Receipt 80mm")
		self.assertEqual(catalog[("POS Invoice", "receipt-58")], "POS Receipt 58mm")
		for name in catalog.values():
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
			self.assertNotIn("ProcessEdge Solutions", values["html"])
			self.assertNotIn("processedge.com.ng", values["html"])
			self.assertNotIn(">RetailEdge<", values["html"])
			self.assertNotIn("valuation_rate", values["html"])
			self.assertNotIn("incoming_rate", values["html"])
			self.assertNotIn("buying_rate", values["html"])
			self.assertNotIn("gross_profit", values["html"])

	def test_receipts_use_client_company_as_visible_identity(self):
		for spec in RECEIPT_PRINT_FORMATS:
			html = _format_values(spec)["html"]
			self.assertIn('{{ doc.get("company") or "" }}', html)
			self.assertNotIn(">RetailEdge<", html)
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

	def test_document_format_uses_native_totals_not_recalculated_accounting(self):
		html = _format_values(PROFESSIONAL_PRINT_FORMATS[0])["html"]
		self.assertIn('doc.get_formatted("net_total")', html)
		self.assertIn('doc.get_formatted("grand_total")', html)
		self.assertIn('doc.get_formatted("total_taxes_and_charges")', html)
		self.assertNotIn("shipping_amount +", html)
		self.assertNotIn("grand_total =", html)

	@patch("retailedge.document_output._permission", return_value=True)
	@patch("retailedge.document_output.frappe.get_list")
	def test_document_output_prioritizes_professional_format_without_hiding_others(self, mock_get_list, _mock_permission):
		mock_get_list.return_value = [
			frappe._dict(name="Customer Custom Invoice"),
			frappe._dict(name="Professional Sales Invoice"),
			frappe._dict(name="Sales Receipt 80mm"),
		]
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats[0], "Professional Sales Invoice")
		self.assertIn("Standard", formats)
		self.assertIn("Customer Custom Invoice", formats)
		self.assertIn("Sales Receipt 80mm", formats)

	@patch("retailedge.document_output._permission", return_value=True)
	@patch("retailedge.document_output.frappe.get_list")
	def test_document_output_falls_back_to_standard_when_preferred_format_missing(self, mock_get_list, _mock_permission):
		mock_get_list.return_value = [frappe._dict(name="Customer Custom Invoice")]
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats, ["Standard", "Customer Custom Invoice"])

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
		self.assertIn('product="Retail"', component)
		self.assertNotIn('product="RetailEdge"', component)
		self.assertNotIn("RetailEdge does not publish", component)

	def test_installer_is_registered_and_collision_safe(self):
		patches = (APP_ROOT / "patches.txt").read_text()
		source = (APP_ROOT / "professional_print_formats.py").read_text()
		self.assertIn("retailedge.patches.install_professional_print_formats", patches)
		self.assertIn("if not owned:", source)
		self.assertIn("Skipping non-managed Print Format name collision", source)
		self.assertNotIn("frappe.db.delete", source)
		self.assertNotIn("delete_doc", source)
		self.assertNotIn("ignore_permissions=True", source)


if __name__ == "__main__":
	unittest.main()
