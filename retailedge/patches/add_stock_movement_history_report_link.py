from __future__ import annotations

import frappe

from retailedge.patches.sync_retailedge_workspace import (
	REPORTS_SECTION_LABEL,
	STOCK_MOVEMENT_REPORT,
	_ensure_report_menu_link,
	_sync_workspace_sidebar,
)


WORKSPACE_NAME = "RetailEdge"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME) or not frappe.db.exists(
		"Report", STOCK_MOVEMENT_REPORT
	):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	links = [row.as_dict(no_nulls=True) for row in workspace.links or []]
	links = _ensure_report_menu_link(
		links,
		report_name=STOCK_MOVEMENT_REPORT,
		label="Stock Movement History",
		section_label=REPORTS_SECTION_LABEL,
		after_link_to="Stock Ledger",
	)
	workspace.set("links", links)
	workspace.save(ignore_permissions=True)
	_sync_workspace_sidebar(workspace)
	frappe.clear_cache(doctype="Workspace")
