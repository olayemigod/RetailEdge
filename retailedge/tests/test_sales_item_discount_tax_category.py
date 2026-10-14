from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.sales_commercial_terms import (
	apply_sales_commercial_terms,
	normalise_sales_commercial_terms,
	search_sales_commercial_term_options,
)
from retailedge.sales_item_discounts import (
	MANUAL_DISCOUNT_AMOUNT,
	MANUAL_DISCOUNT_PERCENTAGE,
	apply_manual_item_discount,
	manual_item_discount_state,
	normalise_manual_item_discount,
	validate_manual_item_discounts_after_pricing,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _Row:
	def __init__(self, **values):
		self.values = dict(values)

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def set(self, fieldname, value):
		self.values[fieldname] = value


class _Doc(_Row):
	def append(self, fieldname, value):
		self.values.setdefault(fieldname, []).append(value)


class TestSalesItemDiscountTaxCategory(unittest.TestCase):
	def test_manual_item_discount_accepts_percentage_or_amount(self):
		percentage = normalise_manual_item_discount({MANUAL_DISCOUNT_PERCENTAGE: 12.5})
		self.assertTrue(percentage["supplied"])
		self.assertTrue(percentage["active"])
		self.assertEqual(percentage[MANUAL_DISCOUNT_PERCENTAGE], 12.5)
		self.assertEqual(percentage[MANUAL_DISCOUNT_AMOUNT], 0)

		amount = normalise_manual_item_discount({MANUAL_DISCOUNT_AMOUNT: 2500})
		self.assertEqual(amount[MANUAL_DISCOUNT_PERCENTAGE], 0)
		self.assertEqual(amount[MANUAL_DISCOUNT_AMOUNT], 2500)

	def test_manual_item_discount_rejects_invalid_or_ambiguous_input(self):
		for values in (
			{MANUAL_DISCOUNT_PERCENTAGE: -1},
			{MANUAL_DISCOUNT_PERCENTAGE: 101},
			{MANUAL_DISCOUNT_AMOUNT: -1},
			{MANUAL_DISCOUNT_PERCENTAGE: 5, MANUAL_DISCOUNT_AMOUNT: 500},
		):
			with self.subTest(values=values):
				with self.assertRaises(frappe.ValidationError):
					normalise_manual_item_discount(values, index=1)

	def test_manual_item_discount_maps_only_to_native_erpnext_item_fields(self):
		row = _Row(item_code="ITEM-001")
		apply_manual_item_discount(row, {MANUAL_DISCOUNT_PERCENTAGE: 7.5}, index=1)
		self.assertEqual(row.get("discount_percentage"), 7.5)
		self.assertEqual(row.get("discount_amount"), 0)
		self.assertNotIn(MANUAL_DISCOUNT_PERCENTAGE, row.values)
		self.assertNotIn(MANUAL_DISCOUNT_AMOUNT, row.values)

	def test_rate_lock_blocks_manual_item_discount(self):
		row = _Row(item_code="ITEM-001")
		with self.assertRaises(frappe.PermissionError):
			apply_manual_item_discount(
				row,
				{MANUAL_DISCOUNT_PERCENTAGE: 10},
				index=1,
				rate_locked=True,
				lock_reason="Assigned POS Profile controls the selling rate.",
			)

	def test_pricing_rule_discount_is_not_exposed_as_manual_input(self):
		state = manual_item_discount_state(
			_Row(
				discount_percentage=10,
				discount_amount=100,
				pricing_rules="Automatic Offer",
			)
		)
		self.assertEqual(state[MANUAL_DISCOUNT_PERCENTAGE], 0)
		self.assertEqual(state[MANUAL_DISCOUNT_AMOUNT], 0)
		self.assertEqual(state["pricing_rule"], "Automatic Offer")

	def test_manual_discount_cannot_silently_override_automatic_pricing_rule(self):
		doc = _Doc(
			items=[
				_Row(
					item_code="ITEM-001",
					is_free_item=0,
					pricing_rules="Automatic Offer",
				)
			]
		)
		with self.assertRaises(frappe.ValidationError):
			validate_manual_item_discounts_after_pricing(
				doc,
				[{"item_code": "ITEM-001", MANUAL_DISCOUNT_PERCENTAGE: 5}],
			)

	def test_manual_discount_survives_when_no_pricing_rule_applies(self):
		doc = _Doc(items=[_Row(item_code="ITEM-001", is_free_item=0, pricing_rules="")])
		validate_manual_item_discounts_after_pricing(
			doc,
			[{"item_code": "ITEM-001", MANUAL_DISCOUNT_AMOUNT: 500}],
		)

	def test_tax_category_is_a_normalised_native_sales_invoice_term(self):
		terms = normalise_sales_commercial_terms({"tax_category": "  Retail Tax  "})
		self.assertEqual(terms["tax_category"], "Retail Tax")

	@patch("retailedge.sales_commercial_terms._validate_tax_category")
	def test_changing_tax_category_clears_stale_template_and_rows(self, mock_validate):
		doc = _Doc(
			company="RetailEdge Consulting",
			tax_category="Old Category",
			taxes_and_charges="Old VAT",
			taxes=[{"description": "Old tax"}],
		)
		result = apply_sales_commercial_terms(doc, {"tax_category": "Retail Tax"})
		mock_validate.assert_called_once_with("Retail Tax")
		self.assertEqual(doc.get("tax_category"), "Retail Tax")
		self.assertEqual(doc.get("taxes_and_charges"), "")
		self.assertEqual(doc.get("taxes"), [])
		self.assertEqual(result["tax_category"], "Retail Tax")

	@patch("retailedge.sales_commercial_terms.get_taxes_and_charges")
	@patch("retailedge.sales_commercial_terms._validate_sales_tax_template")
	@patch("retailedge.sales_commercial_terms._validate_tax_category")
	def test_category_then_compatible_template_uses_erpnext_tax_rows(
		self,
		_mock_category,
		mock_template,
		mock_taxes,
	):
		mock_taxes.return_value = [{"description": "VAT", "rate": 7.5}]
		doc = _Doc(
			company="RetailEdge Consulting",
			tax_category="Old Category",
			taxes_and_charges="Old VAT",
			taxes=[{"description": "Old tax"}],
		)
		apply_sales_commercial_terms(
			doc,
			{"tax_category": "Retail Tax", "taxes_and_charges": "Retail VAT"},
		)
		mock_template.assert_called_once_with(doc, "Retail VAT")
		self.assertEqual(doc.get("tax_category"), "Retail Tax")
		self.assertEqual(doc.get("taxes_and_charges"), "Retail VAT")
		self.assertEqual(doc.get("taxes"), [{"description": "VAT", "rate": 7.5}])

	@patch("retailedge.sales_commercial_terms.search_link")
	@patch("retailedge.sales_commercial_terms._can_select", return_value=True)
	@patch("retailedge.sales_commercial_terms._assert_invoice_term_search_access", return_value=None)
	def test_tax_category_search_is_permission_aware_and_enabled_only(
		self,
		_mock_access,
		_mock_select,
		mock_search,
	):
		mock_search.return_value = [{"value": "Retail Tax"}]
		result = search_sales_commercial_term_options("tax_category", txt="ret", values={})
		self.assertEqual(result, [{"value": "Retail Tax"}])
		self.assertEqual(mock_search.call_args.kwargs["filters"], {"disabled": 0})
		self.assertEqual(mock_search.call_args.kwargs["link_fieldname"], "tax_category")

	@patch("retailedge.sales_commercial_terms._search_sales_tax_templates")
	@patch("retailedge.sales_commercial_terms._can_select", return_value=True)
	@patch("retailedge.sales_commercial_terms._assert_invoice_term_search_access")
	def test_saved_draft_template_search_respects_pending_tax_category(
		self,
		mock_access,
		_mock_select,
		mock_search_templates,
	):
		mock_access.return_value = _Doc(
			company="RetailEdge Consulting",
			customer="CUST-001",
			tax_category="Stored Category",
		)
		mock_search_templates.return_value = []
		search_sales_commercial_term_options(
			"taxes_and_charges",
			values={"document_name": "SINV-001", "tax_category": "Pending Category"},
		)
		self.assertEqual(mock_search_templates.call_args.kwargs["tax_category"], "Pending Category")
		self.assertEqual(mock_search_templates.call_args.kwargs["company"], "RetailEdge Consulting")

	def test_server_paths_validate_manual_discount_after_erpnext_pricing(self):
		guided = (APP_ROOT / "guided_sales_invoice.py").read_text(encoding="utf-8")
		preview = (APP_ROOT / "sales_commercial_preview.py").read_text(encoding="utf-8")
		draft_update = (APP_ROOT / "sales_commercial_draft_update.py").read_text(encoding="utf-8")

		self.assertIn("apply_manual_item_discount(", guided)
		self.assertLess(guided.index("doc.insert()"), guided.index("validate_manual_item_discounts_after_pricing(doc, items)"))
		self.assertGreaterEqual(preview.count("validate_manual_item_discounts_after_pricing"), 3)
		self.assertIn("validate_manual_item_discounts_after_pricing(doc, values.get(\"items\"))", draft_update)
		for source in (preview, draft_update):
			self.assertNotIn("frappe.db.commit(", source)
			self.assertNotIn("ignore_permissions=True", source)

	def test_make_sale_exposes_manual_discount_controls_but_quick_sale_does_not(self):
		extension = (
			APP_ROOT / "public" / "js" / "make_sale" / "commercialEditingExtension.js"
		).read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public" / "js" / "make_sale.bundle.js").read_text(encoding="utf-8")
		quick = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue"
		).read_text(encoding="utf-8")

		self.assertIn('label: "Manual Discount %"', extension)
		self.assertIn('label: "Discount per Unit"', extension)
		self.assertIn('label: "Applied %"', extension)
		self.assertIn("manual_discount_percentage", extension)
		self.assertIn("manual_discount_amount", extension)
		self.assertIn("tax_category", extension)
		self.assertIn("applyMakeSaleCommercialEditing(MakeSale)", bundle)
		self.assertNotIn("Manual Discount %", quick)
		self.assertNotIn("Discount per Unit", quick)

	def test_native_discount_amount_is_documented_as_per_unit(self):
		source = (APP_ROOT / "sales_item_discounts.py").read_text(encoding="utf-8")
		self.assertIn("per-unit discount", source)
		self.assertIn("Discount per Unit", source)

	def test_tax_category_cascades_across_shared_and_quick_sale_ui(self):
		controls = (
			APP_ROOT / "public" / "js" / "selling" / "SalesCommercialTermsControls.vue"
		).read_text(encoding="utf-8")
		quick = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue"
		).read_text(encoding="utf-8")

		self.assertIn('label="Tax category"', controls)
		self.assertIn('this.emitChange({ tax_category: value || "", taxes_and_charges: "" })', controls)
		self.assertIn('return this.searcher("tax_category", query || "")', controls)
		self.assertIn("tax_category: this.values.tax_category", quick)
		self.assertIn('this.values.tax_category = ""', quick)

	def test_manual_discount_helper_has_no_persistence_or_ledger_path(self):
		source = (APP_ROOT / "sales_item_discounts.py").read_text(encoding="utf-8")
		for forbidden in (
			".insert(",
			".save(",
			".submit(",
			"frappe.db.commit(",
			"ignore_permissions=True",
			"GL Entry",
			"Stock Ledger Entry",
			"Payment Ledger Entry",
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
