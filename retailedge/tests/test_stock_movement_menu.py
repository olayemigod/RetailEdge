from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge import workspace_sync
from retailedge.patches import ensure_stock_movement_history_menu_v3 as menu_patch


class TestStockMovementMenu(unittest.TestCase):
	@patch.object(workspace_sync.frappe.db, "exists", return_value=True)
	def test_workspace_report_is_inserted_after_stock_ledger(self, _exists):
		links = [
			{
				"type": "Card Break",
				"label": "Reports & Insights",
				"link_type": "Report",
				"link_count": 1,
			},
			{
				"type": "Link",
				"label": "Stock Ledger",
				"link_to": "Stock Ledger",
				"link_type": "Report",
			},
			{
				"type": "Card Break",
				"label": "Setup & Configuration",
				"link_count": 0,
			},
		]

		result = workspace_sync._ensure_workspace_report_link(links)

		self.assertEqual(result[2]["label"], "Stock Movement History")
		self.assertEqual(result[2]["link_to"], workspace_sync.STOCK_MOVEMENT_REPORT)
		self.assertEqual(result[2]["link_type"], "Report")
		self.assertEqual(result[0]["link_count"], 2)

	@patch.object(workspace_sync.frappe.db, "exists", return_value=True)
	def test_sidebar_report_is_inserted_after_stock_ledger(self, _exists):
		items = [
			{
				"type": "Section Break",
				"label": "Reports & Insights",
			},
			{
				"type": "Link",
				"label": "Stock Ledger",
				"link_to": "Stock Ledger",
				"link_type": "Report",
			},
			{
				"type": "Section Break",
				"label": "Setup & Configuration",
			},
		]

		result = workspace_sync._ensure_sidebar_report_link(items)

		self.assertEqual(result[2]["label"], "Stock Movement History")
		self.assertEqual(result[2]["link_to"], workspace_sync.STOCK_MOVEMENT_REPORT)
		self.assertEqual(result[2]["child"], 1)

	@patch.object(workspace_sync.frappe.db, "exists", return_value=True)
	def test_runtime_menu_registration_is_idempotent(self, _exists):
		links = [{"type": "Card Break", "label": "Reports & Insights", "link_count": 0}]
		items = [{"type": "Section Break", "label": "Reports & Insights"}]

		for _ in range(2):
			links = workspace_sync._ensure_workspace_report_link(links)
			items = workspace_sync._ensure_sidebar_report_link(items)

		workspace_matches = [
			row
			for row in links
			if row.get("type") == "Link" and row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT
		]
		sidebar_matches = [
			row
			for row in items
			if row.get("type") == "Link" and row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT
		]
		self.assertEqual(len(workspace_matches), 1)
		self.assertEqual(len(sidebar_matches), 1)

	@patch.object(menu_patch.frappe.db, "exists", return_value=True)
	@patch.object(menu_patch.frappe, "clear_cache")
	@patch.object(menu_patch, "sync_retailedge_workspace_layout")
	@patch.object(menu_patch.frappe, "reload_doc")
	def test_versioned_patch_reloads_report_and_runs_actual_menu_builder(
		self,
		reload_doc,
		sync_workspace,
		clear_cache,
		_exists,
	):
		menu_patch.execute()

		reload_doc.assert_called_once_with(
			"retailedge",
			"report",
			"retailedge_stock_movement_history",
		)
		sync_workspace.assert_called_once_with()
		clear_cache.assert_any_call(doctype="Workspace")
		clear_cache.assert_any_call(doctype="Workspace Sidebar")
