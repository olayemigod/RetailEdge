from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe

from retailedge.edgesuite_ui import get_retailedge_business_hub_context as _base_business_hub_context

CUSTOMER_ACTION: dict[str, Any] = {
	"key": "new-customer",
	"label": "New Customer",
	"description": "Create a customer using ERPNext's native Customer master and validation rules.",
	"doctype": "Customer",
	"icon": "user",
	"experience": "act",
	"mode": "quick_entry",
	"master_entry": True,
}


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	"""Extend the canonical Business Hub context with safe simple-master actions."""
	context = deepcopy(_base_business_hub_context() or {})
	quick_actions = list(context.get("quick_actions") or [])
	if _can_create_customer() and not any(action.get("key") == CUSTOMER_ACTION["key"] for action in quick_actions):
		quick_actions.append(deepcopy(CUSTOMER_ACTION))
	context["quick_actions"] = quick_actions
	feature_flags = dict(context.get("feature_flags") or {})
	feature_flags["simple_master_data_stage"] = "customer"
	context["feature_flags"] = feature_flags
	return context


def _can_create_customer() -> bool:
	try:
		return bool(frappe.db.exists("DocType", "Customer") and frappe.has_permission("Customer", "create"))
	except Exception:
		return False
