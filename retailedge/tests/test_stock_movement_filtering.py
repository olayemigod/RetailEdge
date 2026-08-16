from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPORT_JS = (
	APP_ROOT
	/ "retailedge"
	/ "report"
	/ "retailedge_stock_movement_history"
	/ "retailedge_stock_movement_history.js"
)


class TestStockMovementFiltering(unittest.TestCase):
	def test_filter_queries_are_permission_aware_and_bounded(self):
		source = (APP_ROOT / "stock_movement_filters.py").read_text(encoding="utf-8")
		for contract in (
			"MAX_FILTER_RESULTS = 20",
			"validate_user_branch_access",
			"get_user_allowed_branches",
			"user_has_global_branch_access",
			"get_branch_profile_defaults",
			"frappe.get_list(",
			"limit_page_length=_page_len(page_len)",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("limit_page_length=0", source)

	def test_branch_and_warehouse_filters_use_server_queries(self):
		content = REPORT_JS.read_text(encoding="utf-8")
		self.assertIn("retailedge.stock_movement_filters.branch_query", content)
		self.assertIn("retailedge.stock_movement_filters.warehouse_query", content)
		self.assertIn("company: frappe.query_report.get_filter_value", content)
		self.assertIn('branch: frappe.query_report.get_filter_value("branch")', content)

	def test_stock_movement_branch_and_warehouse_cascade_both_ways(self):
		content = REPORT_JS.read_text(encoding="utf-8")
		for contract in (
			"handleStockMovementBranchChange",
			"handleStockMovementWarehouseChange",
			"resolveStockMovementContext",
			"resolve_branch_warehouse_selection",
			'preference: "default"',
			"retailedgeStockMovementCascade",
			"retailedgeStockMovementCascadeToken",
		):
			self.assertIn(contract, content)

	def test_existing_stock_movement_accounting_backend_is_not_replaced(self):
		content = REPORT_JS.read_text(encoding="utf-8")
		self.assertIn('frappe.query_reports["RetailEdge Stock Movement History"]', content)
		backend = (
			APP_ROOT
			/ "retailedge"
			/ "report"
			/ "retailedge_stock_movement_history"
			/ "retailedge_stock_movement_history.py"
		).read_text(encoding="utf-8")
		self.assertIn("get_stock_balance", backend)
		self.assertIn("Stock Ledger Entry", backend)
		self.assertIn("apply_running_balances", backend)


if __name__ == "__main__":
	unittest.main()
