from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalSellingSmartForm(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_server_searches_are_context_filtered_and_bounded(self):
		source = self.read("professional_selling.py")
		for contract in (
			"MAX_LINK_RESULTS = 20",
			"search_professional_selling_options",
			'"is_sales_item": 1',
			'"is_group": 0',
			'"disabled": 0',
			'"shipping_rule_type": "Selling"',
			'"company": company',
			"get_user_allowed_branches",
			"validate_user_branch_access",
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all", source)

	def test_item_pricing_is_server_authoritative(self):
		source = self.read("professional_selling.py")
		for contract in (
			"get_professional_selling_item_pricing",
			"resolve_sales_item_pricing",
			"Select a Customer before pricing items.",
			"_assert_read(\"Customer\", customer)",
			"_assert_read(\"Item\", item_code)",
		):
			self.assertIn(contract, source)

	def test_quotation_editor_cascades_branch_and_stock_location(self):
		component = self.read("public/js/professional_selling/ProfessionalQuotationDialog.vue")
		for contract in (
			"EdgeLinkField",
			"EdgeChildTable",
			"resolveBranchWarehouse",
			'preference: "sales"',
			"searchShippingRule",
			"searchLineLink",
			"loadItemPricing",
			"refreshAllItemPricing",
		):
			self.assertIn(contract, component)
		self.assertIn("Stock Location", component)
		self.assertNotIn("Warehouse", component)

	def test_quotation_editor_is_draft_only_with_native_fallback(self):
		component = self.read("public/js/professional_selling/ProfessionalQuotationDialog.vue")
		workspace = self.read("public/js/professional_selling/ProfessionalSelling.vue")
		for contract in (
			"Save Draft",
			"create_professional_quotation_draft",
			"Open Full Form",
		):
			self.assertIn(contract, component)
		self.assertIn("Guided Quotation", workspace)
		self.assertIn("ProfessionalQuotationDialog", workspace)
		self.assertNotIn("submit", component.lower())


if __name__ == "__main__":
	unittest.main()
