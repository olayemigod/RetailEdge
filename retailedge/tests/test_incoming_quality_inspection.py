from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.incoming_quality_inspection import (
	MAX_LINK_RESULTS,
	MAX_QUALITY_INSPECTION_ROWS,
	create_incoming_quality_inspections,
	get_incoming_quality_capability,
	get_incoming_quality_receipt_context,
	search_incoming_quality_receipts,
)


def _item(
	name: str,
	item_code: str,
	*,
	qty: float = 5,
	quality_inspection: str = "",
	sample_quantity: float = 2,
):
	return SimpleNamespace(
		name=name,
		item_code=item_code,
		item_name=f"{item_code} name",
		qty=qty,
		quality_inspection=quality_inspection,
		sample_quantity=sample_quantity,
		description=f"{item_code} description",
		serial_no="SER-001\nSER-002" if item_code == "ITEM-001" else "",
		batch_no="BATCH-001" if item_code == "ITEM-001" else "",
		uom="Nos",
		stock_uom="Nos",
		warehouse="Stores - DEMO",
	)


def _receipt(
	*,
	docstatus: int = 0,
	is_return: int = 0,
	items=None,
):
	return SimpleNamespace(
		doctype="Purchase Receipt",
		name="MAT-PRE-0001",
		docstatus=docstatus,
		is_return=is_return,
		company="Demo Company",
		supplier="SUP-001",
		supplier_name="Supplier One",
		posting_date="2026-08-31",
		items=items or [_item("PRI-ROW-1", "ITEM-001")],
	)


class TestIncomingQualityInspection(unittest.TestCase):
	@patch("retailedge.incoming_quality_inspection._permission")
	def test_capability_requires_receipt_read_and_quality_create(self, mock_permission):
		mock_permission.side_effect = lambda doctype, ptype, name=None: (doctype, ptype) in {
			("Purchase Receipt", "read"),
			("Quality Inspection", "create"),
		}
		result = get_incoming_quality_capability()
		self.assertTrue(result["can_prepare_incoming_quality"])
		self.assertEqual(result["max_rows"], MAX_QUALITY_INSPECTION_ROWS)

		mock_permission.side_effect = lambda doctype, ptype, name=None: doctype == "Purchase Receipt"
		result = get_incoming_quality_capability()
		self.assertFalse(result["can_prepare_incoming_quality"])

	@patch("retailedge.incoming_quality_inspection.search_link")
	@patch("retailedge.incoming_quality_inspection._assert_read")
	@patch("retailedge.incoming_quality_inspection._branch_scoped_filters")
	@patch("retailedge.incoming_quality_inspection._resolve_scope")
	@patch("retailedge.incoming_quality_inspection._assert_quality_permissions")
	def test_source_search_is_bounded_to_draft_non_return_receipts(
		self,
		_mock_permissions,
		mock_scope,
		mock_filters,
		_mock_read,
		mock_search,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_filters.return_value = ({"company": "Demo Company", "retailedge_branch": "Lagos"}, "retailedge_branch")
		mock_search.return_value = [{"value": "MAT-PRE-0001", "label": "MAT-PRE-0001"}]

		result = search_incoming_quality_receipts(
			"MAT",
			company="Demo Company",
			branch="Lagos",
			supplier="SUP-001",
		)

		self.assertEqual(result[0]["value"], "MAT-PRE-0001")
		kwargs = mock_search.call_args.kwargs
		self.assertEqual(kwargs["filters"]["docstatus"], 0)
		self.assertEqual(kwargs["filters"]["is_return"], 0)
		self.assertEqual(kwargs["filters"]["supplier"], "SUP-001")
		self.assertEqual(kwargs["filters"]["retailedge_branch"], "Lagos")
		self.assertEqual(kwargs["page_length"], MAX_LINK_RESULTS)
		self.assertEqual(kwargs["reference_doctype"], "Quality Inspection")

	@patch("retailedge.incoming_quality_inspection.check_item_quality_inspection")
	@patch("retailedge.incoming_quality_inspection._document_branch", return_value="Lagos")
	@patch("retailedge.incoming_quality_inspection._resolve_scope")
	@patch("retailedge.incoming_quality_inspection.frappe.get_doc")
	@patch("retailedge.incoming_quality_inspection._assert_create")
	@patch("retailedge.incoming_quality_inspection._assert_read")
	def test_context_uses_native_eligibility_and_excludes_already_inspected_rows(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_scope,
		_mock_branch,
		mock_check,
	):
		receipt = _receipt(
			items=[
				_item("PRI-ROW-1", "ITEM-001", qty=5, sample_quantity=2),
				_item("PRI-ROW-2", "ITEM-002", qty=3, quality_inspection="MAT-QA-0009"),
			]
		)
		mock_get_doc.return_value = receipt
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_check.side_effect = lambda doctype, docstatus, items: items

		result = get_incoming_quality_receipt_context(receipt.name)

		mock_check.assert_called_once()
		self.assertEqual(result["eligible_count"], 1)
		self.assertEqual(result["items"][0]["child_row_reference"], "PRI-ROW-1")
		self.assertEqual(result["items"][0]["suggested_sample_size"], 2)
		self.assertNotIn("serial_no", result["items"][0])
		self.assertTrue(result["items"][0]["has_serial_no"])

	@patch("retailedge.incoming_quality_inspection.make_quality_inspections")
	@patch("retailedge.incoming_quality_inspection.check_item_quality_inspection")
	@patch("retailedge.incoming_quality_inspection._document_branch", return_value="Lagos")
	@patch("retailedge.incoming_quality_inspection._resolve_scope")
	@patch("retailedge.incoming_quality_inspection.frappe.get_doc")
	@patch("retailedge.incoming_quality_inspection._assert_create")
	@patch("retailedge.incoming_quality_inspection._assert_read")
	def test_create_reconstructs_native_rows_and_creates_drafts_only(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_scope,
		_mock_branch,
		mock_check,
		mock_make,
	):
		receipt = _receipt(items=[_item("PRI-ROW-1", "ITEM-001", qty=5)])
		mock_get_doc.return_value = receipt
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_check.side_effect = lambda doctype, docstatus, items: items
		mock_make.return_value = ["MAT-QA-0001"]

		result = create_incoming_quality_inspections(
			receipt.name,
			[{"child_row_reference": "PRI-ROW-1", "sample_size": 2}],
		)

		kwargs = mock_make.call_args.kwargs
		self.assertEqual(kwargs["company"], "Demo Company")
		self.assertEqual(kwargs["doctype"], "Purchase Receipt")
		self.assertEqual(kwargs["docname"], receipt.name)
		self.assertEqual(kwargs["inspection_type"], "Incoming")
		self.assertEqual(kwargs["items"][0]["item_code"], "ITEM-001")
		self.assertEqual(kwargs["items"][0]["qty"], 5)
		self.assertEqual(kwargs["items"][0]["batch_no"], "BATCH-001")
		self.assertEqual(kwargs["items"][0]["sample_size"], 2)
		self.assertEqual(result["created_count"], 1)
		self.assertEqual(result["created"][0]["docstatus"], 0)
		self.assertEqual(result["created"][0]["posting_status"], "Draft")

	@patch("retailedge.incoming_quality_inspection._document_branch", return_value="Lagos")
	@patch("retailedge.incoming_quality_inspection._resolve_scope")
	@patch("retailedge.incoming_quality_inspection.frappe.get_doc")
	@patch("retailedge.incoming_quality_inspection._assert_create")
	@patch("retailedge.incoming_quality_inspection._assert_read")
	def test_submitted_and_return_receipts_are_rejected(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_scope,
		_mock_branch,
	):
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		for receipt in (_receipt(docstatus=1), _receipt(is_return=1)):
			mock_get_doc.return_value = receipt
			with self.assertRaises(frappe.ValidationError):
				get_incoming_quality_receipt_context(receipt.name)

	def test_selection_payload_cannot_override_authoritative_receipt_fields(self):
		with self.assertRaises(frappe.ValidationError):
			create_incoming_quality_inspections(
				"MAT-PRE-0001",
				[
					{
						"child_row_reference": "PRI-ROW-1",
						"sample_size": 1,
						"item_code": "SPOOFED-ITEM",
					}
				],
			)

	@patch("retailedge.incoming_quality_inspection.check_item_quality_inspection")
	@patch("retailedge.incoming_quality_inspection._document_branch", return_value="Lagos")
	@patch("retailedge.incoming_quality_inspection._resolve_scope")
	@patch("retailedge.incoming_quality_inspection.frappe.get_doc")
	@patch("retailedge.incoming_quality_inspection._assert_create")
	@patch("retailedge.incoming_quality_inspection._assert_read")
	def test_invalid_sample_sizes_and_duplicate_rows_are_rejected(
		self,
		_mock_read,
		_mock_create,
		mock_get_doc,
		mock_scope,
		_mock_branch,
		mock_check,
	):
		receipt = _receipt(items=[_item("PRI-ROW-1", "ITEM-001", qty=2)])
		mock_get_doc.return_value = receipt
		mock_scope.return_value = ("Demo Company", "Lagos", ["Lagos"], False)
		mock_check.side_effect = lambda doctype, docstatus, items: items

		for sample_size in (0, -1, 3):
			with self.assertRaises(frappe.ValidationError):
				create_incoming_quality_inspections(
					receipt.name,
					[{"child_row_reference": "PRI-ROW-1", "sample_size": sample_size}],
				)

		with self.assertRaises(frappe.ValidationError):
			create_incoming_quality_inspections(
				receipt.name,
				[
					{"child_row_reference": "PRI-ROW-1", "sample_size": 1},
					{"child_row_reference": "PRI-ROW-1", "sample_size": 1},
				],
			)


if __name__ == "__main__":
	unittest.main()
