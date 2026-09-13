from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.professional_purchasing import (
	prepare_purchase_receipt_draft,
	prepare_request_for_quotation_draft,
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


class _DraftRFQ(SimpleNamespace):
	doctype = "Request for Quotation"

	def __init__(self, *, material_request="MAT-MR-0001", items=None):
		super().__init__(
			name="PUR-RFQ-0001",
			docstatus=0,
			company="Demo Company",
			items=items if items is not None else [SimpleNamespace(qty=3, material_request=material_request)],
			suppliers=[],
			insert_calls=0,
		)

	def append(self, fieldname, values):
		if fieldname != "suppliers":
			raise AssertionError(f"Unexpected append field {fieldname}")
		row = SimpleNamespace(**values)
		self.suppliers.append(row)
		return row

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

	@patch("retailedge.professional_purchasing._transaction_branch_field", return_value="retailedge_branch")
	@patch("retailedge.professional_purchasing.validate_user_branch_access")
	@patch("retailedge.professional_purchasing._document_branch", return_value="Lagos")
	@patch("retailedge.professional_purchasing.make_request_for_quotation")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_delegates_to_native_mapper_and_inserts_draft_with_email_disabled(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_document_branch,
		mock_branch_access,
		_mock_branch_field,
	):
		request = SimpleNamespace(
			doctype="Material Request",
			name="MAT-MR-0001",
			docstatus=1,
			material_request_type="Purchase",
			status="Pending",
			per_ordered=25,
			company="Demo Company",
		)
		rfq = _DraftRFQ(material_request=request.name)
		mock_get_doc.return_value = request
		mock_mapper.return_value = rfq

		result = prepare_request_for_quotation_draft(request.name, ["SUP-001", "SUP-002"])

		mock_mapper.assert_called_once_with(request.name)
		mock_branch_access.assert_called_once_with(
			"Lagos",
			user=frappe.session.user,
			company="Demo Company",
			throw=True,
		)
		self.assertEqual(rfq.insert_calls, 1)
		self.assertEqual(rfq.docstatus, 0)
		self.assertEqual(rfq.retailedge_branch, "Lagos")
		self.assertEqual([row.supplier for row in rfq.suppliers], ["SUP-001", "SUP-002"])
		self.assertTrue(all(row.send_email == 0 for row in rfq.suppliers))
		self.assertEqual(result["posting_status"], "Draft")
		self.assertFalse(result["email_sending"])
		self.assertEqual(result["supplier_count"], 2)
		self.assertIn("make_request_for_quotation", result["source_of_truth"])

	@patch("retailedge.professional_purchasing.make_request_for_quotation")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_rejects_non_purchase_material_request(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Material Request",
			name="MAT-MR-TRANSFER",
			docstatus=1,
			material_request_type="Material Transfer",
			status="Pending",
			per_ordered=0,
			company="Demo Company",
		)
		with self.assertRaises(frappe.ValidationError):
			prepare_request_for_quotation_draft("MAT-MR-TRANSFER", ["SUP-001"])
		mock_mapper.assert_not_called()

	@patch("retailedge.professional_purchasing.make_request_for_quotation")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_rejects_fully_ordered_material_request(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Material Request",
			name="MAT-MR-ORDERED",
			docstatus=1,
			material_request_type="Purchase",
			status="Pending",
			per_ordered=100,
			company="Demo Company",
		)
		with self.assertRaises(frappe.ValidationError):
			prepare_request_for_quotation_draft("MAT-MR-ORDERED", ["SUP-001"])
		mock_mapper.assert_not_called()

	@patch("retailedge.professional_purchasing._document_branch", return_value="")
	@patch("retailedge.professional_purchasing.make_request_for_quotation")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_rejects_mapper_without_remaining_items(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_document_branch,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Material Request",
			name="MAT-MR-EMPTY",
			docstatus=1,
			material_request_type="Purchase",
			status="Pending",
			per_ordered=50,
			company="Demo Company",
		)
		mock_mapper.return_value = _DraftRFQ(material_request="MAT-MR-EMPTY", items=[])
		with self.assertRaises(frappe.ValidationError):
			prepare_request_for_quotation_draft("MAT-MR-EMPTY", ["SUP-001"])

	@patch("retailedge.professional_purchasing.make_request_for_quotation")
	@patch("retailedge.professional_purchasing.validate_user_branch_access", side_effect=frappe.PermissionError)
	@patch("retailedge.professional_purchasing._document_branch", return_value="Abuja")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_rejects_denied_branch_before_mapping(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		_mock_document_branch,
		_mock_branch_access,
		mock_mapper,
	):
		mock_get_doc.return_value = SimpleNamespace(
			doctype="Material Request",
			name="MAT-MR-ABUJA",
			docstatus=1,
			material_request_type="Purchase",
			status="Pending",
			per_ordered=0,
			company="Demo Company",
		)
		with self.assertRaises(frappe.PermissionError):
			prepare_request_for_quotation_draft("MAT-MR-ABUJA", ["SUP-001"])
		mock_mapper.assert_not_called()

	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_requires_suppliers_and_rejects_duplicates(self, _mock_read, _mock_create):
		with self.assertRaises(frappe.ValidationError):
			prepare_request_for_quotation_draft("MAT-MR-0001", [])
		with self.assertRaises(frappe.ValidationError):
			prepare_request_for_quotation_draft("MAT-MR-0001", ["SUP-001", "SUP-001"])

	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_prepare_rfq_bounds_supplier_count(self, _mock_read, _mock_create):
		with self.assertRaises(frappe.ValidationError):
			prepare_request_for_quotation_draft("MAT-MR-0001", [f"SUP-{index:03d}" for index in range(21)])

	@patch("retailedge.professional_purchasing.search_link")
	def test_company_search_preserves_frappe_link_result_shape(self, mock_search_link):
		mock_search_link.return_value = [
			{"value": "Demo Company", "description": "DC", "label": "Demo Company"}
		]

		result = search_professional_purchasing_options("company", "Demo")

		self.assertEqual(result, mock_search_link.return_value)
		mock_search_link.assert_called_once_with("Company", "Demo", page_length=20)

	@patch("retailedge.professional_purchasing.search_link")
	def test_rfq_supplier_search_uses_native_supplier_link_and_disabled_filter(self, mock_search_link):
		mock_search_link.return_value = [{"value": "SUP-001", "label": "Supplier One", "description": ""}]

		result = search_professional_purchasing_options("rfq_supplier", "Supplier")

		self.assertEqual(result, mock_search_link.return_value)
		mock_search_link.assert_called_once_with(
			"Supplier",
			"Supplier",
			filters={"disabled": 0},
			page_length=20,
			reference_doctype="Request for Quotation",
			link_fieldname="supplier",
		)


if __name__ == "__main__":
	unittest.main()
