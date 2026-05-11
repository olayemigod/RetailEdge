from __future__ import annotations

import frappe

from retailedge.utils.settings import get_retailedge_settings


def _get_configured_hidden_cost_price_roles() -> set[str]:
	settings = get_retailedge_settings()

	return {
		row.role
		for row in settings.cost_price_hidden_roles or []
		if getattr(row, "role", None)
	}


def get_hidden_cost_price_roles() -> set[str]:
	settings = get_retailedge_settings()

	if not settings.hide_cost_price_for_selected_roles:
		return set()

	return _get_configured_hidden_cost_price_roles()


def should_hide_cost_price(user: str | None = None) -> bool:
	settings = get_retailedge_settings()

	if not settings.hide_cost_price_for_selected_roles:
		return False

	user = user or frappe.session.user
	if user in {"Guest", "Administrator"}:
		return False

	user_roles = set(frappe.get_roles(user))
	if "System Manager" in user_roles:
		return False

	return bool(user_roles.intersection(get_hidden_cost_price_roles()))


def get_cost_price_visibility_context(user: str | None = None) -> dict[str, object]:
	user = user or frappe.session.user
	user_roles = set() if user == "Guest" else set(frappe.get_roles(user))
	can_view_hidden_roles = user == "Administrator" or "System Manager" in user_roles

	return {
		"hide_cost_price": int(should_hide_cost_price(user=user)),
		"hidden_roles": sorted(_get_configured_hidden_cost_price_roles()) if can_view_hidden_roles else [],
	}
