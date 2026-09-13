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
	_branch_search_filters,
	_coerce_values,
	_normalise_items,
	_warehouse_search_filters,
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
		self.assertEqual(
			rows,
			[
				{"item_code": "ITEM-001", "qty": 2.0},
				{"item_code": "ITEM-002", "qty": 3.0},
			],
		)
		for invalid in (
			[],
			[{"item_code": "", "qty": 1}],
			[{"item_code": "ITEM-001", "qty": 0}],
			[{"item_code": "ITEM-001", "qty": 1}] * (MAX_ITEMS + 1),
		):
			with self.subTest(rows=len(invalid)):
				with self.assertRaises(frappe.ValidationError):
					_normalise_items(invalid)

	def test_values_payload_accepts_mapping_or_json_object_and_rejects_other_shapes(self):
		self.assertEqual(_coerce_values({"company": "Demo Company"}), {"company": "Demo Company"})
		self.assertEqual(_coerce_values('{"company":"Demo Company"}'), {"company": "Demo Company"})
		for invalid in (["Demo Company"], 42, '"Demo Company"'):
			with self.subTest(value=invalid):
				with self.assertRaises(frappe.ValidationError):
					_coerce_values(invalid)

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
	@patch("retailedge.guided_stock_transfer.resolve_operational_branch")
	@patch("retailedge.guided_stock_transfer._assert_can_create_stock_entry")
	@patch("retailedge.guided_stock_transfer.frappe.db.get_value", return_value="Demo Company")
	@patch("retailedge.guided_stock_transfer.frappe.new_doc")
	def test_create_draft_assembles_material_transfer_once(
		self,
		mock_new_doc,
		_mock_db,
		_mock_create_permission,
		mock_branch_scope,
		_mock_read_permission,
		mock_validate_warehouse,
		mock_item,
	):
		doc = _DraftStockEntry()
		mock_new_doc.return_value = doc
		mock_branch_scope.side_effect = lambda _company, branch="", user=None: {"branch": branch}
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
		self.assertEqual(mock_branch_scope.call_count, 2)
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

	@patch(
		"retailedge.guided_stock_transfer.resolve_operational_branch",
		side_effect=lambda _company, branch="", user=None: {"branch": branch},
	)
	@patch("retailedge.guided_stock_transfer._assert_read_permission")
	@patch("retailedge.guided_stock_transfer._assert_can_create_stock_entry")
	def test_same_source_and_target_warehouse_is_blocked(
		self,
		_mock_create_permission,
		_mock_permission,
		_mock_branch_scope,
	):
		with self.assertRaises(frappe.ValidationError):
			create_simple_stock_transfer_draft(
				{
					"company": "Demo Company",
					"source_warehouse": "Stores - DC",
					"target_warehouse": "Stores - DC",
					"items": [{"item_code": "ITEM-001", "qty": 1}],
				}
			)

	@patch("retailedge.guided_stock_transfer._assert_simple_stock_item")
	@patch("retailedge.guided_stock_transfer._validate_branch_warehouse")
	@patch("retailedge.guided_stock_transfer._assert_read_permission")
	@patch(
		"retailedge.guided_stock_transfer.resolve_operational_branch",
		return_value={"branch": "Lagos"},
	)
	@patch("retailedge.guided_stock_transfer._assert_can_create_stock_entry")
	@patch("retailedge.guided_stock_transfer.frappe.db.get_value", return_value="Demo Company")
	@patch("retailedge.guided_stock_transfer.frappe.new_doc")
	def test_restricted_blank_branch_is_resolved_before_warehouse_validation(
		self,
		mock_new_doc,
		_mock_db,
		_mock_create_permission,
		mock_branch_scope,
		_mock_read_permission,
		mock_validate_warehouse,
		_mock_item,
	):
		doc = _DraftStockEntry()
		mock_new_doc.return_value = doc
		create_simple_stock_transfer_draft(
			{
				"company": "Demo Company",
				"source_warehouse": "Lagos Stores - DC",
				"target_warehouse": "Lagos Transit - DC",
				"items": [{"item_code": "ITEM-001", "qty": 1}],
			}
		)

		self.assertEqual(mock_branch_scope.call_count, 2)
		self.assertEqual(mock_validate_warehouse.call_count, 2)
		for call in mock_validate_warehouse.call_args_list:
			self.assertEqual(call.kwargs["branch"], "Lagos")

	@patch(
		"retailedge.guided_stock_transfer.get_operational_branch_scope",
		return_value={"restricted": True, "allowed_branches": ["Lagos", "Ikeja"]},
	)
	@patch("retailedge.guided_stock_transfer.has_field", return_value=True)
	def test_restricted_multi_branch_warehouse_search_requires_branch_selection(
		self,
		_mock_has_field,
		_mock_scope,
	):
		self.assertIsNone(_warehouse_search_filters("Demo Company", "", "stock@example.com"))

	@patch(
		"retailedge.guided_stock_transfer.get_operational_branch_scope",
		return_value={"restricted": True, "allowed_branches": []},
	)
	@patch("retailedge.guided_stock_transfer.has_field", return_value=True)
	def test_restricted_zero_branch_search_fails_closed(self, _mock_has_field, _mock_scope):
		filters = _branch_search_filters("Demo Company", "stock@example.com")
		self.assertEqual(filters["name"], "__never__")

	def test_branch_and_warehouse_search_fail_closed_without_company(self):
		self.assertIsNone(_warehouse_search_filters("", "", "stock@example.com"))
		self.assertEqual(
			_branch_search_filters("", "stock@example.com"),
			{"name": "__never__"},
		)

	def test_adapter_is_bounded_permission_aware_and_draft_only(self):
		source = (APP_ROOT / "guided_stock_transfer.py").read_text()
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("MAX_ITEMS = 50", source)
		self.assertIn("search_link(", source)
		self.assertIn('query="erpnext.controllers.queries.item_query"', source)
		self.assertIn('filters={"is_stock_item": 1, "disabled": 0}', source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("Invalid Simple Stock Transfer values.", source)
		self.assertIn("doc.insert()", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)
		self.assertNotIn("basic_rate", source)
		self.assertNotIn("valuation_rate", source)

	def test_dialog_uses_shared_edgesuite_components_cascades_and_accepts_safe_prefill(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleStockTransferDialog.vue"
		).read_text()
		self.assertIn("EdgeModal: runtimeComponents.EdgeModal", component)
		self.assertIn("EdgeLinkField: runtimeComponents.EdgeLinkField", component)
		self.assertIn("EdgeChildTable: runtimeComponents.EdgeChildTable", component)
		self.assertIn("prefill: { type: Object, default: () => ({}) }", component)
		self.assertIn("await this.applyPrefill()", component)
		self.assertIn("await this.setSourceWarehouse(sourceWarehouse)", component)
		self.assertIn("await this.setTargetWarehouse(targetWarehouse)", component)
		self.assertIn("setSourceBranch(next)", component)
		self.assertIn("setTargetBranch(next)", component)
		self.assertIn('this.values.source_warehouse = "";', component)
		self.assertIn('this.values.target_warehouse = "";', component)
		self.assertIn("sameWarehouse", component)
		self.assertIn("serial-numbered or batch-managed", component.lower())
		self.assertIn("Open Full Form", component)
		self.assertIn('this.$emit("open-native", "Stock Entry")', component)

	def test_limits_are_small_for_guided_transfer(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_ITEMS, 50)


if __name__ == "__main__":
	unittest.main()
