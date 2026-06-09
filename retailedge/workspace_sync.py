from __future__ import annotations

import json
from pathlib import Path

import frappe

from retailedge.workspace_home import (
	build_home_workspace_content,
	build_home_workspace_links,
	build_home_workspace_shortcuts,
)


def sync_retailedge_workspace_layout():
	base_path = Path(frappe.get_app_path("retailedge", "retailedge"))
	workspace_path = base_path / "workspace" / "retailedge" / "retailedge.json"
	sidebar_path = base_path / "workspace_sidebar" / "retailedge" / "retailedge.json"
	if not workspace_path.exists() or not sidebar_path.exists():
		fallback_base = Path(frappe.get_app_path("retailedge"))
		workspace_path = fallback_base / "retailedge" / "workspace" / "retailedge" / "retailedge.json"
		sidebar_path = fallback_base / "retailedge" / "workspace_sidebar" / "retailedge" / "retailedge.json"

	workspace_data = json.loads(workspace_path.read_text())
	sidebar_data = json.loads(sidebar_path.read_text())

	workspace = frappe.get_doc("Workspace", "RetailEdge")
	workspace.label = workspace_data.get("label") or workspace.label
	workspace.title = workspace_data.get("title") or workspace.title
	workspace.icon = workspace_data.get("icon") or workspace.icon
	workspace.indicator_color = workspace_data.get("indicator_color") or workspace.indicator_color
	workspace.type = workspace_data.get("type") or workspace.type or "Workspace"
	workspace.content = build_home_workspace_content(workspace_data)
	workspace.links = []
	for row in build_home_workspace_links(workspace_data):
		workspace.append("links", row)
	workspace.shortcuts = []
	for row in build_home_workspace_shortcuts(workspace_data):
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
