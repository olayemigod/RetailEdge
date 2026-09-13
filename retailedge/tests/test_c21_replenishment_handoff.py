from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.replenishment_handoff import (
	MAX_REPLENISHMENT_HANDOFF_RULES,
	_due_rule_payloads,
	_native_material_request_type,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestC21ReplenishmentHandoff(unittest.TestCase):
	def test_handoff_reuses_due_math_and_missing_bin_zero(self):
		rules = [
			{
				"warehouse": "Main - RET",
				"warehouse_group": "",
				"warehouse_reorder_level": 8,
				"warehouse_reorder_qty": 3,
				"material_request_type": "Purchase",
			},
			{
				"warehouse": "Branch - RET",
				"warehouse_group": "",
				"warehouse_reorder_level": 5,
				"warehouse_reorder_qty": 10,
				"material_request_type": "Purchase",
			},
		]
		due = _due_rule_payloads(rules, {"Branch - RET": 4})
		self.assertEqual(len(due), 2)
		self.assertEqual(due[0]["projected_qty"], 0)
		self.assertEqual(due[0]["suggested_qty"], 8)
		self.assertEqual(due[1]["suggested_qty"], 10)

	def test_transfer_maps_to_native_material_transfer(self):
		self.assertEqual(_native_material_request_type("Transfer"), "Material Transfer")
		self.assertEqual(_native_material_request_type("Purchase"), "Purchase")
		self.assertEqual(_native_material_request_type("Material Issue"), "Material Issue")
		self.assertEqual(MAX_REPLENISHMENT_HANDOFF_RULES, 20)

	def test_handoff_is_permission_checked_revalidated_and_read_only(self):
		source = (APP_ROOT / "replenishment_handoff.py").read_text()
		self.assertIn('frappe.has_permission("Material Request", "create")', source)
		self.assertIn("_resolve_warehouse_scope(resolved_filters)", source)
		self.assertIn("_load_direct_reorder_rules", source)
		self.assertIn("_evaluate_direct_reorder_rules", source)
		self.assertIn("Replenishment is no longer due", source)
		self.assertIn("multiple Material Request Types", source)
		self.assertIn('"handoff_mode": "unsaved_native_form"', source)
		self.assertIn('"docstatus": 0', source)
		for forbidden in (
			"reorder_item(",
			"_reorder_item(",
			"create_material_request(",
			"frappe.new_doc(",
			".insert(",
			".submit(",
			"ignore_permissions=True",
			"frappe.db.set_value(",
			"frappe.db.commit(",
			"auto_created_via_reorder",
		):
			self.assertNotIn(forbidden, source)

	def test_branch_profile_wrapper_is_post_only_and_constrains_scope(self):
		source = (APP_ROOT / "operating_report_defaults.py").read_text()
		self.assertIn("get_replenishment_handoff_context as _base_replenishment_handoff_context", source)
		self.assertIn("get_replenishment_material_request_handoff as _base_replenishment_material_request_handoff", source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("filters=_constrain_report_filters(filters)", source)

	def test_edgesuite_opens_unsaved_native_material_request_without_classic_dialog(self):
		component = (APP_ROOT / "public" / "js" / "stock_position" / "StockPositionReport.vue").read_text()
		self.assertIn("canCreateMaterialRequest", component)
		self.assertIn("get_replenishment_handoff_context", component)
		self.assertIn("get_replenishment_material_request_handoff", component)
		self.assertIn('type: "POST"', component)
		self.assertIn('frappe.model.get_new_doc("Material Request")', component)
		self.assertIn('frappe.model.add_child(doc, "Material Request Item", "items")', component)
		self.assertIn('frappe.set_route("Form", "Material Request", doc.name)', component)
		self.assertIn('column.fieldname === "replenishment_status"', component)
		for forbidden in ("frappe.ui.Dialog", "frappe.prompt", "frappe.msgprint", "window.EdgeUI"):
			self.assertNotIn(forbidden, component)


if __name__ == "__main__":
	unittest.main()
