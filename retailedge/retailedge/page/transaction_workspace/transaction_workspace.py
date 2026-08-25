from __future__ import annotations

from typing import Any

import frappe

from retailedge.operating_context import get_operating_context
from retailedge.pos_runtime import get_pos_runtime_capabilities

TRANSACTION_ACTIONS: tuple[dict[str, str], ...] = (
	{"key": "sales-invoice", "label": "Sales Invoice", "doctype": "Sales Invoice", "kind": "sell"},
	{"key": "sales-order", "label": "Sales Order", "doctype": "Sales Order", "kind": "sell"},
	{"key": "delivery-note", "label": "Delivery Note", "doctype": "Delivery Note", "kind": "sell"},
	{"key": "purchase-invoice", "label": "Purchase Invoice", "doctype": "Purchase Invoice", "kind": "buy"},
	{"key": "purchase-order", "label": "Purchase Order", "doctype": "Purchase Order", "kind": "buy"},
	{"key": "purchase-receipt", "label": "Purchase Receipt", "doctype": "Purchase Receipt", "kind": "buy"},
	{"key": "stock-entry", "label": "Stock Transfer", "doctype": "Stock Entry", "kind": "stock"},
)


def _can_create(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "create"))
	except Exception:
		return False


def _doctype_exists(doctype: str | None) -> bool:
	return bool(doctype and frappe.db.exists("DocType", doctype))


@frappe.whitelist()
def get_transaction_workspace_context() -> dict[str, Any]:
	"""Return a permission-aware transaction host context without writing state."""
	operating = get_operating_context() or {}
	pos = get_pos_runtime_capabilities()

	actions = [
		{**action, "can_create": True}
		for action in TRANSACTION_ACTIONS
		if _can_create(action["doctype"])
	]

	return {
		"operating": {
			"company": operating.get("company") or "",
			"branch": operating.get("branch") or "",
			"default_pos_profile": operating.get("default_pos_profile") or "",
			"default_stock_location": operating.get("default_stock_location") or "",
		},
		"pos": {
			"provider": pos.provider,
			"start_link_type": pos.start_link_type,
			"start_target": pos.start_target,
			"start_url": pos.start_url,
			"opening_doctype": pos.opening_doctype if _doctype_exists(pos.opening_doctype) else None,
			"closing_doctype": pos.closing_doctype if _doctype_exists(pos.closing_doctype) else None,
			"embedded": False,
		},
		"actions": actions,
		"user_name": frappe.get_user().get_fullname() if getattr(frappe, "session", None) else "",
	}
