from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalSalesOrder(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_standalone_sales_order_is_draft_only_and_server_priced(self):
		source = self.read("professional_sales_order.py")
		for contract in (
			"create_professional_sales_order_draft",
			'frappe.new_doc("Sales Order")',
			"resolve_price_list_context",
			"resolve_sales_item_pricing",
			'"delivery_date": delivery_date',
			"doc.insert()",
			"_apply_shipping_rule_to_draft(doc)",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"doc.submit()",
			"ignore_permissions=True",
			"frappe.db.commit",
			"frappe.db.set_value",
		):
			self.assertNotIn(forbidden, source)

	def test_delivery_date_cannot_precede_order_date(self):
		source = self.read("professional_sales_order.py")
		self.assertIn("delivery_date < transaction_date", source)
		self.assertIn("Delivery Date cannot be before the Order Date.", source)

	def test_quotation_to_order_uses_erpnext_native_mapper(self):
		source = self.read("professional_sales_order.py")
		for contract in (
			"make_sales_order as erpnext_make_sales_order",
			"target = erpnext_make_sales_order(source.name)",
			"source.docstatus != 1",
			'quotation_to") or "") != "Customer"',
			"target.docstatus != 0",
			"target.insert()",
		):
			self.assertIn(contract, source)

	def test_quotation_to_order_reuses_one_exact_source_draft(self):
		source = self.read("professional_sales_order.py")
		for contract in (
			"def _lock_quotation",
			"FOR UPDATE",
			"def _existing_draft_sales_order_for_quotation",
			"item.prevdoc_docname = %s",
			"Multiple draft Sales Orders already reference Quotation",
			"linked_quotations != {quotation}",
			'"existing": True',
			'"existing": False',
		):
			self.assertIn(contract, source)

	def test_direct_quotation_invoice_blocks_parallel_sales_order_path(self):
		source = self.read("professional_sales_order.py")
		self.assertIn("get_quotation_conversion", source)
		self.assertIn("already owns Sales Invoice", source)
		self.assertIn("instead of creating a parallel Sales Order", source)

	def test_mapped_order_supplies_required_header_and_item_delivery_dates(self):
		source = self.read("professional_sales_order.py")
		for contract in (
			"delivery_date = getdate(target.get(\"delivery_date\")",
			"target.delivery_date = delivery_date",
			'item.meta.has_field("delivery_date")',
			"item.delivery_date = delivery_date",
		):
			self.assertIn(contract, source)

	def test_mapping_never_mutates_submitted_quotation(self):
		source = self.read("professional_sales_order.py")
		for forbidden in (
			"source.save(",
			"source.submit(",
			"source.cancel(",
			"source.db_set(",
			"frappe.db.set_value(\"Quotation\"",
			"ignore_permissions=True",
		):
			self.assertNotIn(forbidden, source)
		self.assertIn("The submitted source is never changed here.", source)

	def test_mapped_order_checks_operating_company_and_branch(self):
		source = self.read("professional_sales_order.py")
		for contract in (
			"get_operating_context",
			"_validate_stored_operational_branch",
			"Change Operating Context before creating its Sales Order.",
			"does not match the current Operating Branch.",
		):
			self.assertIn(contract, source)

	def test_quotation_context_is_preserved_on_mapped_order_draft(self):
		source = self.read("professional_sales_order.py")
		for contract in (
			"_preserve_source_quotation_context(source, target)",
			'source.get("branch") or source.get("retailedge_branch")',
			"_validate_stored_operational_branch(",
			"mapped Sales Order Company does not match the submitted Quotation",
			"mapped Sales Order Branch does not match the submitted Quotation Branch",
			"_set_branch_if_supported(target, source_branch)",
		):
			self.assertIn(contract, source)

	def test_quotation_guided_path_preserves_retailedge_branch_truth(self):
		source = self.read("professional_quotation.py")
		for contract in (
			"apply_transaction_branch_attribution",
			'doc.meta.has_field("retailedge_branch")',
			"doc.retailedge_branch = branch",
			"_set_quotation_branch(doc, branch)",
		):
			self.assertIn(contract, source)


if __name__ == "__main__":
	unittest.main()
