from __future__ import annotations

from typing import Any

import frappe
from frappe import _


USER_DEFAULT_KEY = "RetailEdge Transaction Entry Style"
DEFAULT_PREFERENCE = "smart"
PREFERENCE_OPTIONS: tuple[dict[str, str], ...] = (
	{
		"value": "smart",
		"label": "Smart",
		"description": "Use the recommended entry surface for the current workspace. Quick-entry limits and full-page handoff remain active.",
	},
	{
		"value": "quick",
		"label": "Quick Entry",
		"description": "Prefer compact transaction popups where a governed quick-entry flow is available.",
	},
	{
		"value": "full",
		"label": "Full Page",
		"description": "Prefer persistent EdgeSuite transaction pages for supported sales, purchase and stock work.",
	},
)
_ALLOWED = {row["value"] for row in PREFERENCE_OPTIONS}


def _current_user() -> str:
	user = str(getattr(getattr(frappe, "session", None), "user", "") or "").strip()
	if not user or user == "Guest":
		frappe.throw(_("Sign in before changing transaction entry preferences."), frappe.PermissionError)
	return user


def get_transaction_entry_style(*, user: str | None = None) -> str:
	user = str(user or getattr(getattr(frappe, "session", None), "user", "") or "").strip()
	if not user or user == "Guest":
		return DEFAULT_PREFERENCE
	value = str(frappe.defaults.get_user_default(USER_DEFAULT_KEY, user=user) or "").strip().lower()
	return value if value in _ALLOWED else DEFAULT_PREFERENCE


def _payload(value: str) -> dict[str, Any]:
	return {
		"value": value,
		"default": DEFAULT_PREFERENCE,
		"options": [dict(row) for row in PREFERENCE_OPTIONS],
		"scope": "user",
	}


@frappe.whitelist()
def get_transaction_entry_preference() -> dict[str, Any]:
	return _payload(get_transaction_entry_style(user=_current_user()))


@frappe.whitelist(methods=["POST"])
def set_transaction_entry_preference(value: str) -> dict[str, Any]:
	user = _current_user()
	value = str(value or "").strip().lower()
	if value not in _ALLOWED:
		frappe.throw(_("Choose Smart, Quick Entry or Full Page."), frappe.ValidationError)
	frappe.defaults.set_user_default(USER_DEFAULT_KEY, value, user=user)
	return _payload(value)
