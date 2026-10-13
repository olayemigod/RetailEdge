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

	def test_tax_template_cannot_be_cleared_through_guided_terms(self):
		doc = _Doc(company="RetailEdge Consulting")
		with self.assertRaises(frappe.ValidationError):
			apply_sales_commercial_terms(doc, {"taxes_and_charges": ""})

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


if __name__ == "__main__":
	unittest.main()
