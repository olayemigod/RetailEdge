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
