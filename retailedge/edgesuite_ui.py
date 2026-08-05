from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe
from frappe import _


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
		"key": "home",
		"label": "Home",
		"items": (
			{"label": "RetailEdge Business Hub", "target_type": "Page", "target": "retailedge-business-hub"},
			{"label": "Salesperson Performance", "target_type": "Page", "target": "salesperson-performance-dashboard"},
			{"label": "Branch Performance", "target_type": "Report", "target": "RetailEdge Branch Performance Summary"},
		),
	},
	{
		"key": "sales",
		"label": "Sales",
		"items": (
			{"label": "Start POS", "target_type": "URL", "target": "/pos/"},
			{"label": "Sales Invoices", "target_type": "DocType", "target": "Sales Invoice"},
			{"label": "Customers", "target_type": "DocType", "target": "Customer"},
			{"label": "Sales Orders", "target_type": "DocType", "target": "Sales Order"},
			{"label": "Delivery Notes", "target_type": "DocType", "target": "Delivery Note"},
		),
	},
	{
		"key": "purchases",
		"label": "Purchases",
		"items": (
			{"label": "Purchase Invoices", "target_type": "DocType", "target": "Purchase Invoice"},
			{"label": "Purchase Orders", "target_type": "DocType", "target": "Purchase Order"},
			{"label": "Purchase Receipts", "target_type": "DocType", "target": "Purchase Receipt"},
			{"label": "Suppliers", "target_type": "DocType", "target": "Supplier"},
		),
	},
	{
		"key": "inventory",
		"label": "Inventory",
		"items": (
			{"label": "Items", "target_type": "DocType", "target": "Item"},
			{"label": "Warehouses", "target_type": "DocType", "target": "Warehouse"},
			{"label": "Stock Movement History", "target_type": "Report", "target": "RetailEdge Stock Movement History"},
			{"label": "Stock Balance", "target_type": "Report", "target": "Stock Balance"},
			{"label": "Stock Transfers", "target_type": "DocType", "target": "Stock Entry"},
			{"label": "Stock Count", "target_type": "DocType", "target": "Stock Reconciliation"},
		),
	},
	{
		"key": "cash-banking",
		"label": "Cash & Banking",
		"items": (
			{"label": "Payment Entries", "target_type": "DocType", "target": "Payment Entry"},
			{"label": "Bank Transactions", "target_type": "DocType", "target": "Bank Transaction"},
			{"label": "Bank Matching", "target_type": "Report", "target": "RetailEdge Bank Transaction Matching"},
			{"label": "Bank Match Reviews", "target_type": "DocType", "target": "RetailEdge Bank Transaction Match"},
			{"label": "POS Opening Shifts", "target_type": "DocType", "target": "POS Opening Shift"},
			{"label": "POS Closing Shifts", "target_type": "DocType", "target": "POS Closing Shift"},
		),
	},
	{
		"key": "expenses",
		"label": "Expenses",
		"items": (
			{"label": "Cashier Expenses", "target_type": "DocType", "target": "RetailEdge Cashier Expense"},
			{"label": "Expense Claims", "target_type": "DocType", "target": "Expense Claim"},
			{"label": "Expense Categories", "target_type": "DocType", "target": "RetailEdge Expense Category"},
			{"label": "Cashier Expense Review", "target_type": "Report", "target": "RetailEdge Cashier Expense Review"},
		),
	},
	{
		"key": "customers-suppliers",
		"label": "Customers & Suppliers",
		"items": (
			{"label": "Customers", "target_type": "DocType", "target": "Customer"},
			{"label": "Suppliers", "target_type": "DocType", "target": "Supplier"},
			{"label": "Accounts Receivable", "target_type": "Report", "target": "Accounts Receivable"},
			{"label": "Accounts Payable", "target_type": "Report", "target": "Accounts Payable"},
		),
	},
	{
		"key": "reports-insights",
		"label": "Reports & Insights",
		"items": (
			{"label": "Branch Performance", "target_type": "Report", "target": "RetailEdge Branch Performance Summary"},
			{"label": "Salesperson Performance", "target_type": "Page", "target": "salesperson-performance-dashboard"},
			{"label": "Daily Sales Audit Register", "target_type": "Report", "target": "RetailEdge Daily Sales Audit Register"},
			{"label": "Invoice Payment Audit", "target_type": "Report", "target": "RetailEdge Invoice Payment Audit"},
			{"label": "POS Closing Variance vs Expenses", "target_type": "Report", "target": "POS Closing Variance vs Expenses"},
		),
	},
	{
		"key": "setup",
		"label": "Setup",
		"items": (
			{"label": "RetailEdge Settings", "target_type": "DocType", "target": "RetailEdge Settings"},
			{"label": "Branch Profiles", "target_type": "DocType", "target": "RetailEdge Branch Profile"},
			{"label": "Modes of Payment", "target_type": "DocType", "target": "Mode of Payment"},
			{"label": "Bank Accounts", "target_type": "DocType", "target": "Bank Account"},
		),
	},
	{
		"key": "administration",
		"label": "Administration",
		"required_roles": ("System Manager",),
		"items": (
			{"label": "Bank Match Batch Jobs", "target_type": "DocType", "target": "RetailEdge Bank Match Batch Job"},
			{"label": "Error Log", "target_type": "DocType", "target": "Error Log"},
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
			"branch": frappe.defaults.get_user_default("RetailEdge Branch") or frappe.defaults.get_user_default("Branch") or "",
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
		items = [deepcopy(item) for item in group["items"] if _can_open_target(item)]
		if not items:
			continue
		groups.append({"key": group["key"], "label": _(group["label"]), "items": items})
	return groups


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
		return bool(frappe.db.exists(target_type, target))
	return False


def _doctype_exists(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def _has_permission(doctype: str, permission_type: str) -> bool:
	try:
		return bool(frappe.has_permission(doctype, permission_type))
	except Exception:
		return False
