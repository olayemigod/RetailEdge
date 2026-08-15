from __future__ import annotations

from unittest.mock import patch

from retailedge.edgesuite_ui import NAVIGATION_GROUPS, _resolve_navigation_item
from retailedge.pos_runtime import (
	ERPNEXT_POS_CLOSING_ENTRY,
	ERPNEXT_POS_OPENING_ENTRY,
	ERPNEXT_POS_PAGE,
	POSNEXT_CLOSING_SHIFT,
	POSNEXT_OPENING_SHIFT,
	POSNEXT_POS_URL,
	START_POS_LABEL,
)
from retailedge.workspace_home import HOME_WORKSPACE_ITEMS, get_home_workspace_items


def _workspace_exists_without_posnext(link_type: str, link_to: str) -> bool:
	return (link_type, link_to) in {
		("DocType", ERPNEXT_POS_OPENING_ENTRY),
		("DocType", ERPNEXT_POS_CLOSING_ENTRY),
		("Page", ERPNEXT_POS_PAGE),
	}


def _workspace_exists_with_posnext(link_type: str, link_to: str) -> bool:
	return (link_type, link_to) in {
		("DocType", POSNEXT_OPENING_SHIFT),
		("DocType", POSNEXT_CLOSING_SHIFT),
		("Page", ERPNEXT_POS_PAGE),
	}


def _start_pos_workspace_item():
	return next(item for item in HOME_WORKSPACE_ITEMS if item.label == START_POS_LABEL)


def _navigation_item(runtime_target: str):
	for group in NAVIGATION_GROUPS:
		for item in group["items"]:
			if item.get("runtime_target") == runtime_target:
				return item
	raise AssertionError(f"runtime navigation item not found: {runtime_target}")


def test_workspace_uses_native_erpnext_pos_when_posnext_is_unavailable():
	with patch("retailedge.workspace_home._target_exists", side_effect=_workspace_exists_without_posnext):
		items = get_home_workspace_items({}, check_dependencies=True)

	start_pos = next(item for item in items if item.label == START_POS_LABEL)
	assert start_pos.link_type == "Page"
	assert start_pos.link_to == ERPNEXT_POS_PAGE
	assert start_pos.url is None
	assert start_pos.source == "ERPNext Link"
	assert ERPNEXT_POS_OPENING_ENTRY in {item.link_to for item in items}
	assert ERPNEXT_POS_CLOSING_ENTRY in {item.link_to for item in items}
	assert POSNEXT_OPENING_SHIFT not in {item.link_to for item in items}
	assert POSNEXT_CLOSING_SHIFT not in {item.link_to for item in items}


def test_workspace_uses_posnext_and_retains_shift_links_when_available():
	with patch("retailedge.workspace_home._target_exists", side_effect=_workspace_exists_with_posnext):
		items = get_home_workspace_items({}, check_dependencies=True)

	start_pos = next(item for item in items if item.label == START_POS_LABEL)
	assert start_pos.link_type == "URL"
	assert start_pos.link_to == POSNEXT_POS_URL
	assert start_pos.url == POSNEXT_POS_URL
	assert start_pos.source == "POSNext Link"
	assert POSNEXT_OPENING_SHIFT in {item.link_to for item in items}
	assert POSNEXT_CLOSING_SHIFT in {item.link_to for item in items}
	assert ERPNEXT_POS_OPENING_ENTRY not in {item.link_to for item in items}
	assert ERPNEXT_POS_CLOSING_ENTRY not in {item.link_to for item in items}


def test_business_hub_uses_native_erpnext_pos_and_entries_without_posnext():
	with patch("retailedge.edgesuite_ui._target_exists", side_effect=_workspace_exists_without_posnext):
		start = _resolve_navigation_item(_navigation_item("pos"))
		opening = _resolve_navigation_item(_navigation_item("pos_opening"))
		closing = _resolve_navigation_item(_navigation_item("pos_closing"))

	assert start is not None
	assert start["target_type"] == "Page"
	assert start["target"] == ERPNEXT_POS_PAGE
	assert opening is not None
	assert opening["target_type"] == "DocType"
	assert opening["target"] == ERPNEXT_POS_OPENING_ENTRY
	assert opening["label"] == ERPNEXT_POS_OPENING_ENTRY
	assert closing is not None
	assert closing["target_type"] == "DocType"
	assert closing["target"] == ERPNEXT_POS_CLOSING_ENTRY
	assert closing["label"] == ERPNEXT_POS_CLOSING_ENTRY


def test_business_hub_uses_posnext_url_and_shift_documents_when_available():
	with patch("retailedge.edgesuite_ui._target_exists", side_effect=_workspace_exists_with_posnext):
		start = _resolve_navigation_item(_navigation_item("pos"))
		opening = _resolve_navigation_item(_navigation_item("pos_opening"))
		closing = _resolve_navigation_item(_navigation_item("pos_closing"))

	assert start is not None
	assert start["target_type"] == "URL"
	assert start["target"] == POSNEXT_POS_URL
	assert opening is not None
	assert opening["target"] == POSNEXT_OPENING_SHIFT
	assert opening["label"] == POSNEXT_OPENING_SHIFT
	assert closing is not None
	assert closing["target"] == POSNEXT_CLOSING_SHIFT
	assert closing["label"] == POSNEXT_CLOSING_SHIFT


def test_start_pos_workspace_definition_remains_single_runtime_action():
	matches = [item for item in HOME_WORKSPACE_ITEMS if item.label == START_POS_LABEL]
	assert matches == [_start_pos_workspace_item()]
