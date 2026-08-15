from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_stock_transfer import (
	MATERIAL_TRANSFER,
	MAX_ITEMS,
	MAX_LINK_RESULTS,
	_assert_simple_stock_item,
	_normalise_items,
	create_simple_stock_transfer_draft,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class _DraftStockEntry(SimpleNamespace):
	doctype = "Stock Entry"

	def __init__(self):
		super().__init__(
			name="MAT-STE-GUIDED-0001",
			docstatus=0,
			items=[],
			insert_calls=0,
		)

	def append(self, table, row):
		self.items.append(frappe._dict(row))
		return self.items[-1]

	def insert(self):
		self.insert_calls += 1
		return self


class TestGuidedStockTransfer(unittest.TestCase):
	def test_normalise_items_requires_positive_stock_rows(self):
		rows = _normalise_items(
			[
				{"item_code": "ITEM-001", "qty": 2},
				{"item_code": "ITEM-002", "qty": "3"},
			]
		)
		self.assertEqual(rows, [
			{"item_code": "ITEM-001", "qty": 2.0},
			{"item_code": "ITEM-002", "qty": 3.0},
		])
		for invalid in (
			[],
			[{"item_code": "", "qty": 1}],
			[{"item_code": "ITEM-001", "qty": 0}],
			[{"item_code": "ITEM-001", "qty": 1}] * (MAX_ITEMS + 1),
		):
			with self.subTest(rows=len(invalid)):
				with self.assertRaises(frappe.ValidationError):
					_normalise_items(invalid)

	@patch("retailedge.guided_stock_transfer._assert_read_permission")
	@patch("retailedge.guided_stock_transfer.frappe.db.get_value")
	def test_serial_or_batch_items_require_full_stock_entry(self, mock_get_value, _mock_permission):
		for row in (
			frappe._dict(is_stock_item=1, disabled=0, has_serial_no=1, has_batch_no=0),
			frappe._dict(is_stock_item=1, disabled=0, has_serial_no=0, has_batch_no=1),
		):
			mock_get_value.return_value = row
			with self.assertRaises(frappe.ValidationError):
				_assert_simple_stock_item("TRACKED-ITEM")

	@patch("retailedge.guided_stock_transfer._assert_simple_stock_item")
	@patch("retailedge.guided_stock_transfer._validate_branch_warehouse")
	@patch("retailedge.guided_stock_transfer._assert_read_permission")
	@patch("retailedge.guided_stock_transfer.validate_user_branch_access")
	@patch("retailedge.guided_stock_transfer._assert_can_create_stock_entry")
	@patch("retailedge.guided_stock_transfer.frappe.db.get_value", return_value="Demo Company")
	@patch("retailedge.guided_stock_transfer.frappe.new_doc")
	def test_create_draft_assembles_material_transfer_once(
		self,
		mock_new_doc,
		_mock_db,
		_mock_create_permission,
		mock_branch_access,
		_mock_read_permission,
		mock_validate_warehouse,
		mock_item,
	):
		doc = _DraftStockEntry()
		mock_new_doc.return_value = doc
		result = create_simple_stock_transfer_draft(
			{
				"company": "Demo Company",
				"posting_date": "2026-08-15",
				"source_branch": "Lagos",
				"target_branch": "Abuja",
				"source_warehouse": "Lagos Stores - DC",
				"target_warehouse": "Abuja Stores - DC",
				"remarks": "Restock Abuja",
				"items": [
					{"item_code": "ITEM-001", "qty": 5},
					{"item_code": "ITEM-002", "qty": 2},
				],
			}
		)
		mock_new_doc.assert_called_once_with("Stock Entry")
		self.assertEqual(mock_branch_access.call_count, 2)
		self.assertEqual(mock_validate_warehouse.call_count, 2)
		self.assertEqual(mock_item.call_count, 2)
		self.assertEqual(doc.insert_calls, 1)
		self.assertEqual(doc.purpose, MATERIAL_TRANSFER)
		self.assertEqual(doc.stock_entry_type, MATERIAL_TRANSFER)
		self.assertEqual(doc.from_warehouse, "Lagos Stores - DC")
		self.assertEqual(doc.to_warehouse, "Abuja Stores - DC")
		self.assertEqual(len(doc.items), 2)
		self.assertEqual(doc.items[0].s_warehouse, "Lagos Stores - DC")
		self.assertEqual(doc.items[0].t_warehouse, "Abuja Stores - DC")
		self.assertEqual(result["docstatus"], 0)
		self.assertEqual(result["name"], doc.name)

	@patch("retailedge.guided_stock_transfer._assert_read_permission")
	@patch("retailedge.guided_stock_transfer._assert_can_create_stock_entry")
	def test_same_source_and_target_warehouse_is_blocked(self, _mock_permission, _mock_create_permission):
		with self.assertRaises(frappe.ValidationError):
			create_simple_stock_transfer_draft(
				{
					"company": "Demo Company",
					"source_warehouse": "Stores - DC",
					"target_warehouse": "Stores - DC",
					"items": [{"item_code": "ITEM-001", "qty": 1}],
				}
			)

	def test_adapter_is_bounded_permission_aware_and_draft_only(self):
		source = (APP_ROOT / "guided_stock_transfer.py").read_text()
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("MAX_ITEMS = 50", source)
		self.assertIn("search_link(", source)
		self.assertIn('query="erpnext.controllers.queries.item_query"', source)
		self.assertIn('filters={"is_stock_item": 1, "disabled": 0}', source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)
		self.assertNotIn("basic_rate", source)
		self.assertNotIn("valuation_rate", source)

	def test_dialog_uses_shared_edgesuite_components_and_cascades_branches(self):
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleStockTransferDialog.vue"
		).read_text()
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn("EdgeLinkField: runtimeComponents.EdgeLinkField", component)
		self.assertIn("EdgeChildTable: runtimeComponents.EdgeChildTable", component)
		self.assertIn("setSourceBranch(next)", component)
		self.assertIn("setTargetBranch(next)", component)
		self.assertIn('this.values.source_warehouse = "";', component)
		self.assertIn('this.values.target_warehouse = "";', component)
		self.assertIn("sameWarehouse", component)
		self.assertIn("serial-numbered or batch-managed", component)
		self.assertIn("Open Full Form", component)
		self.assertIn('this.$emit("open-native", "Stock Entry")', component)

	def test_limits_are_small_for_guided_transfer(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_ITEMS, 50)


if __name__ == "__main__":
	unittest.main()
