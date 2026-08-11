from __future__ import annotations

from unittest.mock import patch

from retailedge.edgesuite_ui import (
	ERPNEXT_POS_PAGE as EDGEUI_ERPNEXT_POS_PAGE,
	NAVIGATION_GROUPS,
	POSNEXT_POS_URL as EDGEUI_POSNEXT_POS_URL,
	_resolve_navigation_item,
)
from retailedge.workspace_home import (
	ERPNEXT_POS_PAGE,
	HOME_WORKSPACE_ITEMS,
	POSNEXT_CLOSING_SHIFT,
	POSNEXT_OPENING_SHIFT,
	POSNEXT_POS_URL,
	START_POS_LABEL,
	get_home_workspace_items,
)


def _workspace_exists_without_posnext(link_type: str, link_to: str) -> bool:
	return (link_type, link_to) == ("Page", ERPNEXT_POS_PAGE)


def _workspace_exists_with_posnext(link_type: str, link_to: str) -> bool:
	return (link_type, link_to) in {
		("DocType", POSNEXT_OPENING_SHIFT),
		("DocType", POSNEXT_CLOSING_SHIFT),
		("Page", ERPNEXT_POS_PAGE),
	}


def _start_pos_workspace_item():
	return next(item for item in HOME_WORKSPACE_ITEMS if item.label == START_POS_LABEL)


def _start_pos_navigation_item():
	sales = next(group for group in NAVIGATION_GROUPS if group["key"] == "sales")
	return next(item for item in sales["items"] if item["label"] == START_POS_LABEL)


def test_workspace_uses_native_erpnext_pos_when_posnext_is_unavailable():
	with patch("retailedge.workspace_home._target_exists", side_effect=_workspace_exists_without_posnext):
		items = get_home_workspace_items({}, check_dependencies=True)

	start_pos = next(item for item in items if item.label == START_POS_LABEL)
	assert start_pos.link_type == "Page"
	assert start_pos.link_to == ERPNEXT_POS_PAGE
	assert start_pos.url is None
	assert start_pos.source == "ERPNext Link"
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


def test_business_hub_uses_native_erpnext_pos_when_posnext_is_unavailable():
	with (
		patch("retailedge.edgesuite_ui._posnext_available", return_value=False),
		patch(
			"retailedge.edgesuite_ui._target_exists",
			side_effect=lambda target_type, target: (target_type, target)
			== ("Page", EDGEUI_ERPNEXT_POS_PAGE),
		),
	):
		resolved = _resolve_navigation_item(_start_pos_navigation_item())

	assert resolved is not None
	assert resolved["target_type"] == "Page"
	assert resolved["target"] == EDGEUI_ERPNEXT_POS_PAGE
	assert "runtime_target" not in resolved


def test_business_hub_uses_posnext_url_when_posnext_is_available():
	with patch("retailedge.edgesuite_ui._posnext_available", return_value=True):
		resolved = _resolve_navigation_item(_start_pos_navigation_item())

	assert resolved is not None
	assert resolved["target_type"] == "URL"
	assert resolved["target"] == EDGEUI_POSNEXT_POS_URL
	assert "runtime_target" not in resolved


def test_start_pos_workspace_definition_remains_single_runtime_action():
	matches = [item for item in HOME_WORKSPACE_ITEMS if item.label == START_POS_LABEL]
	assert matches == [_start_pos_workspace_item()]
