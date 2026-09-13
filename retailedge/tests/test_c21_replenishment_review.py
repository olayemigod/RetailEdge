from __future__ import annotations

import unittest
from pathlib import Path

from retailedge.stock_position import (
	MAX_REORDER_SCAN_ROWS,
	_evaluate_direct_reorder_rules,
	_matches_stock_status,
	_row_has_stock_signal,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestC21ReplenishmentReview(unittest.TestCase):
	def test_direct_rule_due_below_level_uses_configured_qty_when_larger(self):
		result = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 5,
					"warehouse_reorder_qty": 10,
					"material_request_type": "Purchase",
				}
			],
			{"Main - RET": 4},
		)
		self.assertEqual(result["replenishment_status"], "Reorder Due")
		self.assertEqual(result["reorder_due"], 1)
		self.assertEqual(result["reorder_due_location_count"], 1)
		self.assertEqual(result["suggested_reorder_qty"], 10)
		self.assertEqual(result["reorder_due_warehouses"], "Main - RET")

	def test_direct_rule_due_at_level_and_deficiency_can_exceed_configured_qty(self):
		at_level = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 5,
					"warehouse_reorder_qty": 2,
					"material_request_type": "Purchase",
				}
			],
			{"Main - RET": 5},
		)
		self.assertEqual(at_level["reorder_due"], 1)
		self.assertEqual(at_level["suggested_reorder_qty"], 2)

		deficiency = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 10,
					"warehouse_reorder_qty": 3,
					"material_request_type": "Purchase",
				}
			],
			{"Main - RET": 2},
		)
		self.assertEqual(deficiency["reorder_due"], 1)
		self.assertEqual(deficiency["suggested_reorder_qty"], 8)

	def test_configured_rule_above_level_and_zero_zero_rule_are_not_due(self):
		above = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 5,
					"warehouse_reorder_qty": 10,
					"material_request_type": "Purchase",
				}
			],
			{"Main - RET": 6},
		)
		self.assertEqual(above["replenishment_status"], "Configured")
		self.assertEqual(above["reorder_due"], 0)

		zero_rule = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 0,
					"warehouse_reorder_qty": 0,
					"material_request_type": "Purchase",
				}
			],
			{"Main - RET": 0},
		)
		self.assertEqual(zero_rule["replenishment_status"], "Configured")
		self.assertEqual(zero_rule["reorder_due"], 0)

	def test_missing_bin_is_zero_and_multi_location_suggestions_are_aggregated(self):
		result = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 4,
					"warehouse_reorder_qty": 2,
					"material_request_type": "Purchase",
				},
				{
					"warehouse": "Branch - RET",
					"warehouse_group": "",
					"warehouse_reorder_level": 7,
					"warehouse_reorder_qty": 3,
					"material_request_type": "Transfer",
				},
			],
			{"Main - RET": 0, "Branch - RET": 5},
		)
		self.assertEqual(result["reorder_due"], 1)
		self.assertEqual(result["reorder_due_location_count"], 2)
		self.assertEqual(result["suggested_reorder_qty"], 7)
		self.assertEqual(result["reorder_request_types"], "Purchase, Transfer")

	def test_group_availability_rule_is_not_reinterpreted(self):
		result = _evaluate_direct_reorder_rules(
			[
				{
					"warehouse": "Main - RET",
					"warehouse_group": "All Stores - RET",
					"warehouse_reorder_level": 10,
					"warehouse_reorder_qty": 10,
					"material_request_type": "Purchase",
				}
			],
			{"Main - RET": 0},
		)
		self.assertEqual(result["replenishment_status"], "No Direct Rule")
		self.assertEqual(result["direct_reorder_rule_count"], 0)
		self.assertEqual(result["reorder_due"], 0)

	def test_reorder_due_survives_zero_row_filter_and_status_filter(self):
		row = {
			"actual_qty": 0,
			"reserved_qty": 0,
			"ordered_qty": 0,
			"projected_qty": 0,
			"reorder_due": 1,
			"stock_status": "Out of Stock",
		}
		self.assertTrue(_row_has_stock_signal(row, show_costs=False))
		self.assertTrue(_matches_stock_status(row, "Reorder Due"))

	def test_backend_scope_scans_and_read_only_contract(self):
		source = (APP_ROOT / "stock_position.py").read_text()
		self.assertIn('"Item Reorder"', source)
		self.assertIn('reorder_filters: dict[str, Any] = {"warehouse": ["in", warehouses]}', source)
		self.assertIn('return [row for row in rows if row.warehouse and not row.warehouse_group]', source)
		self.assertIn("limit=MAX_REORDER_SCAN_ROWS + 1", source)
		self.assertEqual(MAX_REORDER_SCAN_ROWS, 10000)
		self.assertIn('if cint(row.get("reorder_due")):', source)
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
		):
			self.assertNotIn(forbidden, source)

	def test_edgesuite_ui_exposes_replenishment_and_preserves_export(self):
		component = (APP_ROOT / "public" / "js" / "stock_position" / "StockPositionReport.vue").read_text()
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertIn("EdgeReportShell", component)
		self.assertIn("EdgeExportMenu", component)
		self.assertIn('"Reorder Due"', component)
		self.assertIn("ERPNext Bin + direct Item Reorder rules", component)
		self.assertIn("loadExportDataset", component)
		self.assertIn("openReportCell", component)
		for forbidden in ("frappe.ui.Dialog", "frappe.prompt", "frappe.msgprint", "window.EdgeUI"):
			self.assertNotIn(forbidden, component)


if __name__ == "__main__":
	unittest.main()
