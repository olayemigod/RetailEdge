from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalSalesInvoice(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_standalone_invoice_reuses_guarded_engine_and_shipping_rule(self):
		source = self.read("professional_sales_invoice.py")
		for contract in (
			"create_simple_sales_invoice_draft",
			"create_professional_sales_invoice_draft",
			"_validate_shipping_rule",
			"doc.apply_shipping_rule()",
			"doc.docstatus != 0",
		):
			self.assertIn(contract, source)

	def test_sales_order_and_delivery_use_erpnext_native_invoice_mappers(self):
		source = self.read("professional_sales_invoice.py")
		for contract in (
			"make_sales_invoice as erpnext_make_sales_invoice_from_order",
			"make_sales_invoice as erpnext_make_sales_invoice_from_delivery",
			"create_sales_invoice_from_sales_order",
			"create_sales_invoice_from_delivery_note",
			"target = mapper(source.name)",
			"target.insert()",
		):
			self.assertIn(contract, source)

	def test_quotation_can_invoice_directly_without_hidden_sales_order(self):
		source = self.read("professional_sales_invoice.py")
		for contract in (
			"create_sales_invoice_from_quotation",
			"create_simple_sales_invoice_draft",
			"_copy_quotation_commercial_terms(source, target)",
			"no hidden Sales Order is created",
		):
			self.assertIn(contract, source)
		self.assertNotIn("erpnext_make_sales_order", source)

	def test_submitted_sources_are_never_mutated_or_submitted(self):
		source = self.read("professional_sales_invoice.py")
		for forbidden in (
			"source.save(",
			"source.submit(",
			"source.cancel(",
			"source.db_set(",
			"target.submit(",
			"ignore_permissions=True",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, source)

	def test_invoice_mapping_revalidates_company_branch_and_stock_locations(self):
		source = self.read("professional_sales_invoice.py")
		for contract in (
			"get_operating_context",
			"validate_user_branch_access",
			"resolve_branch_from_warehouse",
			"Stock Location",
			"multiple Branches",
			"mapped Sales Invoice Company does not match",
		):
			self.assertIn(contract, source)

	def test_invoice_ui_exposes_flexible_paths_and_no_submit_action(self):
		dialog = self.read("public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue")
		page = self.read("public/js/professional_selling/ProfessionalSelling.vue")
		for contract in (
			"New Invoice",
			"From Quotation",
			"From Sales Order",
			"From Delivery Note",
			"create_sales_invoice_from_quotation",
			"create_sales_invoice_from_sales_order",
			"create_sales_invoice_from_delivery_note",
			"Shipping Rule",
			"Stock Location",
		):
			self.assertIn(contract, dialog)
		self.assertIn("ProfessionalSalesInvoiceDialog", page)
		self.assertIn("Use the next document the business transaction requires", page)
		self.assertNotIn("Submit Invoice", dialog)
		self.assertNotIn("frappe.client.save", dialog)


if __name__ == "__main__":
	unittest.main()
