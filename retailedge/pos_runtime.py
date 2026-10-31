from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import frappe

START_POS_LABEL = "Start POS"
POSNEXT_APP = "pos_next"
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


def _default_app_installed(app_name: str) -> bool:
	try:
		return app_name in set(frappe.get_installed_apps() or [])
	except Exception:
		return False


def get_pos_runtime_capabilities(
	target_exists: Callable[[str, str], bool] | None = None,
	app_installed: Callable[[str], bool] | None = None,
) -> POSRuntimeCapabilities:
	"""Resolve the installed POS provider without making POSNext a dependency.

	POSNext owns its web runtime at ``/pos/``. Detect the installed app first so
	RetailEdge does not incorrectly fall back to ERPNext's Desk Point of Sale Page
	when a POSNext schema is partially migrated or one optional shift DocType is
	missing. Existing sites whose POSNext shift DocTypes are present remain
	compatible even if the installed-app probe is unavailable.
	"""
	exists = target_exists or _default_target_exists
	installed = app_installed or _default_app_installed
	posnext_opening = POSNEXT_OPENING_SHIFT if exists("DocType", POSNEXT_OPENING_SHIFT) else None
	posnext_closing = POSNEXT_CLOSING_SHIFT if exists("DocType", POSNEXT_CLOSING_SHIFT) else None
	if installed(POSNEXT_APP) or (posnext_opening and posnext_closing):
		return POSRuntimeCapabilities(
			provider="posnext",
			start_link_type="URL",
			start_target=POSNEXT_POS_URL,
			start_url=POSNEXT_POS_URL,
			opening_doctype=posnext_opening,
			closing_doctype=posnext_closing,
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
