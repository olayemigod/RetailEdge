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
	shortcuts = _normalise_shortcuts(data.get("shortcuts", []))
	links = _normalise_links(data.get("links", []))
	workspace.content = _normalise_content(data.get("content"), shortcuts)
	workspace.public = data.get("public", 1)
	workspace.is_hidden = data.get("is_hidden", 0)
	workspace.label = data.get("label") or WORKSPACE_NAME
	workspace.title = data.get("title") or WORKSPACE_NAME
	workspace.type = data.get("type") or "Workspace"
	workspace.module = data.get("module") or "RetailEdge"
	workspace.icon = data.get("icon") or workspace.icon
	workspace.indicator_color = data.get("indicator_color") or workspace.indicator_color
	workspace.sequence_id = data.get("sequence_id") or 0.0
	workspace.set("shortcuts", shortcuts)
	workspace.set("links", links)
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
	seen = set()
	for shortcut in shortcuts or []:
		row = dict(shortcut)
		label = row.get("label")
		link_to = row.get("link_to")
		link_type = row.get("type")
		identity = (label, link_to, link_type)
		if identity in seen or not _target_exists(link_type, link_to):
			continue
		seen.add(identity)
		doc_view = row.get("doc_view") or ""
		row["doc_view"] = doc_view if doc_view in VALID_SHORTCUT_VIEWS else ""
		normalised.append(row)
	return normalised


def _normalise_links(links: list[dict]) -> list[dict]:
	normalised = []
	current_card_index = None
	seen = set()

	for link in links or []:
		row = dict(link)
		row_type = row.get("type")
		if row_type == "Card Break":
			row["link_count"] = 0
			current_card_index = len(normalised)
			normalised.append(row)
			continue

		identity = (row.get("label"), row.get("link_to"), row.get("link_type"))
		if identity in seen or not _target_exists(row.get("link_type"), row.get("link_to")):
			continue
		seen.add(identity)

		if row_type == "Link" and current_card_index is not None:
			normalised[current_card_index]["link_count"] = (
				normalised[current_card_index].get("link_count", 0) + 1
			)

		normalised.append(row)

	return normalised


def _normalise_content(content: str | None, shortcuts: list[dict]) -> str | None:
	if not content:
		return content
	try:
		blocks = json.loads(content)
	except Exception:
		return content

	valid_shortcut_names = {row.get("label") for row in shortcuts or []}
	filtered_blocks = []
	for block in blocks or []:
		if block.get("type") != "shortcut":
			filtered_blocks.append(block)
			continue
		shortcut_name = ((block.get("data") or {}).get("shortcut_name"))
		if shortcut_name in valid_shortcut_names:
			filtered_blocks.append(block)

	return json.dumps(filtered_blocks, separators=(",", ":"))


def _target_exists(link_type: str | None, link_to: str | None) -> bool:
	if not link_type or not link_to:
		return False
	if link_type in {"DocType", "Link", "Single"}:
		return bool(frappe.db.exists("DocType", link_to))
	if link_type == "Report":
		return bool(frappe.db.exists("Report", link_to))
	if link_type == "Workspace":
		return True
	return True


def _sync_workspace_sidebar(workspace):
	sidebar = _get_or_create_workspace_sidebar(workspace)
	items = []

	items.append(
		_new_sidebar_item(
			label="Home",
			link_to=workspace.name,
			link_type="Workspace",
			item_type="Link",
			idx=0,
		)
	)

	idx = 1
	for link in workspace.links or []:
		if link.type == "Card Break":
			items.append(
				_new_sidebar_item(
					label=link.label,
					item_type="Section Break",
					idx=idx,
					collapsible=1,
					keep_closed=0,
					indent=1,
				)
			)
			idx += 1
			continue

		if link.type != "Link":
			continue

		items.append(
			_new_sidebar_item(
				label=link.label,
				link_to=link.link_to,
				link_type=link.link_type,
				item_type="Link",
				idx=idx,
				child=1,
			)
		)
		idx += 1

	sidebar.items = items
	sidebar.save(ignore_permissions=True)


def _new_sidebar_item(
	label,
	item_type,
	idx,
	link_to=None,
	link_type=None,
	child=0,
	collapsible=1,
	keep_closed=0,
	indent=0,
):
	item = frappe.new_doc("Workspace Sidebar Item")
	item.update(
		{
			"label": label,
			"link_to": link_to,
			"link_type": link_type,
			"type": item_type,
			"idx": idx,
			"child": child,
			"collapsible": collapsible,
			"keep_closed": keep_closed,
			"indent": indent,
		}
	)
	return item


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
