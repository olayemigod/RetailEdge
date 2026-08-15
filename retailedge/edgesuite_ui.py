from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe
from frappe import _

from retailedge.pos_runtime import (
	ERPNEXT_POS_CLOSING_ENTRY,
	ERPNEXT_POS_OPENING_ENTRY,
	POSNEXT_POS_URL,
	START_POS_LABEL,
	get_pos_runtime_capabilities,
)

PROGRAMME_EXPERIENCES: tuple[dict[str, Any], ...] = (
	{
		"key": "navigate",
		"label": "Navigate",
		"description": "Professional, role-aware access to RetailEdge workspaces, transactions, reports, and setup.",
		"icon": "grid",
		"status": "In Progress",
	},
	{
		"key": "act",
		"label": "Act",
		"description": "Quick business actions today, followed by guided entries that create native ERPNext documents.",
		"icon": "zap",
		"status": "Foundation",
	},
	{
		"key": "operate",
		"label": "Operate",
		"description": "Role-focused workspaces, review queues, approvals, and exception handling.",
		"icon": "briefcase",
		"status": "Planned",
	},
	{
		"key": "understand",
		"label": "Understand",
		"description": "Trusted operational reports, owner dashboards, branch insights, cash, stock, and profitability.",
		"icon": "bar-chart-2",
		"status": "In Progress",
	},
	{
		"key": "respond",
		"label": "Respond",
		"description": "Actionable alerts, reminders, follow-up tasks, and explainable recommendations.",
		"icon": "bell",
		"status": "Planned",
	},
)


NAVIGATION_GROUPS: tuple[dict[str, Any], ...] = (
	{
		"key": "dashboard",
		"label": "Dashboard",
		"icon": "chart",
		"items": (
			{
				"label": "RetailEdge Business Hub",
				"target_type": "Page",
				"target": "retailedge-business-hub",
				"icon": "home",
			},
			{
				"label": "Branch Performance",
				"target_type": "Report",
				"target": "RetailEdge Branch Performance Summary",
				"icon": "chart",
			},
			{
				"label": "Salesperson Performance",
				"target_type": "Page",
				"target": "salesperson-performance-dashboard",
				"icon": "user",
			},
		),
	},
	{
		"key": "sales",
		"label": "Sales",
		"icon": "activity",
		"items": (
			{
				"label": START_POS_LABEL,
				"target_type": "URL",
				"target": POSNEXT_POS_URL,
				"runtime_target": "pos",
				"icon": "grid",
			},
			{"label": "Sales Invoices", "target_type": "DocType", "target": "Sales Invoice", "icon": "clipboard"},
			{"label": "Sales Orders", "target_type": "DocType", "target": "Sales Order", "icon": "clipboard"},
			{"label": "Delivery Notes", "target_type": "DocType", "target": "Delivery Note", "icon": "clipboard"},
			{
				"label": "POS Opening",
				"target_type": "DocType",
				"target": ERPNEXT_POS_OPENING_ENTRY,
				"runtime_target": "pos_opening",
				"icon": "calendar",
			},
			{
				"label": "POS Closing",
				"target_type": "DocType",
				"target": ERPNEXT_POS_CLOSING_ENTRY,
				"runtime_target": "pos_closing",
				"icon": "calendar",
			},
		),
	},
	{
		"key": "purchases",
		"label": "Purchases",
		"icon": "clipboard",
		"items": (
			{"label": "Purchase Invoices", "target_type": "DocType", "target": "Purchase Invoice", "icon": "clipboard"},
			{"label": "Purchase Orders", "target_type": "DocType", "target": "Purchase Order", "icon": "clipboard"},
			{"label": "Purchase Receipts", "target_type": "DocType", "target": "Purchase Receipt", "icon": "clipboard"},
		),
	},
	{
		"key": "inventory",
		"label": "Inventory",
		"icon": "layers",
		"items": (
			{"label": "Items", "target_type": "DocType", "target": "Item", "icon": "layers"},
			{"label": "Warehouses", "target_type": "DocType", "target": "Warehouse", "icon": "building"},
			{
				"label": "Stock Movement History",
				"target_type": "Report",
				"target": "RetailEdge Stock Movement History",
				"icon": "report",
			},
			{"label": "Stock Balance", "target_type": "Report", "target": "Stock Balance", "icon": "report"},
			{"label": "Stock Transfers", "target_type": "DocType", "target": "Stock Entry", "icon": "layers"},
			{"label": "Stock Count", "target_type": "DocType", "target": "Stock Reconciliation", "icon": "clipboard"},
			{"label": "Material Requests", "target_type": "DocType", "target": "Material Request", "icon": "clipboard"},
		),
	},
	{
		"key": "cash-banking",
		"label": "Cash & Banking",
		"icon": "wallet",
		"items": (
			{"label": "Payment Entries", "target_type": "DocType", "target": "Payment Entry", "icon": "wallet"},
			{"label": "Bank Transactions", "target_type": "DocType", "target": "Bank Transaction", "icon": "wallet"},
			{
				"label": "Import Bank Statement",
				"target_type": "DocType",
				"target": "RetailEdge Payment Statement Import",
				"icon": "clipboard",
			},
			{
				"label": "Bank Matching",
				"target_type": "Report",
				"target": "RetailEdge Bank Transaction Matching",
				"icon": "report",
			},
		),
	},
	{
		"key": "expenses",
		"label": "Expenses",
		"icon": "report",
		"items": (
			{
				"label": "Cashier Expenses",
				"target_type": "DocType",
				"target": "RetailEdge Cashier Expense",
				"icon": "wallet",
			},
			{"label": "Expense Claims", "target_type": "DocType", "target": "Expense Claim", "icon": "clipboard"},
		),
	},
	{
		"key": "customers-suppliers",
		"label": "Customers & Suppliers",
		"icon": "user",
		"items": (
			{"label": "Customers", "target_type": "DocType", "target": "Customer", "icon": "user"},
			{"label": "Suppliers", "target_type": "DocType", "target": "Supplier", "icon": "user"},
			{"label": "Accounts Receivable", "target_type": "Report", "target": "Accounts Receivable", "icon": "report"},
			{"label": "Accounts Payable", "target_type": "Report", "target": "Accounts Payable", "icon": "report"},
		),
	},
	{
		"key": "reviews-controls",
		"label": "Reviews & Controls",
		"icon": "shield",
		"items": (
			{
				"label": "Bank Match Reviews",
				"target_type": "DocType",
				"target": "RetailEdge Bank Transaction Match",
				"icon": "shield",
			},
			{
				"label": "Daily Sales Audit",
				"target_type": "DocType",
				"target": "RetailEdge Daily Sales Audit",
				"icon": "shield",
			},
			{
				"label": "Cashier Expense Review",
				"target_type": "Report",
				"target": "RetailEdge Cashier Expense Review",
				"icon": "report",
			},
			{
				"label": "Cash Shift Verification",
				"target_type": "Report",
				"target": "RetailEdge Cash Shift Verification",
				"icon": "report",
			},
			{
				"label": "Invoice Payment Audit",
				"target_type": "Report",
				"target": "RetailEdge Invoice Payment Audit",
				"icon": "report",
			},
			{
				"label": "POS Closing Variance vs Expenses",
				"target_type": "Report",
				"target": "POS Closing Variance vs Expenses",
				"icon": "report",
			},
			{
				"label": "Unmatched Bank Transactions",
				"target_type": "Report",
				"target": "RetailEdge Unmatched Bank Transactions",
				"icon": "report",
			},
			{
				"label": "Unmatched Bank Payments",
				"target_type": "Report",
				"target": "RetailEdge Unmatched Bank Payment Events",
				"icon": "report",
			},
			{
				"label": "Reconciliation Readiness",
				"target_type": "Report",
				"target": "RetailEdge Bank Match Reconciliation Readiness",
				"icon": "shield",
			},
			{
				"label": "Reconciliation Handoff",
				"target_type": "Report",
				"target": "RetailEdge Reconciliation Handoff",
				"icon": "report",
			},
		),
	},
	{
		"key": "reports-insights",
		"label": "Reports & Insights",
		"icon": "chart",
		"items": (
			{
				"label": "Daily Sales Audit Register",
				"target_type": "Report",
				"target": "RetailEdge Daily Sales Audit Register",
				"icon": "report",
			},
			{"label": "Stock Ledger", "target_type": "Report", "target": "Stock Ledger", "icon": "report"},
			{"label": "Stock Projected Qty", "target_type": "Report", "target": "Stock Projected Qty", "icon": "report"},
			{"label": "Stock Ageing", "target_type": "Report", "target": "Stock Ageing", "icon": "report"},
			{
				"label": "Batch-Wise Balance History",
				"target_type": "Report",
				"target": "Batch-Wise Balance History",
				"icon": "report",
			},
			{
				"label": "Serial No and Batch Traceability",
				"target_type": "Report",
				"target": "Serial No and Batch Traceability",
				"icon": "report",
			},
		),
	},
	{
		"key": "setup",
		"label": "Setup",
		"icon": "settings",
		"items": (
			{"label": "RetailEdge Settings", "target_type": "DocType", "target": "RetailEdge Settings", "icon": "settings"},
			{"label": "Branch Profiles", "target_type": "DocType", "target": "RetailEdge Branch Profile", "icon": "building"},
			{
				"label": "Expense Categories",
				"target_type": "DocType",
				"target": "RetailEdge Expense Category",
				"icon": "layers",
			},
			{"label": "Bank Accounts", "target_type": "DocType", "target": "Bank Account", "icon": "wallet"},
			{"label": "Modes of Payment", "target_type": "DocType", "target": "Mode of Payment", "icon": "wallet"},
			{
				"label": "Bank Statement Mapping",
				"target_type": "DocType",
				"target": "RetailEdge Statement Mapping Template",
				"icon": "settings",
			},
		),
	},
)


QUICK_ACTIONS: tuple[dict[str, Any], ...] = (
	{
		"key": "new-sales-invoice",
		"label": "New Sales Invoice",
		"description": "Create a formal cash, credit, wholesale, or account-customer invoice.",
		"doctype": "Sales Invoice",
		"icon": "file-text",
		"experience": "act",
		"mode": "native_fallback",
	},
	{
		"key": "receive-customer-payment",
		"label": "Receive Customer Payment",
		"description": "Record and allocate money received from a customer.",
		"doctype": "Payment Entry",
		"icon": "download",
		"experience": "act",
		"mode": "native_fallback",
	},
	{
		"key": "pay-supplier",
		"label": "Pay Supplier",
		"description": "Record a supplier payment and allocate outstanding invoices.",
		"doctype": "Payment Entry",
		"icon": "upload",
		"experience": "act",
		"mode": "native_fallback",
	},
	{
		"key": "record-expense",
		"label": "Record Cashier Expense",
		"description": "Record a controlled expense arising during an open cashier shift.",
		"doctype": "RetailEdge Cashier Expense",
		"icon": "credit-card",
		"experience": "act",
		"mode": "available",
	},
	{
		"key": "record-purchase",
		"label": "Record Purchase",
		"description": "Create a purchase invoice for stock, services, or operating expenses.",
		"doctype": "Purchase Invoice",
		"icon": "shopping-bag",
		"experience": "act",
		"mode": "native_fallback",
	},
	{
		"key": "transfer-stock",
		"label": "Transfer Stock",
		"description": "Move stock between permitted warehouses using a native Stock Entry.",
		"doctype": "Stock Entry",
		"icon": "repeat",
		"experience": "act",
		"mode": "native_fallback",
	},
)


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	"""Return permission-aware metadata for the RetailEdge EdgeSuite Business Hub.

	This endpoint intentionally excludes product-switcher data. Product switching is
	suspended while the RetailEdge navigation, guided-entry, report, and dashboard
	foundations are migrated.
	"""
	roles = set(frappe.get_roles(frappe.session.user))
	return {
		"programme_experiences": deepcopy(PROGRAMME_EXPERIENCES),
		"navigation_groups": _get_permitted_navigation_groups(roles),
		"quick_actions": _get_permitted_quick_actions(),
		"context": {
			"user": frappe.session.user,
			"user_name": frappe.utils.get_fullname(frappe.session.user),
			"company": frappe.defaults.get_user_default("Company") or "",
			"branch": frappe.defaults.get_user_default("RetailEdge Branch")
			or frappe.defaults.get_user_default("Branch")
			or "",
		},
		"feature_flags": {
			"product_switcher_enabled": False,
			"guided_entries_stage": "foundation",
			"native_document_fallback_enabled": True,
		},
	}


def _get_permitted_navigation_groups(roles: set[str]) -> list[dict[str, Any]]:
	groups: list[dict[str, Any]] = []
	for group in NAVIGATION_GROUPS:
		required_roles = set(group.get("required_roles") or ())
		if required_roles and not roles.intersection(required_roles):
			continue

		items: list[dict[str, Any]] = []
		for item in group["items"]:
			resolved = _resolve_navigation_item(item)
			if resolved is not None and _can_open_target(resolved):
				items.append(resolved)
		if not items:
			continue
		groups.append(
			{
				"key": group["key"],
				"label": _(group["label"]),
				"icon": group.get("icon") or "",
				"items": items,
			}
		)
	return groups


def _resolve_navigation_item(item: dict[str, Any]) -> dict[str, Any] | None:
	resolved = deepcopy(item)
	runtime_target = resolved.pop("runtime_target", None)
	if runtime_target is None:
		return resolved

	capabilities = get_pos_runtime_capabilities(_target_exists)
	if runtime_target == "pos":
		if not capabilities.start_link_type or not capabilities.start_target:
			return None
		resolved["target_type"] = capabilities.start_link_type
		resolved["target"] = capabilities.start_target
		return resolved
	if runtime_target == "pos_opening":
		if not capabilities.opening_doctype:
			return None
		resolved["label"] = capabilities.opening_doctype
		resolved["target_type"] = "DocType"
		resolved["target"] = capabilities.opening_doctype
		return resolved
	if runtime_target == "pos_closing":
		if not capabilities.closing_doctype:
			return None
		resolved["label"] = capabilities.closing_doctype
		resolved["target_type"] = "DocType"
		resolved["target"] = capabilities.closing_doctype
		return resolved
	return resolved


def _get_permitted_quick_actions() -> list[dict[str, Any]]:
	actions: list[dict[str, Any]] = []
	for action in QUICK_ACTIONS:
		doctype = action["doctype"]
		if not _doctype_exists(doctype) or not _has_permission(doctype, "create"):
			continue
		actions.append(deepcopy(action))
	return actions


def _can_open_target(item: dict[str, Any]) -> bool:
	target_type = item["target_type"]
	target = item["target"]
	if target_type == "URL":
		return True
	if target_type == "DocType":
		return _doctype_exists(target) and _has_permission(target, "read")
	if target_type in {"Page", "Report"}:
		return _target_exists(target_type, target)
	return False


def _target_exists(target_type: str, target: str) -> bool:
	try:
		return bool(frappe.db.exists(target_type, target))
	except Exception:
		return False


def _doctype_exists(doctype: str) -> bool:
	return _target_exists("DocType", doctype)


def _has_permission(doctype: str, permission_type: str) -> bool:
	try:
		return bool(frappe.has_permission(doctype, permission_type))
	except Exception:
		return False
