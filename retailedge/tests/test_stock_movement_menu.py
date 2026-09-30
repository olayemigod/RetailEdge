from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge import workspace_sync
from retailedge.patches import ensure_stock_movement_history_menu_v3 as menu_patch


class TestStockMovementMenu(unittest.TestCase):
	def test_workspace_report_compat_helper_does_not_reinsert_detailed_report(self):
		links = [
			{"type": "Card Break", "label": "Reports", "link_type": "Page", "link_count": 1},
			{"type": "Link", "label": "Reports Centre", "link_to": "reports-centre", "link_type": "Page"},
		]

		result = workspace_sync._ensure_workspace_report_link(links)

		self.assertEqual(
			[
				row
				for row in result
				if row.get("type") == "Link"
				and row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT
			],
			[],
		)
		self.assertEqual(result[0]["link_count"], 1)

	def test_sidebar_report_compat_helper_does_not_reinsert_detailed_report(self):
		items = [
			{"type": "Section Break", "label": "Reports"},
			{"type": "Link", "label": "Reports Centre", "link_to": "reports-centre", "link_type": "Page"},
		]

		result = workspace_sync._ensure_sidebar_report_link(items)

		self.assertEqual(
			[
				row
				for row in result
				if row.get("type") == "Link"
				and row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT
			],
			[],
		)

	def test_runtime_report_compat_helpers_are_idempotent_no_ops(self):
		links = [{"type": "Card Break", "label": "Reports", "link_count": 0}]
		items = [{"type": "Section Break", "label": "Reports"}]

		for _ in range(2):
			links = workspace_sync._ensure_workspace_report_link(links)
			items = workspace_sync._ensure_sidebar_report_link(items)

		self.assertFalse(
			any(row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT for row in links)
		)
		self.assertFalse(
			any(row.get("link_to") == workspace_sync.STOCK_MOVEMENT_REPORT for row in items)
		)

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
