from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.sales_commercial_terms import (
	apply_sales_commercial_terms,
	normalise_sales_commercial_terms,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _Doc:
	def __init__(self, **values):
		self.values = dict(values)

	def get(self, fieldname, default=None):
		return self.values.get(fieldname, default)

	def set(self, fieldname, value):
		self.values[fieldname] = value

	def append(self, fieldname, value):
		self.values.setdefault(fieldname, []).append(value)


class TestSalesCommercialTerms(unittest.TestCase):
	def test_normalise_accepts_one_additional_discount_mode(self):
		percentage = normalise_sales_commercial_terms(
			{
				"additional_discount_percentage": 7.5,
				"discount_amount": 0,
				"apply_discount_on": "Grand Total",
			}
		)
		self.assertEqual(percentage["additional_discount_percentage"], 7.5)
		self.assertEqual(percentage["discount_amount"], 0)
		self.assertEqual(percentage["apply_discount_on"], "Grand Total")

		amount = normalise_sales_commercial_terms(
			{
				"additional_discount_percentage": 0,
				"discount_amount": 2500,
				"apply_discount_on": "Net Total",
			}
		)
		self.assertEqual(amount["additional_discount_percentage"], 0)
		self.assertEqual(amount["discount_amount"], 2500)
		self.assertEqual(amount["apply_discount_on"], "Net Total")

	def test_normalise_rejects_ambiguous_or_invalid_discounts(self):
		for values in (
			{"additional_discount_percentage": 10, "discount_amount": 100},
			{"additional_discount_percentage": -1},
			{"additional_discount_percentage": 101},
			{"discount_amount": -1},
			{"apply_discount_on": "Outstanding Amount"},
		):
			with self.subTest(values=values):
				with self.assertRaises(frappe.ValidationError):
					normalise_sales_commercial_terms(values)

	@patch("retailedge.sales_commercial_terms.validate_coupon_code")
	@patch("retailedge.sales_commercial_terms.frappe.has_permission", return_value=True)
	@patch("retailedge.sales_commercial_terms.frappe.db.exists", return_value=True)
	def test_coupon_uses_erpnext_validation_and_permission(
		self,
		_mock_exists,
		_mock_permission,
		mock_validate_coupon,
	):
		doc = _Doc(company="RetailEdge Consulting")
		result = apply_sales_commercial_terms(doc, {"coupon_code": "Holiday Offer"})
		self.assertEqual(doc.get("coupon_code"), "Holiday Offer")
		self.assertEqual(result["coupon_code"], "Holiday Offer")
		mock_validate_coupon.assert_called_once_with("Holiday Offer")

	@patch("retailedge.sales_commercial_terms.get_taxes_and_charges")
	@patch("retailedge.sales_commercial_terms.frappe.db.get_value")
	@patch("retailedge.sales_commercial_terms.frappe.has_permission", return_value=True)
	@patch("retailedge.sales_commercial_terms.frappe.db.exists", return_value=True)
	def test_tax_template_is_company_safe_and_uses_erpnext_tax_rows(
		self,
		_mock_exists,
		_mock_permission,
		mock_get_value,
		mock_get_taxes,
	):
		mock_get_value.return_value = frappe._dict(
			company="RetailEdge Consulting",
			disabled=0,
			tax_category="",
		)
		mock_get_taxes.return_value = [
			{"charge_type": "On Net Total", "account_head": "VAT - RC", "rate": 7.5}
		]
		doc = _Doc(company="RetailEdge Consulting", taxes=[{"description": "Old tax"}])
		result = apply_sales_commercial_terms(doc, {"taxes_and_charges": "Nigeria Sales VAT - RC"})
		self.assertEqual(doc.get("taxes_and_charges"), "Nigeria Sales VAT - RC")
		self.assertEqual(len(doc.get("taxes")), 1)
		self.assertEqual(doc.get("taxes")[0]["account_head"], "VAT - RC")
		self.assertEqual(result["taxes_and_charges"], "Nigeria Sales VAT - RC")
		mock_get_taxes.assert_called_once_with(
			"Sales Taxes and Charges Template",
			"Nigeria Sales VAT - RC",
		)

	@patch("retailedge.sales_commercial_terms.get_taxes_and_charges")
	@patch("retailedge.sales_commercial_terms.frappe.db.get_value")
	@patch("retailedge.sales_commercial_terms.frappe.has_permission", return_value=True)
	@patch("retailedge.sales_commercial_terms.frappe.db.exists", return_value=True)
	def test_tax_template_cannot_cross_company(
		self,
		_mock_exists,
		_mock_permission,
		mock_get_value,
		_mock_get_taxes,
	):
		mock_get_value.return_value = frappe._dict(company="Other Company", disabled=0, tax_category="")
		doc = _Doc(company="RetailEdge Consulting")
		with self.assertRaises(frappe.PermissionError):
			apply_sales_commercial_terms(doc, {"taxes_and_charges": "Other VAT"})

	def test_blank_tax_template_means_automatic_and_cannot_clear_existing_tax(self):
		doc = _Doc(
			company="RetailEdge Consulting",
			taxes_and_charges="Nigeria Sales VAT - RC",
			taxes=[{"description": "VAT", "rate": 7.5}],
		)
		result = apply_sales_commercial_terms(doc, {"taxes_and_charges": ""})
		self.assertEqual(doc.get("taxes_and_charges"), "Nigeria Sales VAT - RC")
		self.assertEqual(doc.get("taxes"), [{"description": "VAT", "rate": 7.5}])
		self.assertEqual(result["taxes_and_charges"], "Nigeria Sales VAT - RC")

	def test_discount_application_only_sets_erpnext_fields(self):
		doc = _Doc(company="RetailEdge Consulting")
		result = apply_sales_commercial_terms(
			doc,
			{
				"additional_discount_percentage": 5,
				"discount_amount": 0,
				"apply_discount_on": "Grand Total",
			},
		)
		self.assertEqual(doc.get("additional_discount_percentage"), 5)
		self.assertEqual(doc.get("discount_amount"), 0)
		self.assertEqual(doc.get("apply_discount_on"), "Grand Total")
		self.assertEqual(result["additional_discount_percentage"], 5)

	def test_service_has_no_persistence_or_ledger_path(self):
		source = (APP_ROOT / "sales_commercial_terms.py").read_text(encoding="utf-8")
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
		self.assertIn("validate_coupon_code", source)
		self.assertIn("get_taxes_and_charges", source)
		self.assertIn("frappe.has_permission", source)
		self.assertIn("get_sales_commercial_edit_context", source)

	def test_new_sale_preview_and_draft_share_one_commercial_terms_helper(self):
		preview = (APP_ROOT / "sales_commercial_preview.py").read_text(encoding="utf-8")
		guided = (APP_ROOT / "guided_sales_invoice.py").read_text(encoding="utf-8")

		self.assertGreaterEqual(preview.count("apply_sales_commercial_terms(doc, values)"), 2)
		self.assertIn("apply_sales_commercial_terms(doc, values)", guided)
		self.assertLess(
			guided.index("apply_sales_commercial_terms(doc, values)"),
			guided.index("doc.insert()"),
		)
		self.assertIn('"commercial_terms": get_sales_commercial_term_capabilities()', guided)
		self.assertIn('{"coupon_code", "tax_category", "taxes_and_charges"}', guided)

	def test_guided_draft_keeps_erpnext_as_calculation_and_accounting_authority(self):
		guided = (APP_ROOT / "guided_sales_invoice.py").read_text(encoding="utf-8")
		for forbidden in (
			"calculate_taxes_and_totals()",
			"debit_to =",
			"income_account =",
			"frappe.db.commit(",
			"doc.submit(",
			"ignore_permissions=True",
		):
			self.assertNotIn(forbidden, guided)

	def test_saved_draft_adapter_keeps_standard_completion_authority_and_no_commit(self):
		source = (APP_ROOT / "sales_commercial_draft_update.py").read_text(encoding="utf-8")
		self.assertIn("update_standard_sales_invoice_draft(", source)
		self.assertIn("apply_sales_commercial_terms(doc, terms)", source)
		self.assertLess(
			source.index("update_standard_sales_invoice_draft("),
			source.index("apply_sales_commercial_terms(doc, terms)"),
		)
		self.assertIn("doc.save()", source)
		for forbidden in (
			"frappe.db.commit(",
			"doc.submit(",
			"ignore_permissions=True",
			"GL Entry",
			"Stock Ledger Entry",
			"Payment Ledger Entry",
		):
			self.assertNotIn(forbidden, source)

	def test_sales_surfaces_share_edgesuite_commercial_controls_and_exact_date(self):
		quick = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text(encoding="utf-8")
		make_sale = (APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue").read_text(encoding="utf-8")
		controls = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "selling"
			/ "SalesCommercialTermsControls.vue"
		).read_text(encoding="utf-8")

		for source in (quick, make_sale):
			self.assertIn("SalesCommercialTermsControls", source)
			self.assertIn('label="Posting Date"', source)
			self.assertIn('type="date"', source)
			for fieldname in (
				"coupon_code",
				"taxes_and_charges",
				"additional_discount_percentage",
				"discount_amount",
				"apply_discount_on",
			):
				self.assertIn(fieldname, source)

		self.assertIn("EdgeDropdown", controls)
		self.assertIn("EdgeInput", controls)
		self.assertIn("EdgeLinkField", controls)
		self.assertIn("Automatic tax treatment", controls)
		self.assertIn("No invoice discount", controls)
		self.assertIn("Automatic invoice promotion", controls)

	def test_make_sale_saved_draft_loads_exact_terms_and_uses_atomic_update(self):
		make_sale = (APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue").read_text(encoding="utf-8")
		self.assertIn("retailedge.sales_commercial_terms.get_sales_commercial_edit_context", make_sale)
		self.assertIn("retailedge.sales_commercial_terms.search_sales_commercial_term_options", make_sale)
		self.assertIn("retailedge.sales_commercial_draft_update.update_sales_invoice_draft_with_commercial_terms", make_sale)
		self.assertIn("applyCommercialTermContext", make_sale)
		self.assertIn("savedCommercialTermCapabilities", make_sale)
		self.assertIn("args.document_name = this.savedDocument.name", make_sale)
		self.assertIn("UPDATE_WITH_TERMS_METHOD", make_sale)
		self.assertIn("COMMERCIAL_TERM_CONTEXT_METHOD", make_sale)
		self.assertIn("COMMERCIAL_TERM_SEARCH_METHOD", make_sale)
		self.assertIn("result.commercial_terms", make_sale)

	def test_make_sale_real_commercial_terms_remain_part_of_dirty_state(self):
		make_sale = (APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue").read_text(encoding="utf-8")
		self.assertIn("delete copy.uom", make_sale)
		self.assertIn("delete copy.discount_percentage", make_sale)
		self.assertIn("delete copy.amount", make_sale)
		self.assertNotIn("delete copy.coupon_code", make_sale)
		self.assertNotIn("delete copy.taxes_and_charges", make_sale)
		self.assertNotIn("delete copy.additional_discount_percentage", make_sale)
		self.assertNotIn("delete copy.discount_amount", make_sale)


if __name__ == "__main__":
	unittest.main()
