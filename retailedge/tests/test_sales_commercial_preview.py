from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import call, patch

import frappe

from retailedge.sales_commercial_preview import (
	_assert_can_preview_sales_invoice,
	_item_savings,
	_prepare_preview_document,
	_serialize_preview,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _PreviewDocument:
	def __init__(self):
		self.calls: list[str] = []

	def run_method(self, method: str):
		self.calls.append(method)


class TestSalesCommercialPreview(unittest.TestCase):
	def test_preview_uses_erpnext_document_calculation_without_persistence(self):
		doc = _PreviewDocument()
		_prepare_preview_document(doc)
		self.assertEqual(
			doc.calls,
			["set_missing_values", "set_taxes_and_charges", "calculate_taxes_and_totals"],
		)

	@patch("retailedge.sales_commercial_preview.frappe.has_permission")
	def test_preview_allows_existing_draft_editor_without_create_permission(self, mock_permission):
		mock_permission.side_effect = lambda _doctype, permission: permission == "write"
		_assert_can_preview_sales_invoice()
		self.assertEqual(
			mock_permission.call_args_list,
			[
				call("Sales Invoice", "create"),
				call("Sales Invoice", "write"),
			],
		)

	@patch("retailedge.sales_commercial_preview.frappe.has_permission", return_value=False)
	def test_preview_fails_closed_without_create_or_write_permission(self, _mock_permission):
		with self.assertRaises(frappe.PermissionError):
			_assert_can_preview_sales_invoice()

	def test_item_savings_uses_price_list_reference_without_negative_savings(self):
		self.assertEqual(
			_item_savings(frappe._dict(qty=2, price_list_rate=1000, amount=1800)),
			200,
		)
		self.assertEqual(
			_item_savings(frappe._dict(qty=1, price_list_rate=1000, amount=1100)),
			0,
		)

	def test_serialized_preview_exposes_line_amount_discount_tax_and_payable_total(self):
		doc = frappe._dict(
			company="RetailEdge Consulting",
			branch="Ketu",
			customer="CUST-001",
			currency="NGN",
			selling_price_list="Standard Selling",
			tax_category="VAT",
			taxes_and_charges="Nigeria Sales VAT",
			items=[
				frappe._dict(
					item_code="ITEM-001",
					item_name="Battery",
					uom="Nos",
					stock_uom="Nos",
					qty=2,
					price_list_rate=1000,
					discount_percentage=10,
					discount_amount=100,
					rate=900,
					amount=1800,
					net_rate=900,
					net_amount=1800,
				),
			],
			total=1800,
			net_total=1800,
			additional_discount_percentage=0,
			discount_amount=0,
			apply_discount_on="Grand Total",
			taxes=[
				frappe._dict(
					description="VAT",
					rate=7.5,
					tax_amount=135,
					tax_amount_after_discount_amount=135,
					included_in_print_rate=0,
				),
			],
			total_taxes_and_charges=135,
			rounding_adjustment=0,
			grand_total=1935,
			rounded_total=1940,
		)

		result = _serialize_preview(
			doc,
			branch="Ketu",
			pricing_context={"price_list": "Standard Selling", "currency": "NGN"},
		)

		self.assertTrue(result["is_preview"])
		self.assertEqual(result["items"][0]["uom"], "Nos")
		self.assertEqual(result["items"][0]["amount"], 1800)
		self.assertEqual(result["items"][0]["discount_percentage"], 10)
		self.assertEqual(result["list_value"], 2000)
		self.assertEqual(result["subtotal"], 1800)
		self.assertEqual(result["net_total"], 1800)
		self.assertEqual(result["item_discount_total"], 200)
		self.assertEqual(result["total_taxes_and_charges"], 135)
		self.assertFalse(result["all_taxes_included"])
		self.assertEqual(result["invoice_total"], 1940)
		self.assertTrue(result["has_discount"])
		self.assertTrue(result["has_tax"])

	def test_inclusive_tax_is_explicit_in_preview(self):
		doc = frappe._dict(
			company="RetailEdge Consulting",
			branch="Ketu",
			customer="CUST-001",
			currency="NGN",
			items=[frappe._dict(item_code="ITEM-001", qty=1, rate=1075, amount=1075)],
			total=1075,
			net_total=1000,
			taxes=[
				frappe._dict(
					description="VAT",
					rate=7.5,
					tax_amount=75,
					tax_amount_after_discount_amount=75,
					included_in_print_rate=1,
				),
			],
			total_taxes_and_charges=75,
			grand_total=1075,
			rounded_total=1075,
		)
		result = _serialize_preview(doc, branch="Ketu", pricing_context={"currency": "NGN"})
		self.assertTrue(result["all_taxes_included"])
		self.assertEqual(result["invoice_total"], 1075)

	def test_backend_contract_is_post_only_and_has_no_persistence_path(self):
		source = (APP_ROOT / "sales_commercial_preview.py").read_text()
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn('doc.run_method("set_missing_values")', source)
		self.assertIn('doc.run_method("set_taxes_and_charges")', source)
		self.assertIn('doc.run_method("calculate_taxes_and_totals")', source)
		self.assertIn("resolve_sales_item_pricing", source)
		self.assertIn("resolve_price_list_context", source)
		for forbidden in (
			"doc.insert(",
			"doc.save(",
			"doc.submit(",
			"frappe.db.commit(",
			"ignore_permissions=True",
			"GL Entry",
			"Stock Ledger Entry",
			"Payment Ledger Entry",
		):
			self.assertNotIn(forbidden, source)

	def test_quick_and_make_sale_share_commercial_preview_contract(self):
		quick = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleSalesInvoiceDialog.vue"
		).read_text()
		make_sale = (APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue").read_text()
		summary = (APP_ROOT / "public" / "js" / "selling" / "SalesCommercialSummary.vue").read_text()

		for source in (quick, make_sale):
			self.assertIn("retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview", source)
			self.assertIn("SalesCommercialSummary", source)
			self.assertIn('fieldname: "uom"', source)
			self.assertIn('fieldname: "discount_percentage"', source)
			self.assertIn('fieldname: "amount"', source)
			self.assertIn("commercialPreviewBlocked", source)
			self.assertIn("previewAppliedSignature", source)
			self.assertIn("token !== this.previewToken", source)
			self.assertIn("signature !== this.commercialPreviewSignature", source)

		self.assertIn("List value", summary)
		self.assertIn("Invoice Total", summary)
		self.assertIn("Item savings", summary)
		self.assertIn("Tax (included)", summary)
		self.assertIn("View tax breakdown", summary)
		self.assertIn("Updating total", summary)

	def test_make_sale_preview_only_fields_do_not_create_false_user_edits(self):
		source = (APP_ROOT / "public" / "js" / "make_sale" / "MakeSale.vue").read_text()
		self.assertIn("function editableSnapshot(values)", source)
		self.assertIn("delete copy.uom", source)
		self.assertIn("delete copy.discount_percentage", source)
		self.assertIn("delete copy.amount", source)
		self.assertIn("editableSnapshot(this.values) !== this.initialSnapshot", source)


if __name__ == "__main__":
	unittest.main()
