from __future__ import annotations

import frappe

from retailedge.patches import sync_retailedge_workspace


def execute():
	"""Refresh the report link with a new patch identity.

	The first menu patch may already be recorded in Patch Log on sites that
	installed an earlier revision. Reload the standard report, rebuild the
	RetailEdge workspace links, and regenerate the Workspace Sidebar.
	"""
	frappe.reload_doc("retailedge", "report", "retailedge_stock_movement_history")
	sync_retailedge_workspace.execute()
	frappe.clear_cache(doctype="Workspace")
	if frappe.db.exists("DocType", "Workspace Sidebar"):
		frappe.clear_cache(doctype="Workspace Sidebar")
