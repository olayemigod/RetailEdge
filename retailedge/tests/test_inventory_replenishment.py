from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import inventory_replenishment


class _Meta:
	def __init__(self, fields=(), table_field=None):
		self.fields = set(fields)
		self.table_field = table_field

	def has_field(self, fieldname):
		return fieldname in self.fields

	def get_field(self, fieldname):
		return self.table_field if fieldname == "reorder_levels" else None


class TestInventoryReplenishment(unittest.TestCase):
	def test_direct_rule_uses_erpnext_projected_qty_and_effective_reorder_quantity(self):
		item = frappe._dict(item_name="Item One", item_group="Products", stock_uom="Nos")
		rule = frappe._dict(
			warehouse="Lagos - TC",
			warehouse_group="",
			warehouse_reorder_level=10,
			warehouse_reorder_qty=4,
			material_request_type="Purchase",
		)
		result = inventory_replenishment._evaluate_rule(
			item_code="ITEM-1",
			item=item,
			rule=rule,
			projected_qty=-5,
			inherited_from="",
		)
		self.assertTrue(result["reorder_triggered"])
		self.assertEqual(result["shortfall_qty"], 15)
		self.assertEqual(result["recommended_reorder_qty"], 15)
		self.assertEqual(result["evaluation_status"], "Reorder Now")

	def test_at_reorder_level_triggers_like_erpnext_v16(self):
		result = inventory_replenishment._evaluate_rule(
			item_code="ITEM-1",
			item=frappe._dict(item_name="Item One", item_group="Products", stock_uom="Nos"),
			rule=frappe._dict(
				warehouse="Lagos - TC",
				warehouse_group="",
				warehouse_reorder_level=10,
				warehouse_reorder_qty=20,
				material_request_type="Purchase",
			),
			projected_qty=10,
			inherited_from="",
		)
		self.assertTrue(result["reorder_triggered"])
		self.assertEqual(result["recommended_reorder_qty"], 20)

	def test_warehouse_group_rule_is_not_falsely_scored_from_partial_scope(self):
		result = inventory_replenishment._evaluate_rule(
			item_code="ITEM-1",
			item=frappe._dict(item_name="Item One", item_group="Products", stock_uom="Nos"),
			rule=frappe._dict(
				warehouse="Lagos - TC",
				warehouse_group="All Warehouses - TC",
				warehouse_reorder_level=10,
				warehouse_reorder_qty=20,
				material_request_type="Purchase",
			),
			projected_qty=0,
			inherited_from="",
		)
		self.assertFalse(result["reorder_triggered"])
		self.assertEqual(result["evaluation_status"], "Unavailable")
		self.assertIsNone(result["projected_qty"])
		self.assertIsNone(result["recommended_reorder_qty"])

	@patch("retailedge.inventory_replenishment._get_projected_qty")
	@patch("retailedge.inventory_replenishment._get_reorder_rules")
	@patch("retailedge.inventory_replenishment._get_permitted_templates")
	@patch("retailedge.inventory_replenishment._get_permitted_items")
	@patch("retailedge.inventory_replenishment._resolve_warehouse_scope", return_value=["Lagos - TC"])
	@patch("retailedge.inventory_replenishment._assert_reorder_runtime_contract")
	@patch("retailedge.inventory_replenishment._assert_report_access")
	@patch("retailedge.inventory_replenishment._validate_filters")
	def test_service_inherits_template_rule_only_when_variant_has_no_direct_rule(
		self,
		_validate,
		_assert_access,
		_assert_runtime,
		_resolve_warehouses,
		get_items,
		get_templates,
		get_rules,
		get_projected,
	):
		get_items.return_value = [
			frappe._dict(
				name="VARIANT-1",
				item_name="Variant One",
				item_group="Products",
				stock_uom="Nos",
				variant_of="TEMPLATE-1",
				has_variants=0,
				end_of_life="2099-12-31",
			)
		]
		get_templates.return_value = {
			"TEMPLATE-1": frappe._dict(name="TEMPLATE-1", has_variants=1)
		}
		get_rules.return_value = {
			"TEMPLATE-1": [
				frappe._dict(
					warehouse="Lagos - TC",
					warehouse_group="",
					warehouse_reorder_level=10,
					warehouse_reorder_qty=20,
					material_request_type="Purchase",
				)
			]
		}
		get_projected.return_value = {("VARIANT-1", "Lagos - TC"): 5}

		result = inventory_replenishment.get_inventory_replenishment(
			{"company": "Test Company", "branch": "Lagos"}
		)
		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["rows"][0]["inherited_from_template"], "TEMPLATE-1")
		self.assertTrue(result["rows"][0]["reorder_triggered"])
		self.assertEqual(result["items"][0]["replenishment_status"], "Reorder Now")
		self.assertFalse(result["metadata"]["creates_material_request"])
		self.assertTrue(result["metadata"]["runtime_contract_validated"])
		_assert_runtime.assert_called_once()

	def test_runtime_contract_accepts_expected_erpnext_item_reorder_schema(self):
		setattr(frappe.local, "retailedge_r10_reorder_runtime_contract", False)
		item_meta = _Meta(table_field=frappe._dict(fieldtype="Table", options="Item Reorder"))
		reorder_meta = _Meta(fields=inventory_replenishment.REQUIRED_REORDER_FIELDS)
		with patch(
			"retailedge.inventory_replenishment.frappe.get_meta",
			side_effect=[item_meta, reorder_meta],
		):
			inventory_replenishment._assert_reorder_runtime_contract()
		self.assertTrue(getattr(frappe.local, "retailedge_r10_reorder_runtime_contract"))

	def test_runtime_contract_fails_closed_when_required_reorder_field_is_missing(self):
		setattr(frappe.local, "retailedge_r10_reorder_runtime_contract", False)
		item_meta = _Meta(table_field=frappe._dict(fieldtype="Table", options="Item Reorder"))
		reorder_meta = _Meta(
			fields=[
				fieldname
				for fieldname in inventory_replenishment.REQUIRED_REORDER_FIELDS
				if fieldname != "material_request_type"
			]
		)
		with (
			patch(
				"retailedge.inventory_replenishment.frappe.get_meta",
				side_effect=[item_meta, reorder_meta],
			),
			self.assertRaises(frappe.ValidationError),
		):
			inventory_replenishment._assert_reorder_runtime_contract()

	def test_item_aggregation_prioritises_triggered_rules_without_mutating_source_truth(self):
		rows = [
			{
				"item_code": "ITEM-1",
				"reorder_triggered": True,
				"recommended_reorder_qty": 12,
				"evaluation_status": "Reorder Now",
			},
			{
				"item_code": "ITEM-1",
				"reorder_triggered": False,
				"recommended_reorder_qty": 0,
				"evaluation_status": "Unavailable",
			},
		]
		items = inventory_replenishment._aggregate_items(
			rows,
			item_map={
				"ITEM-1": frappe._dict(item_name="Item One", item_group="Products", stock_uom="Nos")
			},
		)
		self.assertEqual(items[0]["triggered_location_count"], 1)
		self.assertEqual(items[0]["unavailable_rule_count"], 1)
		self.assertEqual(items[0]["recommended_reorder_qty"], 12)
		self.assertEqual(items[0]["replenishment_status"], "Reorder Now")

	def test_source_is_read_only_bounded_parent_scoped_and_runtime_guarded(self):
		source = Path(inventory_replenishment.__file__).read_text(encoding="utf-8")
		for forbidden in (
			"frappe.get_all(",
			"frappe.db.sql(",
			"ignore_permissions=True",
			"frappe.db.commit(",
			".submit(",
			"frappe.new_doc(",
		):
			self.assertNotIn(forbidden, source)
		self.assertIn('frappe.get_list(\n\t\t"Item"', source)
		self.assertIn('frappe.get_list(\n\t\t"Bin"', source)
		self.assertIn("frappe.qb.DocType(REORDER_CHILD_DOCTYPE)", source)
		self.assertIn("_assert_reorder_runtime_contract()", source)
		self.assertIn("reorder.parent.isin(parent_names)", source)
		self.assertIn("MAX_REORDER_RULES = 20000", source)


if __name__ == "__main__":
	unittest.main()