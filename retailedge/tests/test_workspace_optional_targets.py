from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from retailedge.workspace_home import (
	ERPNEXT_POS_PAGE,
	POSNEXT_CLOSING_SHIFT,
	POSNEXT_OPENING_SHIFT,
	POSNEXT_POS_URL,
	START_POS_LABEL,
)
from retailedge.workspace_sync import (
	_ensure_sidebar_posnext_shift_links,
	_ensure_sidebar_start_pos_link,
	_filter_workspace_content,
	_normalise_sidebar_items,
)


def _exists(doctype: str, name: str) -> bool:
	available = {
		("DocType", "Sales Invoice"),
		("Page", "retailedge-business-hub"),
		("Page", ERPNEXT_POS_PAGE),
		("Report", "RetailEdge Stock Movement History"),
		("Workspace", "RetailEdge"),
	}
	return (doctype, name) in available


def test_sidebar_filters_optional_posnext_targets_but_keeps_native_links():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{
			"type": "Link",
			"label": POSNEXT_OPENING_SHIFT,
			"link_type": "DocType",
			"link_to": POSNEXT_OPENING_SHIFT,
		},
		{
			"type": "Link",
			"label": POSNEXT_CLOSING_SHIFT,
			"link_type": "DocType",
			"link_to": POSNEXT_CLOSING_SHIFT,
		},
		{
			"type": "Link",
			"label": "Sales Invoice",
			"link_type": "DocType",
			"link_to": "Sales Invoice",
		},
	]

	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", side_effect=_exists):
		normalised = _normalise_sidebar_items(items)

	assert [row.get("label") for row in normalised] == ["Sales & POS", "Sales Invoice"]


def test_sidebar_retains_posnext_targets_when_posnext_is_installed():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{
			"type": "Link",
			"label": POSNEXT_OPENING_SHIFT,
			"link_type": "DocType",
			"link_to": POSNEXT_OPENING_SHIFT,
		},
	]

	with patch(
		"retailedge.patches.sync_retailedge_workspace.frappe.db.exists",
		return_value=True,
	):
		normalised = _normalise_sidebar_items(items)

	assert [row.get("label") for row in normalised] == ["Sales & POS", POSNEXT_OPENING_SHIFT]


def test_sidebar_drops_empty_optional_section():
	items = [
		{"type": "Section Break", "label": "POSNext Only"},
		{
			"type": "Link",
			"label": POSNEXT_CLOSING_SHIFT,
			"link_type": "DocType",
			"link_to": POSNEXT_CLOSING_SHIFT,
		},
	]

	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", return_value=False):
		assert _normalise_sidebar_items(items) == []


def test_sidebar_start_pos_uses_native_erpnext_page_without_posnext():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{
			"type": "Link",
			"label": "Sales Invoice",
			"link_type": "DocType",
			"link_to": "Sales Invoice",
		},
	]

	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", side_effect=_exists):
		resolved = _ensure_sidebar_start_pos_link(items)

	start_pos = next(row for row in resolved if row.get("label") == START_POS_LABEL)
	assert start_pos["link_type"] == "Page"
	assert start_pos["link_to"] == ERPNEXT_POS_PAGE
	assert "url" not in start_pos


def test_sidebar_start_pos_uses_posnext_url_when_posnext_is_available():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{
			"type": "Link",
			"label": "Sales Invoice",
			"link_type": "DocType",
			"link_to": "Sales Invoice",
		},
	]

	with patch(
		"retailedge.patches.sync_retailedge_workspace.frappe.db.exists",
		return_value=True,
	):
		resolved = _ensure_sidebar_start_pos_link(items)

	start_pos = next(row for row in resolved if row.get("label") == START_POS_LABEL)
	assert start_pos["link_type"] == "URL"
	assert start_pos["url"] == POSNEXT_POS_URL
	assert "link_to" not in start_pos


def test_sidebar_does_not_provision_posnext_shift_links_when_posnext_is_unavailable():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{"type": "Link", "label": START_POS_LABEL, "link_type": "Page", "link_to": ERPNEXT_POS_PAGE},
		{"type": "Link", "label": "Sales Invoice", "link_type": "DocType", "link_to": "Sales Invoice"},
	]

	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", side_effect=_exists):
		resolved = _ensure_sidebar_posnext_shift_links(items)

	labels = [row.get("label") for row in resolved]
	assert POSNEXT_OPENING_SHIFT not in labels
	assert POSNEXT_CLOSING_SHIFT not in labels


def test_sidebar_provisions_posnext_shift_links_only_when_posnext_is_available():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{"type": "Link", "label": START_POS_LABEL, "link_type": "URL", "url": POSNEXT_POS_URL},
		{"type": "Link", "label": "Sales Invoice", "link_type": "DocType", "link_to": "Sales Invoice"},
	]

	with patch(
		"retailedge.patches.sync_retailedge_workspace.frappe.db.exists",
		return_value=True,
	):
		resolved = _ensure_sidebar_posnext_shift_links(items)

	labels = [row.get("label") for row in resolved]
	assert labels[:5] == [
		"Sales & POS",
		START_POS_LABEL,
		POSNEXT_OPENING_SHIFT,
		POSNEXT_CLOSING_SHIFT,
		"Sales Invoice",
	]
	assert labels.count(POSNEXT_OPENING_SHIFT) == 1
	assert labels.count(POSNEXT_CLOSING_SHIFT) == 1


def test_workspace_content_removes_shortcuts_filtered_from_workspace():
	content = (
		'[{"type":"shortcut","data":{"shortcut_name":"POS Opening Shift"}},'
		'{"type":"shortcut","data":{"shortcut_name":"Sales Invoice"}},'
		'{"type":"header","data":{"text":"Sales"}}]'
	)
	shortcuts = [{"label": "Sales Invoice"}]

	filtered = _filter_workspace_content(content, shortcuts)

	assert "POS Opening Shift" not in filtered
	assert "Sales Invoice" in filtered
	assert '"type":"header"' in filtered


def test_static_workspace_uses_native_pos_and_has_no_posnext_dependencies():
	app_path = Path(__file__).resolve().parents[1]
	workspace_path = app_path / "retailedge" / "workspace" / "retailedge" / "retailedge.json"
	sidebar_path = app_path / "retailedge" / "workspace_sidebar" / "retailedge" / "retailedge.json"

	workspace = json.loads(workspace_path.read_text())
	workspace_link_labels = {row.get("label") for row in workspace.get("links", [])}
	shortcut_labels = {row.get("label") for row in workspace.get("shortcuts", [])}

	assert POSNEXT_OPENING_SHIFT not in workspace_link_labels
	assert POSNEXT_CLOSING_SHIFT not in workspace_link_labels
	assert POSNEXT_OPENING_SHIFT not in shortcut_labels
	assert POSNEXT_CLOSING_SHIFT not in shortcut_labels

	start_pos = next(row for row in workspace["shortcuts"] if row.get("label") == START_POS_LABEL)
	assert start_pos["type"] == "Page"
	assert start_pos["link_to"] == ERPNEXT_POS_PAGE
	assert "url" not in start_pos

	sales_pos = next(
		row
		for row in workspace["links"]
		if row.get("type") == "Card Break" and row.get("label") == "Sales & POS"
	)
	assert sales_pos["link_count"] == 2

	sidebar = json.loads(sidebar_path.read_text())
	sidebar_labels = {row.get("label") for row in sidebar.get("items", [])}
	assert POSNEXT_OPENING_SHIFT not in sidebar_labels
	assert POSNEXT_CLOSING_SHIFT not in sidebar_labels
	assert START_POS_LABEL not in sidebar_labels
