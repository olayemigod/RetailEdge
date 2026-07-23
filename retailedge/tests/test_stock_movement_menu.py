from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.patches import ensure_stock_movement_history_menu_v2 as menu_patch
from retailedge.patches import sync_retailedge_workspace as workspace_sync


class TestStockMovementMenu(unittest.TestCase):
	@patch(
		"retailedge.patches.sync_retailedge_workspace.frappe.db.exists",
		return_value=True,
	)
	def test_report_is_inserted_after_stock_ledger_in_reports_menu(self, _exists):
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

		result = workspace_sync._ensure_report_menu_link(
			links,
			report_name=workspace_sync.STOCK_MOVEMENT_REPORT,
			label="Stock Movement History",
			section_label=workspace_sync.REPORTS_SECTION_LABEL,
			after_link_to="Stock Ledger",
		)

		self.assertEqual(result[2]["label"], "Stock Movement History")
		self.assertEqual(result[2]["link_to"], workspace_sync.STOCK_MOVEMENT_REPORT)
		self.assertEqual(result[2]["link_type"], "Report")
		self.assertEqual(result[0]["link_count"], 2)

	@patch(
		"retailedge.patches.sync_retailedge_workspace.frappe.db.exists",
		return_value=True,
	)
	def test_report_menu_registration_is_idempotent(self, _exists):
		links = [{"type": "Card Break", "label": "Reports & Insights", "link_count": 0}]
		for _ in range(2):
			links = workspace_sync._ensure_report_menu_link(
				links,
				report_name=workspace_sync.STOCK_MOVEMENT_REPORT,
				label="Stock Movement History",
				section_label=workspace_sync.REPORTS_SECTION_LABEL,
			)

		matches = [
			row
			for row in links
			if row.get("type") == "Link"
			and row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT
		]
		self.assertEqual(len(matches), 1)
		self.assertEqual(links[0]["link_count"], 1)

	@patch.object(menu_patch.frappe.db, "exists", return_value=True)
	@patch.object(menu_patch.frappe, "clear_cache")
	@patch.object(menu_patch.sync_retailedge_workspace, "execute")
	@patch.object(menu_patch.frappe, "reload_doc")
	def test_versioned_patch_reloads_report_and_rebuilds_menu(
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
