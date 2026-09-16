from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalDelivery(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_delivery_uses_erpnext_v16_native_sales_order_mapper(self):
		source = self.read("professional_delivery.py")
		for contract in (
			"from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note as erpnext_make_delivery_note",
			"target = erpnext_make_delivery_note(source.name)",
			"source.docstatus != 1",
			'"Fully Delivered"',
			"target.docstatus != 0",
			"not target.get(\"items\")",
			"target.insert()",
		):
			self.assertIn(contract, source)

	def test_sales_invoice_to_delivery_uses_erpnext_native_mapper_and_blocks_double_stock(self):
		source = self.read("professional_delivery.py")
		for contract in (
			"erpnext_make_delivery_note_from_invoice",
			"def create_delivery_note_from_sales_invoice(",
			"source.docstatus != 1",
			'source.get("is_return")',
			'source.get("update_stock")',
			"duplicate stock movement",
			"target = erpnext_make_delivery_note_from_invoice(source.name)",
			"not target.get(\"items\")",
			"target.insert()",
		):
			self.assertIn(contract, source)
		self.assertNotIn("target.submit()", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_sales_invoice_delivery_creation_reuses_existing_draft(self):
		source = self.read("professional_delivery.py")
		for contract in (
			"def _lock_sales_invoice",
			"FOR UPDATE",
			"def _existing_draft_delivery_for_invoice",
			"item.against_sales_invoice = %s",
			"dn.docstatus = 0",
			'"existing": existing',
			"if existing:",
		):
			self.assertIn(contract, source)

	def test_delivery_never_mutates_or_submits_source_or_target(self):
		source = self.read("professional_delivery.py")
		for forbidden in (
			"source.save(",
			"source.submit(",
			"source.cancel(",
			"source.db_set(",
			"target.submit(",
			"frappe.db.commit",
			"ignore_permissions=True",
			"frappe.db.set_value(\"Sales Order\"",
		):
			self.assertNotIn(forbidden, source)
		self.assertIn("No stock ledger entry is created until normal ERPNext", source)

	def test_delivery_validates_company_branch_and_each_stock_location(self):
		source = self.read("professional_delivery.py")
		for contract in (
			"get_operating_context",
			"_validate_stored_operational_branch",
			"resolve_branch_from_warehouse",
			"Stock Location",
			"multiple Branches",
			"current Operating Branch",
		):
			self.assertIn(contract, source)

	def test_delivery_source_search_is_submitted_and_remaining_only(self):
		source = self.read("professional_selling_sources.py")
		for contract in (
			'if target == "delivery-note"',
			'"docstatus": 1',
			'"delivery_status": ["!=", "Fully Delivered"]',
			'reference_doctype="Delivery Note"',
			'link_fieldname="against_sales_order"',
		):
			self.assertIn(contract, source)

	def test_delivery_ui_exposes_guided_mapping_and_native_fallback(self):
		component = self.read("public/js/professional_selling/ProfessionalDeliveryDialog.vue")
		workspace = self.read("public/js/professional_selling/ProfessionalSelling.vue")
		for contract in (
			"EdgeModal",
			"EdgeLinkField",
			"Submitted Sales Order",
			"Create Delivery Draft",
			"create_delivery_note_from_sales_order",
			"never changes the submitted Sales Order",
		):
			self.assertIn(contract, component)
		for contract in (
			"ProfessionalDeliveryDialog",
			"Create Delivery",
			"deliveryOpen",
		):
			self.assertIn(contract, workspace)


if __name__ == "__main__":
	unittest.main()
