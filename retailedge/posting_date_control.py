from __future__ import annotations

import frappe

from retailedge.utils.settings import get_retailedge_settings


def _get_configured_posting_date_allowed_roles() -> set[str]:
	settings = get_retailedge_settings()

	return {
		row.role
		for row in settings.posting_date_allowed_roles or []
		if getattr(row, "role", None)
	}


def get_posting_date_allowed_roles() -> set[str]:
	settings = get_retailedge_settings()

	if not settings.enable_posting_date_control:
		return set()

	if not settings.allow_pos_posting_date_override:
		return set()

	return _get_configured_posting_date_allowed_roles()


def can_override_posting_date(user: str | None = None) -> bool:
	settings = get_retailedge_settings()
	if not settings.enable_posting_date_control:
		return False

	if not settings.allow_pos_posting_date_override:
		return False

	user = user or frappe.session.user
	if user == "Guest":
		return False

	if user == "Administrator":
		return True

	user_roles = set(frappe.get_roles(user))
	if "System Manager" in user_roles:
		return True

	return bool(user_roles.intersection(get_posting_date_allowed_roles()))


def get_posting_date_context(user: str | None = None) -> dict[str, object]:
	settings = get_retailedge_settings()
	user = user or frappe.session.user
	user_roles = set() if user == "Guest" else set(frappe.get_roles(user))
	can_view_allowed_roles = user == "Administrator" or "System Manager" in user_roles

	return {
		"enabled": int(bool(settings.enable_posting_date_control)),
		"allow_override": int(bool(settings.allow_pos_posting_date_override)),
		"can_override": int(can_override_posting_date(user=user)),
		"allowed_roles": sorted(_get_configured_posting_date_allowed_roles()) if can_view_allowed_roles else [],
	}
