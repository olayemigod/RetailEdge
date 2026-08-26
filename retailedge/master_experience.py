from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe

from retailedge.edgesuite_ui import get_retailedge_business_hub_context as _base_business_hub_context
from retailedge.operating_context import get_operating_context

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

ITEM_ACTION: dict[str, Any] = {
	"key": "new-item",
	"label": "New Product",
	"description": "Create an ERPNext Item without exposing buying cost or valuation fields.",
	"doctype": "Item",
	"icon": "layers",
	"experience": "act",
	"mode": "quick_entry",
	"master_entry": True,
}

MASTER_ACTIONS: tuple[dict[str, Any], ...] = (CUSTOMER_ACTION, SUPPLIER_ACTION, ITEM_ACTION)

PROMOTED_R4_PAGE_TARGETS: dict[str, str] = {
	"Cashier Expense Review": "expense-review",
	"Cash Shift Verification": "cash-shift-verification",
	"Daily Sales Audit": "daily-sales-audit",
}

OPERATING_CONTEXT_ITEM: dict[str, Any] = {
	"label": "Operating Context",
	"description": "Choose the Company and Branch that should guide new work and branch defaults.",
	"target_type": "Page",
	"target": "operating-context",
	"icon": "building",
}

TRANSACTION_WORKSPACE_ITEM: dict[str, Any] = {
	"label": "Transaction Workspace",
	"description": "Start sales, purchasing, stock and POS work inside the RetailEdge operating shell.",
	"target_type": "Page",
	"target": "transaction-workspace",
	"icon": "shopping-cart",
}

PROFESSIONAL_SELLING_ITEM: dict[str, Any] = {
	"label": "Professional Selling",
	"description": "Prepare Quotations, Sales Orders and Delivery Notes in one guided RetailEdge selling flow.",
	"target_type": "Page",
	"target": "professional-selling",
	"icon": "shopping-bag",
}

SETUP_HUB_ITEM: dict[str, Any] = {
	"label": "Setup",
	"description": "Configure RetailEdge business rules, Branch Setup, payment masters and statement mappings.",
	"target_type": "Page",
	"target": "retailedge-setup",
	"icon": "settings",
}

SETUP_MANAGED_DOCTYPES = {
	"RetailEdge Settings",
	"RetailEdge Branch Profile",
	"RetailEdge Expense Category",
	"RetailEdge Statement Mapping Template",
}


def _promote_browser_approved_r4_pages(navigation_groups: list[dict[str, Any]]) -> None:
	"""Promote only R4 pages that completed local browser QA.

	Stock Movement History deliberately remains on its native Query Report until
	its separate parity/export/mobile promotion gate is completed.
	"""
	for group in navigation_groups:
		for item in group.get("items") or []:
			target = PROMOTED_R4_PAGE_TARGETS.get(str(item.get("label") or ""))
			if not target:
				continue
			item["target_type"] = "Page"
			item["target"] = target


def _can_open_page(target: str) -> bool:
	try:
		return bool(frappe.db.exists("Page", target) and frappe.has_permission("Page", "read", doc=target))
	except Exception:
		return False


def _can_open_operating_context_page() -> bool:
	return _can_open_page(OPERATING_CONTEXT_ITEM["target"])


def _add_operating_context_navigation(navigation_groups: list[dict[str, Any]]) -> None:
	if not _can_open_operating_context_page():
		return
	for group in navigation_groups:
		if group.get("key") != "home":
			continue
		items = list(group.get("items") or [])
		if any(item.get("target") == OPERATING_CONTEXT_ITEM["target"] for item in items):
			return
		insert_at = 1 if items else 0
		items.insert(insert_at, deepcopy(OPERATING_CONTEXT_ITEM))
		group["items"] = items
		return


def _promote_transaction_workspace(navigation_groups: list[dict[str, Any]]) -> None:
	"""Add the EdgeSuite transaction host without removing the direct POS path.

	Transaction Workspace is the preferred RetailEdge operating entry point, but
	the existing provider-aware Start POS item remains available. That preserves a
	direct POSNext route for offline resilience and an explicit native POS fallback.
	If the Page is unavailable, navigation is left untouched.
	"""
	if not _can_open_page(TRANSACTION_WORKSPACE_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "sell":
			continue
		items = list(group.get("items") or [])
		if any(item.get("target_type") == "Page" and item.get("target") == TRANSACTION_WORKSPACE_ITEM["target"] for item in items):
			return
		pos_index = next((index for index, item in enumerate(items) if item.get("runtime_target") == "pos"), 0)
		items.insert(pos_index, deepcopy(TRANSACTION_WORKSPACE_ITEM))
		group["items"] = items
		return


def _promote_professional_selling(navigation_groups: list[dict[str, Any]]) -> None:
	"""Expose the guided selling suite while retaining native ERPNext fallbacks."""
	if not _can_open_page(PROFESSIONAL_SELLING_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "sell":
			continue
		items = list(group.get("items") or [])
		if any(item.get("target_type") == "Page" and item.get("target") == PROFESSIONAL_SELLING_ITEM["target"] for item in items):
			return
		workspace_index = next(
			(index for index, item in enumerate(items) if item.get("target") == TRANSACTION_WORKSPACE_ITEM["target"]),
			-1,
		)
		items.insert(workspace_index + 1 if workspace_index >= 0 else 0, deepcopy(PROFESSIONAL_SELLING_ITEM))
		group["items"] = items
		return


def _consolidate_setup_navigation(navigation_groups: list[dict[str, Any]]) -> None:
	"""Route RetailEdge-owned setup masters through one EdgeSuite Setup hub.

	Native DocTypes remain authoritative and are opened from the Setup hub as
	explicit full-form fallbacks. Bank Account and Mode of Payment remain visible
	native ERPNext destinations in the Setup group.
	"""
	if not _can_open_page(SETUP_HUB_ITEM["target"]):
		return

	setup_group = None
	for group in navigation_groups:
		if group.get("key") == "setup":
			setup_group = group
		items = []
		for item in group.get("items") or []:
			if item.get("target_type") == "DocType" and item.get("target") in SETUP_MANAGED_DOCTYPES:
				continue
			items.append(item)
		group["items"] = items

	if setup_group is None:
		return
	items = list(setup_group.get("items") or [])
	if not any(item.get("target_type") == "Page" and item.get("target") == SETUP_HUB_ITEM["target"] for item in items):
		items.insert(0, deepcopy(SETUP_HUB_ITEM))
	setup_group["items"] = items


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	"""Extend the canonical Business Hub context with safe product UX refinements."""
	context = deepcopy(_base_business_hub_context() or {})
	navigation_groups = context.get("navigation_groups") or []
	_promote_browser_approved_r4_pages(navigation_groups)
	_add_operating_context_navigation(navigation_groups)
	_promote_transaction_workspace(navigation_groups)
	_promote_professional_selling(navigation_groups)
	_consolidate_setup_navigation(navigation_groups)

	quick_actions = list(context.get("quick_actions") or [])
	existing_keys = {action.get("key") for action in quick_actions}
	for action in MASTER_ACTIONS:
		if action["key"] in existing_keys or not _can_create_master(action["doctype"]):
			continue
		quick_actions.append(deepcopy(action))
		existing_keys.add(action["key"])
	context["quick_actions"] = quick_actions

	operating = get_operating_context()
	user_context = dict(context.get("context") or {})
	user_context.update(
		{
			"company": operating.get("company") or "",
			"branch": operating.get("branch") or "",
			"operating_context_source": operating.get("source") or "",
			"default_pos_profile": operating.get("default_pos_profile") or "",
			"default_stock_location": operating.get("default_stock_location") or "",
		}
	)
	context["context"] = user_context

	feature_flags = dict(context.get("feature_flags") or {})
	feature_flags["simple_master_data_stage"] = "customer_supplier_item"
	feature_flags["r4_browser_promoted_pages"] = sorted(PROMOTED_R4_PAGE_TARGETS.values())
	feature_flags["operating_branch_context"] = "phase2_active"
	feature_flags["setup_route_consolidation"] = "edgesuite_setup"
	feature_flags["transaction_workspace"] = "edgesuite_host"
	feature_flags["professional_selling"] = "edgesuite_guided"
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


def _can_create_item() -> bool:
	return _can_create_master("Item")
