from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalQuotation(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_quotation_is_draft_only_and_server_priced(self):
		source = self.read("professional_quotation.py")
		for contract in (
			"create_professional_quotation_draft",
			'frappe.new_doc("Quotation")',
			'doc.quotation_to = "Customer"',
			"resolve_price_list_context",
			"resolve_sales_item_pricing",
			"doc.insert()",
			'"docstatus": doc.docstatus',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"doc.submit()",
			"ignore_permissions=True",
			"frappe.db.commit",
			"frappe.db.set_value",
		):
			self.assertNotIn(forbidden, source)

	def test_shipping_rule_is_erpnext_native_and_company_safe(self):
		source = self.read("professional_quotation.py")
		for contract in (
			'"Shipping Rule"',
			'"disabled"',
			'"shipping_rule_type"',
			'!= "Selling"',
			"does not belong to Company",
			"doc.apply_shipping_rule()",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"shipping_charge_ledger",
			"delivery_charge_ledger",
			"doc.taxes.append",
		):
			self.assertNotIn(forbidden, source)

	def test_item_input_is_bounded_and_positive(self):
		source = self.read("professional_quotation.py")
		self.assertIn("MAX_ITEMS = 50", source)
		self.assertIn("len(items) > MAX_ITEMS", source)
		self.assertIn("qty <= 0", source)
		self.assertIn("rate < 0", source)

	def test_valid_till_cannot_precede_transaction_date(self):
		source = self.read("professional_quotation.py")
		self.assertIn("valid_till < transaction_date", source)
		self.assertIn("Valid Till cannot be before the Quotation Date.", source)


if __name__ == "__main__":
	unittest.main()
