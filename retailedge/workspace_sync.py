from __future__ import annotations

import json
from pathlib import Path

import frappe

from retailedge.patches.sync_retailedge_workspace import (
	_normalise_links,
	_normalise_shortcuts,
	_target_exists,
)
from retailedge.pos_runtime import (
	ERPNEXT_POS_CLOSING_ENTRY,
	ERPNEXT_POS_OPENING_ENTRY,
	POSNEXT_CLOSING_SHIFT,
	POSNEXT_OPENING_SHIFT,
	START_POS_LABEL,
	get_pos_runtime_capabilities,
)
from retailedge.workspace_home import (
	build_home_workspace_content,
	build_home_workspace_links,
	build_home_workspace_shortcuts,
)

BUSINESS_HUB_PAGE = "retailedge-business-hub"
BUSINESS_HUB_LABEL = "RetailEdge Business Hub"
DASHBOARD_SECTION_LABEL = "Dashboard"
SALES_POS_SECTION_LABEL = "Sales & POS"
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

	workspace_shortcuts = _normalise_shortcuts(build_home_workspace_shortcuts(workspace_data))
	workspace.content = _filter_workspace_content(
		build_home_workspace_content(workspace_data),
		workspace_shortcuts,
	)
	workspace_links = _normalise_links(build_home_workspace_links(workspace_data))
	workspace_links = _ensure_workspace_business_hub_link(_ensure_workspace_report_link(workspace_links))
	workspace.links = []
	for row in workspace_links:
		workspace.append("links", row)
	workspace.shortcuts = []
	for row in _ensure_business_hub_shortcut(workspace_shortcuts):
		short_row = dict(row)
		if short_row.get("type") == "Report":
			short_row["doc_view"] = ""
		workspace.append("shortcuts", short_row)
	workspace.save(ignore_permissions=True)

	sidebar = frappe.get_doc("Workspace Sidebar", "RetailEdge")
	sidebar.header_icon = sidebar_data.get("header_icon")
	sidebar.items = []
	sidebar_items = _normalise_sidebar_items(list(sidebar_data.get("items", []) or []))
	sidebar_items = _ensure_sidebar_start_pos_link(sidebar_items)
	sidebar_items = _ensure_sidebar_pos_shift_links(sidebar_items)
	sidebar_items = _ensure_sidebar_business_hub_link(_ensure_sidebar_report_link(sidebar_items))
	for row in sidebar_items:
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


def _filter_workspace_content(content: str | None, shortcuts: list[dict]) -> str | None:
	if not content:
		return content
	try:
		blocks = json.loads(content)
	except (TypeError, ValueError):
		return content

	valid_shortcut_names = {row.get("label") for row in shortcuts or []}
	filtered = []
	for block in blocks or []:
		if block.get("type") != "shortcut":
			filtered.append(block)
			continue
		shortcut_name = (block.get("data") or {}).get("shortcut_name")
		if shortcut_name in valid_shortcut_names:
			filtered.append(block)
	return json.dumps(filtered, separators=(",", ":"))


def _normalise_sidebar_items(items: list[dict]) -> list[dict]:
	"""Drop links to targets that are unavailable on this site.

	Sections are retained only when they still contain at least one valid child.
	Provider-specific POS opening/closing links are provisioned after this pass,
	so RetailEdge remains valid with ERPNext alone or with POSNext installed.
	"""
	normalised: list[dict] = []
	pending_section: dict | None = None
	seen: set[tuple] = set()

	for item in items or []:
		row = dict(item)
		if row.get("type") == "Section Break":
			pending_section = row
			continue

		if row.get("type") == "Link":
			link_type = row.get("link_type")
			target = row.get("url") if link_type == "URL" else row.get("link_to")
			identity = (row.get("label"), target, link_type)
			if identity in seen or not _sidebar_target_exists(row):
				continue
			seen.add(identity)

		if pending_section is not None:
			normalised.append(pending_section)
			pending_section = None
		normalised.append(row)

	return normalised


def _sidebar_target_exists(row: dict) -> bool:
	if row.get("link_type") == "URL":
		return bool(row.get("url"))
	return _target_exists(row.get("link_type"), row.get("link_to"))


def _start_pos_sidebar_row() -> dict | None:
	capabilities = get_pos_runtime_capabilities(_target_exists)
	if not capabilities.start_link_type or not capabilities.start_target:
		return None
	row = {
		"child": 1,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"label": START_POS_LABEL,
		"link_type": capabilities.start_link_type,
		"show_arrow": 0,
		"type": "Link",
	}
	if capabilities.start_link_type == "URL":
		row["url"] = capabilities.start_url or capabilities.start_target
	else:
		row["link_to"] = capabilities.start_target
	return row


def _ensure_sidebar_start_pos_link(items: list[dict]) -> list[dict]:
	items = [row for row in items if not (row.get("type") == "Link" and row.get("label") == START_POS_LABEL)]
	row = _start_pos_sidebar_row()
	if row is None:
		return items

	section_index = _find_section_index(items, SALES_POS_SECTION_LABEL)
	if section_index is None:
		return items
	items.insert(section_index + 1, row)
	return items


def _pos_shift_sidebar_row(doctype: str) -> dict:
	return {
		"child": 1,
		"collapsible": 0,
		"indent": 0,
		"keep_closed": 0,
		"label": doctype,
		"link_to": doctype,
		"link_type": "DocType",
		"show_arrow": 0,
		"type": "Link",
	}


def _ensure_sidebar_pos_shift_links(items: list[dict]) -> list[dict]:
	shift_targets = {
		POSNEXT_OPENING_SHIFT,
		POSNEXT_CLOSING_SHIFT,
		ERPNEXT_POS_OPENING_ENTRY,
		ERPNEXT_POS_CLOSING_ENTRY,
	}
	items = [
		row
		for row in items
		if not (
			row.get("type") == "Link"
			and (row.get("label") in shift_targets or row.get("link_to") in shift_targets)
		)
	]
	capabilities = get_pos_runtime_capabilities(_target_exists)
	shift_doctypes = [
		doctype for doctype in (capabilities.opening_doctype, capabilities.closing_doctype) if doctype
	]
	if not shift_doctypes:
		return items

	section_index = _find_section_index(items, SALES_POS_SECTION_LABEL)
	if section_index is None:
		return items

	insert_at = section_index + 1
	if insert_at < len(items) and items[insert_at].get("label") == START_POS_LABEL:
		insert_at += 1
	for offset, doctype in enumerate(shift_doctypes):
		items.insert(insert_at + offset, _pos_shift_sidebar_row(doctype))
	return items


# Compatibility alias for existing callers/tests while the provider-neutral name rolls out.
def _ensure_sidebar_posnext_shift_links(items: list[dict]) -> list[dict]:
	return _ensure_sidebar_pos_shift_links(items)


def _business_hub_exists() -> bool:
	return bool(frappe.db.exists("Page", BUSINESS_HUB_PAGE))


def _report_exists() -> bool:
	return bool(frappe.db.exists("Report", STOCK_MOVEMENT_REPORT))


def _ensure_business_hub_shortcut(shortcuts: list[dict]) -> list[dict]:
	if not _business_hub_exists() or any(
		row.get("type") == "Page" and row.get("link_to") == BUSINESS_HUB_PAGE for row in shortcuts
	):
		return shortcuts
	return [
		{
			"color": "Blue",
			"doc_view": "List",
			"label": BUSINESS_HUB_LABEL,
			"link_to": BUSINESS_HUB_PAGE,
			"stats_filter": "[]",
			"type": "Page",
		},
		*shortcuts,
	]


def _ensure_workspace_business_hub_link(links: list[dict]) -> list[dict]:
	if not _business_hub_exists() or any(
		row.get("type") == "Link" and row.get("link_to") == BUSINESS_HUB_PAGE for row in links
	):
		return _recount_workspace_links(links)

	section_index = _find_section_index(links, DASHBOARD_SECTION_LABEL)
	if section_index is None:
		links.insert(
			0,
			{
				"hidden": 0,
				"is_query_report": 0,
				"label": DASHBOARD_SECTION_LABEL,
				"link_count": 0,
				"link_type": "Page",
				"onboard": 0,
				"type": "Card Break",
				"close": 1,
			},
		)
		section_index = 0

	links.insert(
		section_index + 1,
		{
			"hidden": 0,
			"is_query_report": 0,
			"label": BUSINESS_HUB_LABEL,
			"link_count": 0,
			"link_to": BUSINESS_HUB_PAGE,
			"link_type": "Page",
			"onboard": 0,
			"type": "Link",
		},
	)
	return _recount_workspace_links(links)


def _ensure_sidebar_business_hub_link(items: list[dict]) -> list[dict]:
	if not _business_hub_exists() or any(
		row.get("type") == "Link" and row.get("link_to") == BUSINESS_HUB_PAGE for row in items
	):
		return items

	section_index = _find_section_index(items, DASHBOARD_SECTION_LABEL)
	if section_index is None:
		items.insert(
			0,
			{
				"child": 0,
				"collapsible": 1,
				"indent": 1,
				"keep_closed": 0,
				"label": DASHBOARD_SECTION_LABEL,
				"link_type": "Page",
				"show_arrow": 0,
				"type": "Section Break",
			},
		)
		section_index = 0

	items.insert(
		section_index + 1,
		{
			"child": 1,
			"collapsible": 0,
			"indent": 0,
			"keep_closed": 0,
			"label": BUSINESS_HUB_LABEL,
			"link_to": BUSINESS_HUB_PAGE,
			"link_type": "Page",
			"show_arrow": 0,
			"type": "Link",
		},
	)
	return items


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
