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
		{"type": "Section Break", "label": "Point of Sale"},
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
		"Point of Sale",
		START_POS_LABEL,
		"POS Opening Shift",
		"POS Closing Shift",
		"Sales Invoice",
	]
	opening = next(row for row in items if row.get("label") == "POS Opening Shift")
	closing = next(row for row in items if row.get("label") == "POS Closing Shift")
	assert opening["link_to"] == ERPNEXT_POS_OPENING_ENTRY
	assert closing["link_to"] == ERPNEXT_POS_CLOSING_ENTRY


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
	assert "POS Opening Shift" in labels
	assert "POS Closing Shift" in labels
	opening = next(row for row in items if row.get("label") == "POS Opening Shift")
	closing = next(row for row in items if row.get("label") == "POS Closing Shift")
	assert opening["link_to"] == POSNEXT_OPENING_SHIFT
	assert closing["link_to"] == POSNEXT_CLOSING_SHIFT
