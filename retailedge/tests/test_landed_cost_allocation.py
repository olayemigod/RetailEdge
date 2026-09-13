from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.landed_cost_allocation import (
	MAX_LINK_RESULTS,
	prepare_landed_cost_voucher_draft,
	search_landed_cost_sources,
)


def _source(
	doctype: str,
	name: str,
	*,
	docstatus: int = 1,
	is_return: int = 0,
	update_stock: int = 1,
):
	return SimpleNamespace(
		doctype=doctype,
		name=name,
		docstatus=docstatus,
		is_return=is_return,
		update_stock=update_stock,
		company="Demo Company",
		supplier="SUP-001",
	)


def _native_lcv(source) -> dict:
	return {
		"doctype": "Landed Cost Voucher",
		"name": "new-landed-cost-voucher-1",
		"docstatus": 0,
		"company": source.company,
		"distribute_charges_based_on": "Amount",
		"purchase_receipts": [
			frappe._dict(
				{
					"receipt_document_type": source.doctype,
					"receipt_document": source.name,
					"supplier": source.supplier,
					"posting_date": "2026-08-31",
					"grand_total": 500000,
				}
			)
		],
		"items": [frappe._dict({"item_code": "ITEM-001", "qty": 2, "amount": 500000})],
		"taxes": [],
	}


class TestLandedCostAllocation(unittest.TestCase):
	@patch("retailedge.landed_cost_allocation.make_lcv")
	@patch("retailedge.landed_cost_allocation._validate_native_purchase_return_source")
	@patch("retailedge.landed_cost_allocation.frappe.get_doc")
	@patch("retailedge.landed_cost_allocation._assert_create")
	@patch("retailedge.landed_cost_allocation._assert_read")
	def test_purchase_receipt_uses_native_make_lcv_and_returns_unsaved_document(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_validate,
		mock_make_lcv,
	):
		source = _source("Purchase Receipt", "MAT-PRE-0001")
		mock_get_doc.return_value = source
		mock_validate.return_value = (source.company, "Lagos")
		mock_make_lcv.return_value = _native_lcv(source)

		result = prepare_landed_cost_voucher_draft(
			"purchase_receipt",
			source.name,
			distribution_method="Qty",
		)

		mock_make_lcv.assert_called_once_with("Purchase Receipt", source.name)
		self.assertFalse(result["persisted"])
		self.assertEqual(result["posting_status"], "Unsaved Draft")
		self.assertEqual(result["distribution_method"], "Qty")
		self.assertEqual(result["document"]["distribute_charges_based_on"], "Qty")
		self.assertEqual(result["item_count"], 1)
		self.assertEqual(result["branch"], "Lagos")

	@patch("retailedge.landed_cost_allocation.make_lcv")
	@patch("retailedge.landed_cost_allocation._validate_native_purchase_return_source")
	@patch("retailedge.landed_cost_allocation.frappe.get_doc")
	@patch("retailedge.landed_cost_allocation._assert_create")
	@patch("retailedge.landed_cost_allocation._assert_read")
	def test_stock_updating_purchase_invoice_is_supported(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_validate,
		mock_make_lcv,
	):
		source = _source("Purchase Invoice", "ACC-PINV-0001", update_stock=1)
		mock_get_doc.return_value = source
		mock_validate.return_value = (source.company, "")
		mock_make_lcv.return_value = _native_lcv(source)

		result = prepare_landed_cost_voucher_draft("purchase_invoice", source.name)

		mock_make_lcv.assert_called_once_with("Purchase Invoice", source.name)
		self.assertEqual(result["source_type"], "Purchase Invoice")
		self.assertEqual(result["distribution_method"], "Amount")
		self.assertFalse(result["persisted"])

	@patch("retailedge.landed_cost_allocation.make_lcv")
	@patch("retailedge.landed_cost_allocation._validate_native_purchase_return_source")
	@patch("retailedge.landed_cost_allocation.frappe.get_doc")
	@patch("retailedge.landed_cost_allocation._assert_create")
	@patch("retailedge.landed_cost_allocation._assert_read")
	def test_purchase_invoice_without_update_stock_is_rejected_before_native_mapping(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_validate,
		mock_make_lcv,
	):
		source = _source("Purchase Invoice", "ACC-PINV-NOSTOCK", update_stock=0)
		mock_get_doc.return_value = source
		mock_validate.return_value = (source.company, "")

		with self.assertRaises(frappe.ValidationError):
			prepare_landed_cost_voucher_draft("purchase_invoice", source.name)
		mock_make_lcv.assert_not_called()

	def test_unsupported_source_and_distribution_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			prepare_landed_cost_voucher_draft("stock_entry", "MAT-STE-0001")
		with self.assertRaises(frappe.ValidationError):
			prepare_landed_cost_voucher_draft(
				"purchase_receipt",
				"MAT-PRE-0001",
				distribution_method="Equal",
			)

	@patch("retailedge.landed_cost_allocation.make_lcv")
	@patch("retailedge.landed_cost_allocation._validate_native_purchase_return_source")
	@patch("retailedge.landed_cost_allocation.frappe.get_doc")
	@patch("retailedge.landed_cost_allocation._assert_create")
	@patch("retailedge.landed_cost_allocation._assert_read")
	def test_invalid_native_mapping_is_rejected(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_validate,
		mock_make_lcv,
	):
		source = _source("Purchase Receipt", "MAT-PRE-0002")
		mock_get_doc.return_value = source
		mock_validate.return_value = (source.company, "")

		invalid_documents = [
			{**_native_lcv(source), "company": "Other Company"},
			{**_native_lcv(source), "purchase_receipts": []},
			{**_native_lcv(source), "items": []},
			{
				**_native_lcv(source),
				"purchase_receipts": [
					frappe._dict(
						{
							"receipt_document_type": source.doctype,
							"receipt_document": "MAT-PRE-OTHER",
							"supplier": source.supplier,
						}
					)
				],
			},
		]
		for document in invalid_documents:
			mock_make_lcv.return_value = document
			with self.assertRaises(frappe.ValidationError):
				prepare_landed_cost_voucher_draft("purchase_receipt", source.name)

	@patch("retailedge.landed_cost_allocation.search_link")
	@patch("retailedge.landed_cost_allocation._assert_read")
	@patch("retailedge.landed_cost_allocation._branch_scoped_filters")
	@patch("retailedge.landed_cost_allocation._resolve_scope")
	@patch("retailedge.landed_cost_allocation._assert_landed_cost_permissions")
	def test_purchase_invoice_search_is_bounded_and_server_filtered(
		self,
		_mock_permissions,
		mock_scope,
		mock_filters,
		_mock_read,
		mock_search,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_filters.return_value = ({"company": "Demo Company", "retailedge_branch": "Lagos"}, "retailedge_branch")
		mock_search.return_value = [{"value": "ACC-PINV-0001", "label": "ACC-PINV-0001"}]

		result = search_landed_cost_sources(
			"purchase_invoice",
			"ACC",
			company="Demo Company",
			branch="Lagos",
			supplier="SUP-001",
		)

		self.assertEqual(result[0]["value"], "ACC-PINV-0001")
		kwargs = mock_search.call_args.kwargs
		self.assertEqual(kwargs["filters"]["company"], "Demo Company")
		self.assertEqual(kwargs["filters"]["retailedge_branch"], "Lagos")
		self.assertEqual(kwargs["filters"]["supplier"], "SUP-001")
		self.assertEqual(kwargs["filters"]["docstatus"], 1)
		self.assertEqual(kwargs["filters"]["is_return"], 0)
		self.assertEqual(kwargs["filters"]["update_stock"], 1)
		self.assertEqual(kwargs["page_length"], MAX_LINK_RESULTS)
		self.assertEqual(kwargs["reference_doctype"], "Landed Cost Voucher")


if __name__ == "__main__":
	unittest.main()
