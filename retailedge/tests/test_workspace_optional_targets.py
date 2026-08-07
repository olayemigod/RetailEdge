from __future__ import annotations

from unittest.mock import patch

from retailedge.workspace_sync import _filter_workspace_content, _normalise_sidebar_items


def _exists(doctype: str, name: str) -> bool:
	available = {
		("DocType", "Sales Invoice"),
		("Page", "retailedge-business-hub"),
		("Report", "RetailEdge Stock Movement History"),
		("Workspace", "RetailEdge"),
	}
	return (doctype, name) in available


def test_sidebar_filters_optional_posnext_targets_but_keeps_native_links():
	items = [
		{"type": "Section Break", "label": "Sales & POS"},
		{
			"type": "Link",
			"label": "POS Opening Shift",
			"link_type": "DocType",
			"link_to": "POS Opening Shift",
		},
		{
			"type": "Link",
			"label": "POS Closing Shift",
			"link_type": "DocType",
			"link_to": "POS Closing Shift",
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
			"label": "POS Opening Shift",
			"link_type": "DocType",
			"link_to": "POS Opening Shift",
		},
	]

	with patch(
		"retailedge.patches.sync_retailedge_workspace.frappe.db.exists",
		return_value=True,
	):
		normalised = _normalise_sidebar_items(items)

	assert [row.get("label") for row in normalised] == ["Sales & POS", "POS Opening Shift"]


def test_sidebar_drops_empty_optional_section():
	items = [
		{"type": "Section Break", "label": "POSNext Only"},
		{
			"type": "Link",
			"label": "POS Closing Shift",
			"link_type": "DocType",
			"link_to": "POS Closing Shift",
		},
	]

	with patch("retailedge.patches.sync_retailedge_workspace.frappe.db.exists", return_value=False):
		assert _normalise_sidebar_items(items) == []


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
