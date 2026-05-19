from __future__ import annotations

import json
from pathlib import Path

import frappe


def sync_retailedge_workspace_layout():
	base_path = Path(frappe.get_app_path("retailedge", "retailedge"))
	workspace_path = base_path / "workspace" / "retailedge" / "retailedge.json"
	sidebar_path = base_path / "workspace_sidebar" / "retailedge" / "retailedge.json"

	workspace_data = json.loads(workspace_path.read_text())
	sidebar_data = json.loads(sidebar_path.read_text())

	workspace = frappe.get_doc("Workspace", "RetailEdge")
	workspace.content = workspace_data.get("content")
	workspace.links = []
	for row in workspace_data.get("links", []) or []:
		workspace.append("links", row)
	workspace.shortcuts = []
	for row in workspace_data.get("shortcuts", []) or []:
		short_row = dict(row)
		if short_row.get("type") == "Report":
			short_row["doc_view"] = ""
		workspace.append("shortcuts", short_row)
	workspace.save(ignore_permissions=True)

	sidebar = frappe.get_doc("Workspace Sidebar", "RetailEdge")
	sidebar.header_icon = sidebar_data.get("header_icon")
	sidebar.items = []
	for row in sidebar_data.get("items", []) or []:
		sidebar.append("items", row)
	sidebar.save(ignore_permissions=True)

	frappe.db.commit()
	return {
		"workspace": workspace.name,
		"workspace_links": len(workspace.links or []),
		"workspace_shortcuts": len(workspace.shortcuts or []),
		"sidebar": sidebar.name,
		"sidebar_items": len(sidebar.items or []),
	}
