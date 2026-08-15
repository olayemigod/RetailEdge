from __future__ import annotations

import frappe

from retailedge.workspace_sync import sync_retailedge_workspace_layout


def execute():
	"""Reload the report and run the actual RetailEdge after-migrate menu builder."""
	frappe.reload_doc("retailedge", "report", "retailedge_stock_movement_history")
	sync_retailedge_workspace_layout()
	frappe.clear_cache(doctype="Workspace")
	if frappe.db.exists("DocType", "Workspace Sidebar"):
		frappe.clear_cache(doctype="Workspace Sidebar")
