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

SUPPLIER_ACTION: dict[str, Any] = {
	"key": "new-supplier",
	"label": "New Supplier",
	"description": "Create a supplier using ERPNext's native Supplier master and validation rules.",
	"doctype": "Supplier",
	"icon": "user",
	"experience": "act",
	"mode": "quick_entry",
	"master_entry": True,
}

MASTER_ACTIONS: tuple[dict[str, Any], ...] = (CUSTOMER_ACTION, SUPPLIER_ACTION)


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	"""Extend the canonical Business Hub context with safe simple-master actions."""
	context = deepcopy(_base_business_hub_context() or {})
	quick_actions = list(context.get("quick_actions") or [])
	existing_keys = {action.get("key") for action in quick_actions}
	for action in MASTER_ACTIONS:
		if action["key"] in existing_keys or not _can_create_master(action["doctype"]):
			continue
		quick_actions.append(deepcopy(action))
		existing_keys.add(action["key"])
	context["quick_actions"] = quick_actions
	feature_flags = dict(context.get("feature_flags") or {})
	feature_flags["simple_master_data_stage"] = "customer_supplier"
	context["feature_flags"] = feature_flags
	return context


def _can_create_master(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "create"))
	except Exception:
		return False


def _can_create_customer() -> bool:
	return _can_create_master("Customer")


def _can_create_supplier() -> bool:
	return _can_create_master("Supplier")
