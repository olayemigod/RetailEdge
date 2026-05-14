from __future__ import annotations

import json
from pathlib import Path

import frappe


WORKSPACE_NAME = "RetailEdge"
VALID_SHORTCUT_VIEWS = {"", "List", "Report Builder", "Dashboard", "Tree", "New", "Calendar", "Kanban", "Image"}


def execute():
	workspace_path = (
		Path(frappe.get_app_path("retailedge"))
		/ "retailedge"
		/ "workspace"
		/ "retailedge"
		/ "retailedge.json"
	)
	if not workspace_path.exists():
		return

	data = json.loads(workspace_path.read_text())
	workspace = _get_or_create_workspace(data)
	workspace.content = data.get("content")
	workspace.public = data.get("public", 1)
	workspace.is_hidden = data.get("is_hidden", 0)
	workspace.label = data.get("label") or WORKSPACE_NAME
	workspace.title = data.get("title") or WORKSPACE_NAME
	workspace.type = data.get("type") or "Workspace"
	workspace.module = data.get("module") or "RetailEdge"
	workspace.icon = data.get("icon") or workspace.icon
	workspace.indicator_color = data.get("indicator_color") or workspace.indicator_color
	workspace.sequence_id = data.get("sequence_id") or 0.0
	workspace.set("shortcuts", _normalise_shortcuts(data.get("shortcuts", [])))
	workspace.set("links", _normalise_links(data.get("links", [])))
	workspace.save(ignore_permissions=True)
	_sync_workspace_sidebar(workspace)


def _get_or_create_workspace(data: dict):
	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		return frappe.get_doc("Workspace", WORKSPACE_NAME)

	workspace = frappe.new_doc("Workspace")
	workspace.name = WORKSPACE_NAME
	workspace.title = data.get("title") or WORKSPACE_NAME
	workspace.label = data.get("label") or WORKSPACE_NAME
	workspace.type = data.get("type") or "Workspace"
	workspace.module = data.get("module") or "RetailEdge"
	return workspace


def _normalise_shortcuts(shortcuts: list[dict]) -> list[dict]:
	normalised = []
	for shortcut in shortcuts or []:
		row = dict(shortcut)
		doc_view = row.get("doc_view") or ""
		row["doc_view"] = doc_view if doc_view in VALID_SHORTCUT_VIEWS else ""
		normalised.append(row)
	return normalised


def _normalise_links(links: list[dict]) -> list[dict]:
	normalised = []
	current_card_index = None

	for link in links or []:
		row = dict(link)
		row_type = row.get("type")
		if row_type == "Card Break":
			row["link_count"] = 0
			current_card_index = len(normalised)
			normalised.append(row)
			continue

		if row_type == "Link" and current_card_index is not None:
			normalised[current_card_index]["link_count"] = (
				normalised[current_card_index].get("link_count", 0) + 1
			)

		normalised.append(row)

	return normalised


def _sync_workspace_sidebar(workspace):
	sidebar = _get_or_create_workspace_sidebar(workspace)
	items = []

	home_item = frappe.new_doc("Workspace Sidebar Item")
	home_item.update(
		{
			"label": "Home",
			"link_to": workspace.name,
			"link_type": "Workspace",
			"type": "Link",
			"idx": 0,
		}
	)
	items.append(home_item)

	for idx, shortcut in enumerate(workspace.shortcuts or [], start=1):
		item = frappe.new_doc("Workspace Sidebar Item")
		item.update(
			{
				"label": shortcut.label,
				"link_to": shortcut.link_to,
				"link_type": shortcut.type,
				"type": "Link",
				"idx": idx,
			}
		)
		items.append(item)

	sidebar.items = items
	sidebar.save(ignore_permissions=True)


def _get_or_create_workspace_sidebar(workspace):
	if frappe.db.exists("Workspace Sidebar", WORKSPACE_NAME):
		sidebar = frappe.get_doc("Workspace Sidebar", WORKSPACE_NAME)
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = WORKSPACE_NAME

	sidebar.title = WORKSPACE_NAME
	sidebar.app = "retailedge"
	sidebar.standard = 1
	if hasattr(sidebar, "module") and not sidebar.module:
		sidebar.module = workspace.module or "RetailEdge"
	if hasattr(sidebar, "header_icon"):
		sidebar.header_icon = workspace.icon
	return sidebar
