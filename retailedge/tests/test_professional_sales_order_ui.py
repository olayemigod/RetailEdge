from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestProfessionalSalesOrderUI(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_source_search_is_submitted_customer_company_scoped_and_bounded(self):
		source = self.read("professional_selling_sources.py")
		for contract in (
			"MAX_LINK_RESULTS",
			'"docstatus": 1',
			'"quotation_to": "Customer"',
			'"company": company',
			'"status": ["not in", ["Ordered", "Lost", "Cancelled", "Expired"]]',
			"page_length=limit",
			'reference_doctype="Sales Order"',
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all", source)

	def test_sales_order_editor_supports_new_and_native_quotation_mapping_modes(self):
		component = self.read("public/js/professional_selling/ProfessionalSalesOrderDialog.vue")
		for contract in (
			"New Order",
			"From Submitted Quotation",
			"searchSourceQuotation",
			"create_professional_sales_order_draft",
			"create_sales_order_from_quotation",
			"Create Draft from Quotation",
			"Save Draft",
		):
			self.assertIn(contract, component)
		# References to submitted source Quotations are required for native
		# mapping. What must stay absent is a submit action for the new order.
		self.assertNotIn(">Submit<", component)
		self.assertNotIn(">Submit Sales Order<", component)
		self.assertNotIn('@click="submit', component)

	def test_new_order_form_is_smart_and_edgesuite_based(self):
		component = self.read("public/js/professional_selling/ProfessionalSalesOrderDialog.vue")
		for contract in (
			"EdgeModal",
			"EdgeLinkField",
			"EdgeChildTable",
			"resolveBranchWarehouse",
			"Source Stock Location",
			"searchShippingRule",
			"loadItemPricing",
		):
			self.assertIn(contract, component)
		self.assertNotIn(">Warehouse<", component)

	def test_workspace_keeps_quote_and_order_together(self):
		workspace = self.read("public/js/professional_selling/ProfessionalSelling.vue")
		for contract in (
			"ProfessionalQuotationDialog",
			"ProfessionalSalesOrderDialog",
			"Guided Quotation",
			"Guided Sales Order",
			"salesOrderOpen",
		):
			self.assertIn(contract, workspace)


if __name__ == "__main__":
	unittest.main()
