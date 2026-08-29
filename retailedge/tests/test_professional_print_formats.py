from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.document_output import _available_print_formats
from retailedge.professional_print_formats import (
	MANAGED_MARKER,
	PROFESSIONAL_PRINT_FORMATS,
	_format_values,
	get_preferred_print_format,
)


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalPrintFormats(unittest.TestCase):
	def test_catalog_covers_four_customer_sales_documents(self):
		catalog = {row["doctype"]: row["name"] for row in PROFESSIONAL_PRINT_FORMATS}
		self.assertEqual(
			catalog,
			{
				"Quotation": "RetailEdge Professional Quotation",
				"Sales Order": "RetailEdge Professional Sales Order",
				"Delivery Note": "RetailEdge Professional Delivery Note",
				"Sales Invoice": "RetailEdge Professional Sales Invoice",
			},
		)
		for doctype, name in catalog.items():
			self.assertEqual(get_preferred_print_format(doctype), name)

	def test_format_values_are_custom_jinja_and_white_label_safe(self):
		for spec in PROFESSIONAL_PRINT_FORMATS:
			values = _format_values(spec)
			self.assertEqual(values["print_format_for"], "DocType")
			self.assertEqual(values["doc_type"], spec["doctype"])
			self.assertEqual(values["module"], "RetailEdge")
			self.assertEqual(values["standard"], "No")
			self.assertEqual(values["custom_format"], 1)
			self.assertEqual(values["print_format_type"], "Jinja")
			self.assertIn(MANAGED_MARKER, values["html"])
			self.assertIn(spec["heading"], values["html"])
			self.assertIn('doc.get("company")', values["html"])
			self.assertIn('doc.get("shipping_rule")', values["html"])
			self.assertIn('doc.get("total_taxes_and_charges")', values["html"])
			self.assertIn('doc.get("payment_schedule")', values["html"])
			self.assertIn('doc.get("terms")', values["html"])
			self.assertNotIn("ProcessEdge Solutions", values["html"])
			self.assertNotIn("processedge.com.ng", values["html"])
			self.assertNotIn("RetailEdge", values["html"])
			self.assertNotIn("valuation_rate", values["html"])
			self.assertNotIn("incoming_rate", values["html"])
			self.assertNotIn("buying_rate", values["html"])
			self.assertNotIn("gross_profit", values["html"])

	def test_format_uses_native_totals_instead_of_recalculating_delivery_or_tax(self):
		html = _format_values(PROFESSIONAL_PRINT_FORMATS[0])["html"]
		self.assertIn('doc.get_formatted("net_total")', html)
		self.assertIn('doc.get_formatted("grand_total")', html)
		self.assertIn('doc.get_formatted("total_taxes_and_charges")', html)
		self.assertNotIn("shipping_amount +", html)
		self.assertNotIn("grand_total =", html)

	@patch("retailedge.document_output._permission", return_value=True)
	@patch("retailedge.document_output.frappe.get_list")
	def test_document_output_prioritizes_owned_format_without_hiding_standard_or_other_formats(self, mock_get_list, _mock_permission):
		mock_get_list.return_value = [
			frappe._dict(name="Customer Custom Invoice"),
			frappe._dict(name="RetailEdge Professional Sales Invoice"),
		]
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats[0], "RetailEdge Professional Sales Invoice")
		self.assertIn("Standard", formats)
		self.assertIn("Customer Custom Invoice", formats)

	@patch("retailedge.document_output._permission", return_value=True)
	@patch("retailedge.document_output.frappe.get_list")
	def test_document_output_falls_back_to_standard_when_managed_format_is_not_installed(self, mock_get_list, _mock_permission):
		mock_get_list.return_value = [frappe._dict(name="Customer Custom Invoice")]
		formats = _available_print_formats("Sales Invoice")
		self.assertEqual(formats[0], "Standard")
		self.assertEqual(formats, ["Standard", "Customer Custom Invoice"])

	def test_installer_is_registered_as_post_model_sync_patch_and_has_collision_guard(self):
		patches = (APP_ROOT / "patches.txt").read_text()
		source = (APP_ROOT / "professional_print_formats.py").read_text()
		self.assertIn("retailedge.patches.install_professional_print_formats", patches)
		self.assertIn("if not owned:", source)
		self.assertIn("Skipping non-RetailEdge Print Format name collision", source)
		self.assertNotIn("frappe.db.delete", source)
		self.assertNotIn("delete_doc", source)
		self.assertNotIn("ignore_permissions=True", source)


if __name__ == "__main__":
	unittest.main()
