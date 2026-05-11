from __future__ import annotations

from importlib import import_module
from typing import Any

import frappe

from retailedge.utils.settings import get_retailedge_settings


def is_coreedge_installed() -> bool:
	return "coreedge" in frappe.get_installed_apps()


def is_coreedge_enabled() -> bool:
	if not is_coreedge_installed():
		return False

	settings = get_retailedge_settings()
	return bool(settings.enable_coreedge_integration)


def get_coreedge_status() -> dict[str, int]:
	settings = get_retailedge_settings()
	enabled = is_coreedge_enabled()

	return {
		"installed": int(is_coreedge_installed()),
		"enabled": int(enabled),
		"payments_enabled": int(enabled and bool(settings.enable_coreedge_payment_requests)),
		"notifications_enabled": int(enabled and bool(settings.enable_coreedge_notifications)),
		"branch_context_enabled": int(enabled and bool(settings.enable_coreedge_branch_context)),
		"portal_required": int(enabled and bool(settings.coreedge_required_for_portal)),
	}


def load_coreedge_attr(*paths: str) -> Any | None:
	if not is_coreedge_installed():
		return None

	for path in paths:
		module_name, _, attr_name = path.rpartition(".")
		if not module_name or not attr_name:
			continue

		try:
			module = import_module(module_name)
			attr = getattr(module, attr_name, None)
		except Exception:
			continue

		if attr:
			return attr

	return None


def log_coreedge_debug(message: str, *, context: dict[str, Any] | None = None) -> None:
	logger = frappe.logger("retailedge.coreedge")
	if context:
		logger.debug("%s | %s", message, frappe.as_json(context))
		return

	logger.debug(message)
