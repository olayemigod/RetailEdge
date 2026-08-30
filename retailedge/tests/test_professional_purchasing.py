from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.professional_purchasing import (
	prepare_purchase_receipt_draft,
	search_professional_purchasing_options,
)


class _DraftReceipt(SimpleNamespace):
	doctype = "Purchase Receipt"

	def __init__(self, *, items=None):
		super().__init__(
			name="MAT-PRE-0001",
			docstatus=0,
			company="Demo Company",
			supplier="SUP-001",
			items=items if items is not None else [SimpleNamespace(qty=2)],
			insert_calls=0,
		)

	def insert(self):
		self.insert_calls += 1
		return self


class TestProfessionalPurchasing(unittest.TestCase):
	@patch("retailedge.professional_purchasing._transaction_branch_field", return_value="retailedge_branch")
	@patch("retailedge.professional_purchasing.validate_user_branch_access")
	@patch("retailedge.professional_purchasing._document_branch", return_value="Lagos")
	@patch("retailedge.professional_purchasing.make_purchase_receipt")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_receipt_delegates_to_erpnext_mapper_and_inserts_draft_only(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_document_branch,
		mock_branch_access,
		_mock_branch_field,
	):
		po = SimpleNamespace(
			doctype="Purchase Order",
			name="PUR-ORD-0001",
			docstatus=1,
			status="To Receive and Bill",
			per_received=20,
			is_subcontracted=0,
			company="Demo Company",
			supplier="SUP-001",
		)
		receipt = _DraftReceipt()
		mock_get_doc.return_value = po
		mock_mapper.return_value = receipt

		result = prepare_purchase_receipt_draft("PUR-ORD-0001")

		mock_mapper.assert_called_once_with("PUR-ORD-0001")
		mock_branch_access.assert_called_once_with(
			"Lagos",
			user=frappe.session.user,
			company="Demo Company",
			throw=True,
		)
		self.assertEqual(receipt.insert_calls, 1)
		self.assertEqual(receipt.docstatus, 0)
		self.assertEqual(receipt.retailedge_branch, "Lagos")
		self.assertEqual(result["posting_status"], "Draft")
		self.assertEqual(result["purchase_order"], "PUR-ORD-0001")
		self.assertIn("make_purchase_receipt", result["source_of_truth"])

	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_receipt_rejects_draft_purchase_order(self, _mock_read, _mock_create, mock_get_doc):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Purchase Order",
			name="PUR-ORD-DRAFT",
			docstatus=0,
			status="Draft",
			per_received=0,
			is_subcontracted=0,
			company="Demo Company",
			supplier="SUP-001",
		)
		with self.assertRaises(frappe.ValidationError):
			prepare_purchase_receipt_draft("PUR-ORD-DRAFT")

	@patch("retailedge.professional_purchasing._document_branch", return_value="")
	@patch("retailedge.professional_purchasing.make_purchase_receipt")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_receipt_rejects_no_remaining_receivable_items(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_document_branch,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Purchase Order",
			name="PUR-ORD-0002",
			docstatus=1,
			status="To Receive",
			per_received=50,
			is_subcontracted=0,
			company="Demo Company",
			supplier="SUP-001",
		)
		mock_mapper.return_value = _DraftReceipt(items=[])
		with self.assertRaises(frappe.ValidationError):
			prepare_purchase_receipt_draft("PUR-ORD-0002")

	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_receipt_rejects_subcontracted_purchase_order(self, _mock_read, _mock_create, mock_get_doc):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Purchase Order",
			name="PUR-ORD-SUB",
			docstatus=1,
			status="To Receive and Bill",
			per_received=0,
			is_subcontracted=1,
			company="Demo Company",
			supplier="SUP-001",
		)
		with self.assertRaises(frappe.ValidationError):
			prepare_purchase_receipt_draft("PUR-ORD-SUB")

	@patch("retailedge.professional_purchasing._permission", return_value=False)
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_receipt_requires_purchase_receipt_create_permission(self, _mock_read, _mock_permission):
		with self.assertRaises(frappe.PermissionError):
			prepare_purchase_receipt_draft("PUR-ORD-0003")

	@patch("retailedge.professional_purchasing._document_branch", return_value="Abuja")
	@patch("retailedge.professional_purchasing.make_purchase_receipt")
	@patch("retailedge.professional_purchasing.validate_user_branch_access", side_effect=frappe.PermissionError)
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_receipt_rejects_denied_purchase_order_branch_before_mapping(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		_mock_branch_access,
		mock_mapper,
		_mock_document_branch,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Purchase Order",
			name="PUR-ORD-ABUJA",
			docstatus=1,
			status="To Receive and Bill",
			per_received=0,
			is_subcontracted=0,
			company="Demo Company",
			supplier="SUP-001",
		)

		with self.assertRaises(frappe.PermissionError):
			prepare_purchase_receipt_draft("PUR-ORD-ABUJA")
		mock_mapper.assert_not_called()

	@patch("retailedge.professional_purchasing.search_link")
	def test_company_search_preserves_frappe_link_result_shape(self, mock_search_link):
		mock_search_link.return_value = [
			{"value": "Demo Company", "description": "DC", "label": "Demo Company"}
		]

		result = search_professional_purchasing_options("company", "Demo")

		self.assertEqual(result, mock_search_link.return_value)
		mock_search_link.assert_called_once_with("Company", "Demo", page_length=20)


if __name__ == "__main__":
	unittest.main()
