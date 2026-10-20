from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.sales_commercial_preview import (
	_serialize_preview,
	_validate_manual_invoice_discount_against_promotions,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestSalesPricingProvenance(unittest.TestCase):
	@patch("retailedge.sales_commercial_preview.get_sales_commercial_term_capabilities", return_value={})
	def test_multi_item_preview_separates_promotion_rate_adjustment_and_line_discount(self, _mock_caps):
		doc = frappe._dict(
			company="RetailEdge Consulting",
			customer="CUST-001",
			currency="NGN",
			selling_price_list="Standard Selling",
			items=[
				frappe._dict(
					item_code="INVERTER",
					item_name="Inverter",
					qty=1,
					price_list_rate=200000,
					pricing_rules="Item Promo 5",
					discount_percentage=5,
					rate=190000,
					amount=190000,
					net_rate=190000,
					net_amount=190000,
				),
				frappe._dict(
					item_code="BATTERY",
					item_name="Battery",
					qty=1,
					price_list_rate=120000,
					discount_percentage=10,
					discount_amount=11500,
					rate_with_margin=115000,
					rate=103500,
					amount=103500,
					net_rate=103500,
					net_amount=103500,
				),
				frappe._dict(
					item_code="CABLE",
					item_name="Cable",
					qty=1,
					price_list_rate=30000,
					rate=30000,
					amount=30000,
					net_rate=30000,
					net_amount=30000,
				),
			],
			total=323500,
			net_total=323500,
			additional_discount_percentage=0,
			discount_amount=0,
			apply_discount_on="Grand Total",
			pricing_rules=[],
			taxes=[
				frappe._dict(
					description="VAT",
					rate=5,
					tax_amount=16175,
					tax_amount_after_discount_amount=16175,
					included_in_print_rate=0,
				),
			],
			total_taxes_and_charges=16175,
			rounding_adjustment=0,
			grand_total=339675,
			rounded_total=339675,
		)
		doc.flags = frappe._dict(
			retailedge_item_pricing_provenance=[
				{
					"price_list_rate": 200000,
					"automatic_rate": 190000,
					"entered_rate": 190000,
				},
				{
					"price_list_rate": 120000,
					"automatic_rate": 120000,
					"entered_rate": 115000,
				},
				{
					"price_list_rate": 30000,
					"automatic_rate": 30000,
					"entered_rate": 30000,
				},
			]
		)

		result = _serialize_preview(
			doc,
			branch="Lagos Island",
			pricing_context={"price_list": "Standard Selling", "currency": "NGN"},
		)

		self.assertEqual(result["price_list_value"], 350000)
		self.assertEqual(result["item_promotion_total"], 10000)
		self.assertEqual(result["selling_rate_adjustment_total"], -5000)
		self.assertEqual(result["line_discount_total"], 11500)
		self.assertEqual(result["subtotal"], 323500)
		self.assertEqual(result["items"][0]["item_promotion_percentage"], 5)
		self.assertEqual(result["items"][1]["selling_rate_adjustment"], -5000)
		self.assertEqual(result["items"][1]["line_discount_amount"], 11500)

	@patch("retailedge.sales_commercial_preview.get_sales_commercial_term_capabilities", return_value={})
	def test_transaction_pricing_rule_is_serialized_as_invoice_promotion(self, _mock_caps):
		doc = frappe._dict(
			company="RetailEdge Consulting",
			customer="CUST-001",
			currency="NGN",
			selling_price_list="Standard Selling",
			items=[frappe._dict(item_code="ITEM-001", qty=1, price_list_rate=200000, rate=200000, amount=200000)],
			total=200000,
			net_total=190000,
			additional_discount_percentage=5,
			discount_amount=10500,
			apply_discount_on="Grand Total",
			pricing_rules=[frappe._dict(pricing_rule="Spend 200K Promotion", rule_applied=1)],
			taxes=[
				frappe._dict(
					description="VAT",
					rate=5,
					tax_amount=10000,
					tax_amount_after_discount_amount=9500,
					included_in_print_rate=0,
				),
			],
			total_taxes_and_charges=9500,
			rounding_adjustment=0,
			grand_total=199500,
			rounded_total=199500,
		)
		doc.flags = frappe._dict()

		result = _serialize_preview(doc, branch="Ketu", pricing_context={"currency": "NGN"})

		self.assertEqual(result["invoice_adjustment_kind"], "promotion")
		self.assertEqual(result["invoice_promotion_amount"], 10500)
		self.assertEqual(result["invoice_discount_amount"], 0)
		self.assertEqual(result["tax_before_invoice_adjustment"], 10000)
		self.assertEqual(result["tax_after_invoice_adjustment"], 9500)
		self.assertEqual(result["gross_before_invoice_adjustment"], 210000)
		self.assertEqual(result["invoice_promotion_names"], ["Spend 200K Promotion"])

	@patch("retailedge.sales_commercial_preview.get_sales_commercial_term_capabilities", return_value={})
	def test_manual_invoice_discount_remains_distinct_without_transaction_rule(self, _mock_caps):
		doc = frappe._dict(
			company="RetailEdge Consulting",
			customer="CUST-001",
			currency="NGN",
			items=[frappe._dict(item_code="ITEM-001", qty=1, price_list_rate=200000, rate=200000, amount=200000)],
			total=200000,
			net_total=190000,
			additional_discount_percentage=5,
			discount_amount=10000,
			apply_discount_on="Net Total",
			pricing_rules=[],
			taxes=[],
			total_taxes_and_charges=0,
			rounding_adjustment=0,
			grand_total=190000,
			rounded_total=190000,
		)
		doc.flags = frappe._dict()

		result = _serialize_preview(doc, branch="Ketu", pricing_context={"currency": "NGN"})

		self.assertEqual(result["invoice_adjustment_kind"], "discount")
		self.assertEqual(result["invoice_promotion_amount"], 0)
		self.assertEqual(result["invoice_discount_amount"], 10000)

	def test_manual_invoice_discount_cannot_silently_compete_with_invoice_promotion(self):
		doc = frappe._dict(
			pricing_rules=[frappe._dict(pricing_rule="Spend Promotion", rule_applied=1)],
		)
		with self.assertRaises(frappe.ValidationError):
			_validate_manual_invoice_discount_against_promotions(
				doc,
				{"additional_discount_percentage": 5, "discount_amount": 0},
			)

	def test_shared_sale_surfaces_use_business_pricing_terms(self):
		summary = (APP_ROOT / "public" / "js" / "selling" / "SalesCommercialSummary.vue").read_text(encoding="utf-8")
		terms = (APP_ROOT / "public" / "js" / "selling" / "SalesCommercialTermsControls.vue").read_text(encoding="utf-8")
		make_sale = (APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue").read_text(encoding="utf-8")
		quick_sale = (APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue").read_text(encoding="utf-8")

		for wording in (
			"Item promotions",
			"Rate adjustments",
			"Line discounts",
			"invoiceAdjustmentLabel",
			"grandTotalBeforeAdjustmentLabel",
		):
			self.assertIn(wording, summary)
		self.assertIn('documentLabel: { type: String, default: "Invoice" }', summary)
		self.assertIn('const prefix = this.documentLabel === "Invoice" ? "Invoice" : this.documentLabel', summary)
		self.assertNotIn("Price adjustment", summary)
		self.assertNotIn("Selling rate adjustments", summary)
		self.assertIn("Automatic invoice promotion", terms)
		self.assertIn(':label="discountFieldLabel"', terms)
		self.assertIn('label: this.documentLabel === "Invoice" ? "No invoice discount"', terms)
		self.assertIn('discountFieldLabel()', terms)
		self.assertNotIn('label="Additional discount"', terms)
		self.assertNotIn("activeTermCount", terms)
		for source in (make_sale, quick_sale):
			self.assertIn("SalesCommercialSummary", source)
			self.assertIn("SalesCommercialTermsControls", source)

	def test_shared_summary_uses_one_final_tax_label_and_compact_typography(self):
		summary = (APP_ROOT / "public" / "js" / "selling" / "SalesCommercialSummary.vue").read_text(encoding="utf-8")

		self.assertIn("taxDisplayName(tax)", summary)
		self.assertIn("Final tax", summary)
		self.assertIn("Tax change", summary)
		self.assertIn("taxDescriptionIncludesRate", summary)
		self.assertIn("sales-commercial-summary__final-tax", summary)
		self.assertIn("font-size: .76rem", summary)
		self.assertIn("font-weight: 500", summary)
		self.assertIn("white-space: nowrap", summary)

	def test_shared_summary_uses_configured_tax_rate_and_red_negative_values(self):
		summary = (APP_ROOT / "public" / "js" / "selling" / "SalesCommercialSummary.vue").read_text(encoding="utf-8")

		self.assertIn("configuredTaxDisplayName(tax)", summary)
		self.assertIn("const rate = Number(tax?.rate || 0)", summary)
		self.assertIn("sales-commercial-summary__negative-amount", summary)
		self.assertIn("var(--edge-color-danger, #d92d20)", summary)
		self.assertNotIn("sales-commercial-summary__muted-row strong {\n\tcolor: var(--edge-color-success", summary)


if __name__ == "__main__":
	unittest.main()
