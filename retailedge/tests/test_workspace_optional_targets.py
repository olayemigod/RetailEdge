from __future__ import annotations

from unittest.mock import patch

from retailedge.pos_runtime import (
	ERPNEXT_POS_CLOSING_ENTRY,
	ERPNEXT_POS_OPENING_ENTRY,
	ERPNEXT_POS_PAGE,
	POSNEXT_CLOSING_SHIFT,
	POSNEXT_OPENING_SHIFT,
	POSNEXT_POS_URL,
	START_POS_LABEL,
)
from retailedge.workspace_sync import _ensure_sidebar_pos_shift_links, _ensure_sidebar_start_pos_link


def _erpnext_exists(doctype: str, name: str) -> bool:
	return (doctype, name) in {
		("DocType", ERPNEXT_POS_OPENING_ENTRY),
		("DocType", ERPNEXT_POS_CLOSING_ENTRY),
		("Page", ERPNEXT_POS_PAGE),
	}


def _posnext_exists(doctype: str, name: str) -> bool:
	return _erpnext_exists(doctype, name) or (doctype, name) in {
		("DocType", POSNEXT_OPENING_SHIFT),
		("DocType", POSNEXT_CLOSING_SHIFT),
	}


def _base_sidebar(start_row: dict) -> list[dict]:
	return [
		{"type": "Section Break", "label": "Sales & POS"},
		start_row,
		{"type": "Link", "label": "Sales Invoice", "link_type": "DocType", "link_to": "Sales Invoice"},
	]


def test_sidebar_uses_native_erpnext_pos_without_posnext():
	items = _base_sidebar(
		{"type": "Link", "label": START_POS_LABEL, "link_type": "Page", "link_to": ERPNEXT_POS_PAGE}
	)
	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", side_effect=_erpnext_exists):
		items = _ensure_sidebar_start_pos_link(items)
		items = _ensure_sidebar_pos_shift_links(items)

	labels = [row.get("label") for row in items]
	assert labels[:5] == [
		"Sales & POS",
		START_POS_LABEL,
		ERPNEXT_POS_OPENING_ENTRY,
		ERPNEXT_POS_CLOSING_ENTRY,
		"Sales Invoice",
	]
	assert POSNEXT_OPENING_SHIFT not in labels
	assert POSNEXT_CLOSING_SHIFT not in labels


def test_sidebar_uses_posnext_when_shift_doctypes_are_installed():
	items = _base_sidebar(
		{"type": "Link", "label": START_POS_LABEL, "link_type": "Page", "link_to": ERPNEXT_POS_PAGE}
	)
	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", side_effect=_posnext_exists):
		items = _ensure_sidebar_start_pos_link(items)
		items = _ensure_sidebar_pos_shift_links(items)

	start = next(row for row in items if row.get("label") == START_POS_LABEL)
	labels = [row.get("label") for row in items]
	assert start["link_type"] == "URL"
	assert start["url"] == POSNEXT_POS_URL
	assert POSNEXT_OPENING_SHIFT in labels
	assert POSNEXT_CLOSING_SHIFT in labels
	assert ERPNEXT_POS_OPENING_ENTRY not in labels
	assert ERPNEXT_POS_CLOSING_ENTRY not in labels
