from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import frappe


START_POS_LABEL = "Start POS"
POSNEXT_POS_URL = "/pos/"
POSNEXT_OPENING_SHIFT = "POS Opening Shift"
POSNEXT_CLOSING_SHIFT = "POS Closing Shift"
ERPNEXT_POS_PAGE = "point-of-sale"
ERPNEXT_POS_OPENING_ENTRY = "POS Opening Entry"
ERPNEXT_POS_CLOSING_ENTRY = "POS Closing Entry"


@dataclass(frozen=True)
class POSRuntimeCapabilities:
	provider: str
	start_link_type: str | None
	start_target: str | None
	start_url: str | None
	opening_doctype: str | None
	closing_doctype: str | None


def _default_target_exists(target_type: str, target: str) -> bool:
	try:
		return bool(frappe.db.exists(target_type, target))
	except Exception:
		return False


def get_pos_runtime_capabilities(
	target_exists: Callable[[str, str], bool] | None = None,
) -> POSRuntimeCapabilities:
	"""Resolve the installed POS provider without making POSNext a dependency.

	POSNext is preferred only when both of its shift DocTypes exist. Otherwise
	RetailEdge falls back to ERPNext's native Point of Sale page and POS Opening
	Entry / POS Closing Entry documents.
	"""
	exists = target_exists or _default_target_exists
	if exists("DocType", POSNEXT_OPENING_SHIFT) and exists("DocType", POSNEXT_CLOSING_SHIFT):
		return POSRuntimeCapabilities(
			provider="posnext",
			start_link_type="URL",
			start_target=POSNEXT_POS_URL,
			start_url=POSNEXT_POS_URL,
			opening_doctype=POSNEXT_OPENING_SHIFT,
			closing_doctype=POSNEXT_CLOSING_SHIFT,
		)

	opening = ERPNEXT_POS_OPENING_ENTRY if exists("DocType", ERPNEXT_POS_OPENING_ENTRY) else None
	closing = ERPNEXT_POS_CLOSING_ENTRY if exists("DocType", ERPNEXT_POS_CLOSING_ENTRY) else None
	page = ERPNEXT_POS_PAGE if exists("Page", ERPNEXT_POS_PAGE) else None
	return POSRuntimeCapabilities(
		provider="erpnext",
		start_link_type="Page" if page else None,
		start_target=page,
		start_url=None,
		opening_doctype=opening,
		closing_doctype=closing,
	)
