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
			"validate_user_branch_access",
			"Change Operating Context before creating its Sales Order.",
			"does not match the current Operating Branch.",
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
