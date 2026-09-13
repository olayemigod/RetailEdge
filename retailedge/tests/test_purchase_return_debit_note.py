from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.professional_purchasing import (
	MAX_LINK_RESULTS,
	prepare_purchase_return_draft,
	prepare_supplier_debit_note_draft,
	search_purchase_return_sources,
)


class _DraftReturn(SimpleNamespace):
	def __init__(
		self,
		*,
		doctype: str,
		name: str,
		return_against: str,
		company: str = "Demo Company",
		supplier: str = "SUP-001",
		items=None,
		is_return: int = 1,
		docstatus: int = 0,
		update_stock: int = 0,
	):
		super().__init__(
			doctype=doctype,
			name=name,
			return_against=return_against,
			company=company,
			supplier=supplier,
			items=items if items is not None else [SimpleNamespace(qty=-2)],
			is_return=is_return,
			docstatus=docstatus,
			update_stock=update_stock,
			insert_calls=0,
		)

	def insert(self):
		self.insert_calls += 1
		return self


def _source(doctype: str, name: str, *, docstatus: int = 1, is_return: int = 0):
	return SimpleNamespace(
		doctype=doctype,
		name=name,
		docstatus=docstatus,
		is_return=is_return,
		company="Demo Company",
		supplier="SUP-001",
	)


class TestPurchaseReturnDebitNote(unittest.TestCase):
	@patch("retailedge.professional_purchasing.get_operating_context", return_value={})
	@patch("retailedge.professional_purchasing._document_branch", return_value="")
	@patch("erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_return")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_purchase_receipt_return_uses_native_mapper_and_inserts_draft_only(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_branch,
		_mock_context,
	):
		source = _source("Purchase Receipt", "MAT-PRE-0001")
		target = _DraftReturn(
			doctype="Purchase Receipt",
			name="MAT-PRE-RET-0001",
			return_against=source.name,
		)
		mock_get_doc.return_value = source
		mock_mapper.return_value = target

		result = prepare_purchase_return_draft(source.name)

		mock_mapper.assert_called_once_with(source.name)
		self.assertEqual(target.insert_calls, 1)
		self.assertEqual(target.docstatus, 0)
		self.assertEqual(result["return_against"], source.name)
		self.assertEqual(result["posting_status"], "Draft")
		self.assertEqual(result["route"], "/app/purchase-receipt/MAT-PRE-RET-0001")
		self.assertIn("make_purchase_return", result["source_of_truth"])

	@patch("retailedge.professional_purchasing.get_operating_context", return_value={})
	@patch("retailedge.professional_purchasing._document_branch", return_value="")
	@patch("erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_debit_note")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_supplier_debit_note_uses_native_mapper_and_preserves_update_stock(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_branch,
		_mock_context,
	):
		source = _source("Purchase Invoice", "ACC-PINV-0001")
		target = _DraftReturn(
			doctype="Purchase Invoice",
			name="ACC-PINV-RET-0001",
			return_against=source.name,
			update_stock=1,
		)
		mock_get_doc.return_value = source
		mock_mapper.return_value = target

		result = prepare_supplier_debit_note_draft(source.name)

		mock_mapper.assert_called_once_with(source.name)
		self.assertEqual(target.insert_calls, 1)
		self.assertEqual(target.update_stock, 1)
		self.assertTrue(result["update_stock"])
		self.assertEqual(result["posting_status"], "Draft")
		self.assertEqual(result["route"], "/app/purchase-invoice/ACC-PINV-RET-0001")
		self.assertIn("make_debit_note", result["source_of_truth"])

	@patch("erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_return")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_purchase_return_rejects_draft_and_existing_return_sources_before_mapping(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
	):
		for source in (
			_source("Purchase Receipt", "MAT-PRE-DRAFT", docstatus=0),
			_source("Purchase Receipt", "MAT-PRE-RETURN", is_return=1),
		):
			mock_get_doc.return_value = source
			with self.assertRaises(frappe.ValidationError):
				prepare_purchase_return_draft(source.name)
		mock_mapper.assert_not_called()

	@patch("retailedge.professional_purchasing.get_operating_context", return_value={})
	@patch("retailedge.professional_purchasing._document_branch", return_value="")
	@patch("erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_return")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_purchase_return_rejects_invalid_native_mapping(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_mapper,
		_mock_branch,
		_mock_context,
	):
		source = _source("Purchase Receipt", "MAT-PRE-0002")
		mock_get_doc.return_value = source
		invalid_targets = (
			_DraftReturn(doctype="Purchase Receipt", name="RET-WRONG-LINK", return_against="MAT-PRE-OTHER"),
			_DraftReturn(doctype="Purchase Receipt", name="RET-WRONG-COMPANY", return_against=source.name, company="Other Company"),
			_DraftReturn(doctype="Purchase Receipt", name="RET-WRONG-SUPPLIER", return_against=source.name, supplier="SUP-OTHER"),
			_DraftReturn(doctype="Purchase Receipt", name="RET-EMPTY", return_against=source.name, items=[]),
			_DraftReturn(doctype="Purchase Receipt", name="RET-POSITIVE", return_against=source.name, items=[SimpleNamespace(qty=1)]),
		)
		for target in invalid_targets:
			mock_mapper.return_value = target
			with self.assertRaises(frappe.ValidationError):
				prepare_purchase_return_draft(source.name)
			self.assertEqual(target.insert_calls, 0)

	@patch("erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_debit_note")
	@patch("retailedge.professional_purchasing.validate_user_branch_access", side_effect=frappe.PermissionError)
	@patch("retailedge.professional_purchasing._document_branch", return_value="Abuja")
	@patch("retailedge.professional_purchasing.frappe.get_doc")
	@patch("retailedge.professional_purchasing._assert_create")
	@patch("retailedge.professional_purchasing._assert_read")
	def test_supplier_debit_note_rejects_denied_source_branch_before_mapping(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		_mock_branch,
		_mock_branch_access,
		mock_mapper,
	):
		source = _source("Purchase Invoice", "ACC-PINV-ABUJA")
		mock_get_doc.return_value = source

		with self.assertRaises(frappe.PermissionError):
			prepare_supplier_debit_note_draft(source.name)
		mock_mapper.assert_not_called()

	@patch("retailedge.professional_purchasing.search_link")
	@patch("retailedge.professional_purchasing._assert_read")
	@patch("retailedge.professional_purchasing._branch_scoped_filters")
	@patch("retailedge.professional_purchasing._resolve_scope")
	@patch("retailedge.professional_purchasing._permission", return_value=True)
	def test_return_source_search_is_bounded_and_context_filtered(
		self,
		_mock_permission,
		mock_scope,
		mock_filters,
		_mock_read,
		mock_search,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_filters.return_value = ({"company": "Demo Company", "retailedge_branch": "Lagos"}, "retailedge_branch")
		mock_search.return_value = [{"value": "ACC-PINV-0001", "label": "ACC-PINV-0001"}]

		result = search_purchase_return_sources(
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
		self.assertEqual(kwargs["page_length"], MAX_LINK_RESULTS)
		self.assertEqual(kwargs["reference_doctype"], "Purchase Invoice")


if __name__ == "__main__":
	unittest.main()
