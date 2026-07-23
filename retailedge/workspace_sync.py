from __future__ import annotations

import json
from pathlib import Path

import frappe

from retailedge.workspace_home import (
	build_home_workspace_content,
	build_home_workspace_links,
	build_home_workspace_shortcuts,
)


STOCK_MOVEMENT_REPORT = "RetailEdge Stock Movement History"
STOCK_MOVEMENT_LABEL = "Stock Movement History"
REPORTS_SECTION_LABEL = "Reports & Insights"


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
	workspace_links = _ensure_workspace_report_link(build_home_workspace_links(workspace_data))
	workspace.links = []
	for row in workspace_links:
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
	for row in _ensure_sidebar_report_link(list(sidebar_data.get("items", []) or [])):
		sidebar.append("items", row)
	sidebar.save(ignore_permissions=True)

	frappe.db.commit()
	frappe.clear_cache(doctype="Workspace")
	frappe.clear_cache(doctype="Workspace Sidebar")
	return {
		"workspace": workspace.name,
		"workspace_links": len(workspace.links or []),
		"workspace_shortcuts": len(workspace.shortcuts or []),
		"sidebar": sidebar.name,
		"sidebar_items": len(sidebar.items or []),
	}


def _report_exists() -> bool:
	return bool(frappe.db.exists("Report", STOCK_MOVEMENT_REPORT))


def _ensure_workspace_report_link(links: list[dict]) -> list[dict]:
	"""Keep the report in the Reports & Insights workspace card."""
	if not _report_exists() or any(
		row.get("type") == "Link" and row.get("link_to") == STOCK_MOVEMENT_REPORT for row in links
	):
		return _recount_workspace_links(links)

	section_index = _find_section_index(links, REPORTS_SECTION_LABEL)
	if section_index is None:
		links.append(
			{
				"hidden": 0,
				"is_query_report": 0,
				"label": REPORTS_SECTION_LABEL,
				"link_count": 0,
				"link_type": "Report",
				"onboard": 0,
				"type": "Card Break",
				"close": 1,
			}
		)
		insert_at = len(links)
	else:
		insert_at = _find_section_end(links, section_index)
		for index in range(section_index + 1, insert_at):
			if links[index].get("type") == "Link" and links[index].get("link_to") == "Stock Ledger":
				insert_at = index + 1
				break

	links.insert(
		insert_at,
		{
			"hidden": 0,
			"is_query_report": 1,
			"label": STOCK_MOVEMENT_LABEL,
			"link_count": 0,
			"link_to": STOCK_MOVEMENT_REPORT,
			"link_type": "Report",
			"onboard": 0,
			"type": "Link",
		},
	)
	return _recount_workspace_links(links)


def _ensure_sidebar_report_link(items: list[dict]) -> list[dict]:
	"""Keep the report in the generated RetailEdge sidebar."""
	if not _report_exists() or any(
		row.get("type") == "Link" and row.get("link_to") == STOCK_MOVEMENT_REPORT for row in items
	):
		return items

	section_index = _find_section_index(items, REPORTS_SECTION_LABEL)
	if section_index is None:
		items.append(
			{
				"child": 0,
				"collapsible": 1,
				"indent": 1,
				"keep_closed": 1,
				"label": REPORTS_SECTION_LABEL,
				"link_type": "DocType",
				"show_arrow": 0,
				"type": "Section Break",
			}
		)
		insert_at = len(items)
	else:
		insert_at = _find_section_end(items, section_index)
		for index in range(section_index + 1, insert_at):
			if items[index].get("type") == "Link" and items[index].get("link_to") == "Stock Ledger":
				insert_at = index + 1
				break

	items.insert(
		insert_at,
		{
			"child": 1,
			"collapsible": 0,
			"indent": 0,
			"keep_closed": 0,
			"label": STOCK_MOVEMENT_LABEL,
			"link_to": STOCK_MOVEMENT_REPORT,
			"link_type": "Report",
			"show_arrow": 0,
			"type": "Link",
		},
	)
	return items


def _find_section_index(rows: list[dict], label: str) -> int | None:
	return next(
		(
			index
			for index, row in enumerate(rows)
			if row.get("type") in {"Card Break", "Section Break"} and row.get("label") == label
		),
		None,
	)


def _find_section_end(rows: list[dict], section_index: int) -> int:
	for index in range(section_index + 1, len(rows)):
		if rows[index].get("type") in {"Card Break", "Section Break"}:
			return index
	return len(rows)


def _recount_workspace_links(links: list[dict]) -> list[dict]:
	current_card = None
	for row in links:
		if row.get("type") == "Card Break":
			row["link_count"] = 0
			current_card = row
		elif row.get("type") == "Link" and current_card is not None:
			current_card["link_count"] = int(current_card.get("link_count") or 0) + 1
	return links
