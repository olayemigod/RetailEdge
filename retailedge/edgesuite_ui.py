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

FINANCE_TRANSFER_ROLES = {"Accounts User", "Accounts Manager", "System Manager"}
CASH_FLOW_OUTLOOK_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
	"Accounts Manager",
	"Accounts User",
}
STOCK_ACCOUNTING_INTEGRITY_ROLES = {"System Manager", "Stock User", "Accounts Manager"}
SUPPLIER_DOCUMENT_REVIEW_ROLES = {
	"System Manager",
	"Purchase Manager",
	"Purchase User",
	"Accounts Manager",
	"Accounts User",
}
ACTION_CENTER_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
	"Accounts Manager",
	"Accounts User",
	"Stock Manager",
	"Sales Manager",
	"Purchase Manager",
}

PROGRAMME_EXPERIENCES: tuple[dict[str, Any], ...] = (
	{
		"key": "navigate",
		"label": "Navigate",
		"description": "Professional, role-aware access to workspaces, transactions, reports, and setup.",
		"icon": "grid",
		"status": "In Progress",
	},
	{
		"key": "act",
		"label": "Act",
		"description": "Quick, permission-aware guided entries that create native ERPNext documents while keeping full-form fallbacks available.",
		"icon": "zap",
		"status": "In Progress",
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
		"icon": "home",
		"items": ({"label": "Business Hub", "target_type": "Page", "target": "retailedge-business-hub", "icon": "home"},),
	},
	{
		"key": "sell",
		"label": "Sell",
		"icon": "shopping-cart",
		"items": (
			{"label": START_POS_LABEL, "target_type": "URL", "target": POSNEXT_POS_URL, "runtime_target": "pos", "icon": "grid"},
			{"label": "Sales Invoices", "target_type": "DocType", "target": "Sales Invoice", "icon": "clipboard"},
			{"label": "Sales Orders", "target_type": "DocType", "target": "Sales Order", "icon": "clipboard"},
			{"label": "Delivery Notes", "target_type": "DocType", "target": "Delivery Note", "icon": "truck"},
			{"label": "Sales People", "target_type": "DocType", "target": "Sales Person", "icon": "user"},
			{"label": "Sales Partners", "target_type": "DocType", "target": "Sales Partner", "icon": "users"},
			{"label": "Sales Person Commissions", "target_type": "Report", "target": "Sales Person Commission Summary", "icon": "report"},
			{"label": "Sales Partner Commissions", "target_type": "Report", "target": "Sales Partner Commission Summary", "icon": "report"},
			{"label": "Sales Person Targets", "target_type": "Report", "target": "Sales Person Target Variance Based On Item Group", "icon": "chart"},
			{"label": "Sales Partner Targets", "target_type": "Report", "target": "Sales Partner Target Variance based on Item Group", "icon": "chart"},
			{"label": "POS Opening", "target_type": "DocType", "target": ERPNEXT_POS_OPENING_ENTRY, "runtime_target": "pos_opening", "icon": "calendar"},
			{"label": "POS Closing", "target_type": "DocType", "target": ERPNEXT_POS_CLOSING_ENTRY, "runtime_target": "pos_closing", "icon": "calendar"},
		),
	},
	{
		"key": "pricing-promotions", "label": "Pricing & Promotions", "icon": "tag", "items": (
			{"label": "Price Lists", "target_type": "DocType", "target": "Price List", "icon": "tag"},
			{"label": "Item Prices", "target_type": "DocType", "target": "Item Price", "icon": "tag"},
			{"label": "Pricing Rules", "target_type": "DocType", "target": "Pricing Rule", "icon": "settings"},
			{"label": "Promotional Schemes", "target_type": "DocType", "target": "Promotional Scheme", "icon": "gift"},
			{"label": "Coupon Codes", "target_type": "DocType", "target": "Coupon Code", "icon": "tag"},
			{"label": "Loyalty Programs", "target_type": "DocType", "target": "Loyalty Program", "icon": "gift"},
		),
	},
	{
		"key": "buy",
		"label": "Buy",
		"icon": "shopping-bag",
		"items": (
			{"label": "Purchase Invoices", "target_type": "DocType", "target": "Purchase Invoice", "icon": "clipboard"},
			{"label": "Purchase Register", "target_type": "Page", "target": "purchase-register", "icon": "report"},
			{"label": "Purchase Orders", "target_type": "DocType", "target": "Purchase Order", "icon": "clipboard"},
			{"label": "Purchase Receipts", "target_type": "DocType", "target": "Purchase Receipt", "icon": "truck"},
		),
	},
	{
		"key": "stock", "label": "Stock", "icon": "layers", "items": (
			{"label": "Products", "target_type": "DocType", "target": "Item", "icon": "layers"},
			{"label": "Stock Locations", "target_type": "DocType", "target": "Warehouse", "icon": "building"},
			{"label": "Batches", "target_type": "DocType", "target": "Batch", "icon": "layers"},
			{"label": "Serial Numbers", "target_type": "DocType", "target": "Serial No", "icon": "clipboard"},
			{"label": "Stock Movement History", "target_type": "Report", "target": "RetailEdge Stock Movement History", "icon": "report"},
			{"label": "Stock Position", "target_type": "Page", "target": "stock-position", "icon": "report"},
			{"label": "Stock & Accounting Integrity", "target_type": "Page", "target": "stock-accounting-integrity", "icon": "shield", "required_roles": tuple(sorted(STOCK_ACCOUNTING_INTEGRITY_ROLES))},
			{"label": "Stock Balance", "target_type": "Report", "target": "Stock Balance", "icon": "report"},
			{"label": "Stock Transfers", "target_type": "DocType", "target": "Stock Entry", "icon": "repeat"},
			{"label": "Stock Count", "target_type": "DocType", "target": "Stock Reconciliation", "icon": "clipboard"},
			{"label": "Reorder Requests", "target_type": "DocType", "target": "Material Request", "icon": "clipboard"},
			{"label": "Stock Ledger", "target_type": "Report", "target": "Stock Ledger", "icon": "report"},
			{"label": "Projected Stock", "target_type": "Report", "target": "Stock Projected Qty", "icon": "report"},
			{"label": "Stock Ageing", "target_type": "Report", "target": "Stock Ageing", "icon": "report"},
		),
	},
	{
		"key": "assets", "label": "Assets", "icon": "briefcase", "items": (
			{"label": "Fixed Assets", "target_type": "DocType", "target": "Asset", "icon": "briefcase"},
			{"label": "Asset Categories", "target_type": "DocType", "target": "Asset Category", "icon": "layers"},
		),
	},
	{
		"key": "money", "label": "Money", "icon": "wallet", "items": (
			{"label": "Cash Movement", "target_type": "Page", "target": "cash-movement", "icon": "report"},
			{"label": "Cash Flow Outlook", "target_type": "Page", "target": "cash-flow-outlook", "icon": "chart", "required_roles": tuple(sorted(CASH_FLOW_OUTLOOK_ROLES))},
			{"label": "Payments", "target_type": "DocType", "target": "Payment Entry", "icon": "wallet"},
			{"label": "Payment Reconciliation", "target_type": "DocType", "target": "Payment Reconciliation", "icon": "repeat"},
			{"label": "Subscriptions", "target_type": "DocType", "target": "Subscription", "icon": "repeat"},
			{"label": "Subscription Plans", "target_type": "DocType", "target": "Subscription Plan", "icon": "clipboard"},
			{"label": "Bank Transactions", "target_type": "DocType", "target": "Bank Transaction", "icon": "wallet"},
			{"label": "Import Bank Statement", "target_type": "DocType", "target": "RetailEdge Payment Statement Import", "icon": "upload"},
			{"label": "Bank Matching", "target_type": "Report", "target": "RetailEdge Bank Transaction Matching", "icon": "report"},
		),
	},
	{
		"key": "expenses", "label": "Expenses", "icon": "file-text", "items": (
			{"label": "Expense Register", "target_type": "Page", "target": "expense-register", "icon": "report"},
			{"label": "Cashier Expenses", "target_type": "DocType", "target": "RetailEdge Cashier Expense", "icon": "wallet"},
			{"label": "Expense Categories", "target_type": "DocType", "target": "RetailEdge Expense Category", "icon": "layers"},
		),
	},
	{
		"key": "customers", "label": "Customers", "icon": "users", "items": (
			{"label": "Customers", "target_type": "DocType", "target": "Customer", "icon": "user"},
			{"label": "Customer Receivables", "target_type": "Page", "target": "customer-receivables", "icon": "report"},
			{"label": "Accounts Receivable (Detailed)", "target_type": "Report", "target": "Accounts Receivable", "icon": "report"},
		),
	},
	{
		"key": "service-warranty", "label": "Service & Warranty", "icon": "tool", "items": (
			{"label": "Warranty Claims", "target_type": "DocType", "target": "Warranty Claim", "icon": "shield"},
			{"label": "Maintenance Schedules", "target_type": "DocType", "target": "Maintenance Schedule", "icon": "calendar"},
			{"label": "Maintenance Visits", "target_type": "DocType", "target": "Maintenance Visit", "icon": "tool"},
		),
	},
	{
		"key": "suppliers-payables", "label": "Suppliers & Payables", "icon": "users", "items": (
			{"label": "Suppliers", "target_type": "DocType", "target": "Supplier", "icon": "user"},
			{"label": "Supplier Payables", "target_type": "Page", "target": "supplier-payables", "icon": "report"},
			{"label": "Payment Orders", "target_type": "DocType", "target": "Payment Order", "icon": "wallet"},
			{"label": "Accounts Payable (Detailed)", "target_type": "Report", "target": "Accounts Payable", "icon": "report"},
		),
	},
	{
		"key": "insights", "label": "Insights", "icon": "chart", "items": (
			{"label": "Sales by Item", "target_type": "Page", "target": "sales-by-item", "icon": "report"},
			{"label": "Sales Invoice Register", "target_type": "Page", "target": "sales-invoice-register", "icon": "report"},
			{"label": "Salesperson Performance", "target_type": "Page", "target": "salesperson-performance-dashboard", "icon": "user"},
			{"label": "Branch Performance", "target_type": "Page", "target": "branch-performance-dashboard", "icon": "chart"},
		),
	},
	{
		"key": "review-approvals", "label": "Review & Approvals", "icon": "shield", "items": (
			{"label": "Action Centre", "target_type": "Page", "target": "action-center", "icon": "bell", "required_roles": tuple(sorted(ACTION_CENTER_ROLES))},
			{"label": "Supplier Document Review", "target_type": "Page", "target": "supplier-document-review", "icon": "clipboard", "required_roles": tuple(sorted(SUPPLIER_DOCUMENT_REVIEW_ROLES))},
			{"label": "Bank Match Reviews", "target_type": "DocType", "target": "RetailEdge Bank Transaction Match", "icon": "shield"},
			{"label": "Daily Sales Audit", "target_type": "DocType", "target": "RetailEdge Daily Sales Audit", "icon": "shield"},
			{"label": "Cashier Expense Review", "target_type": "Report", "target": "RetailEdge Cashier Expense Review", "icon": "report"},
			{"label": "Cash Shift Verification", "target_type": "Report", "target": "RetailEdge Cash Shift Verification", "icon": "report"},
			{"label": "Invoice Payment Audit", "target_type": "Report", "target": "RetailEdge Invoice Payment Audit", "icon": "report"},
			{"label": "POS Closing Variance vs Expenses", "target_type": "Report", "target": "POS Closing Variance vs Expenses", "icon": "report"},
			{"label": "Unmatched Bank Transactions", "target_type": "Report", "target": "RetailEdge Unmatched Bank Transactions", "icon": "report"},
			{"label": "Unmatched Bank Payments", "target_type": "Report", "target": "RetailEdge Unmatched Bank Payment Events", "icon": "report"},
			{"label": "Reconciliation Readiness", "target_type": "Report", "target": "RetailEdge Bank Match Reconciliation Readiness", "icon": "shield"},
			{"label": "Reconciliation Handoff", "target_type": "Report", "target": "RetailEdge Reconciliation Handoff", "icon": "report"},
			{"label": "Daily Sales Audit Register", "target_type": "Report", "target": "RetailEdge Daily Sales Audit Register", "icon": "report"},
		),
	},
	{
		"key": "accounting", "label": "Accounting", "icon": "book-open", "required_roles": ("Accounts User", "Accounts Manager", "System Manager"), "items": (
			{"label": "General Ledger", "target_type": "Report", "target": "General Ledger", "icon": "report"},
			{"label": "Trial Balance", "target_type": "Report", "target": "Trial Balance", "icon": "report"},
			{"label": "Profit & Loss", "target_type": "Report", "target": "Profit and Loss Statement", "icon": "report"},
			{"label": "Balance Sheet", "target_type": "Report", "target": "Balance Sheet", "icon": "report"},
			{"label": "Cash Flow Statement", "target_type": "Report", "target": "Cash Flow", "icon": "report"},
			{"label": "Budgets", "target_type": "DocType", "target": "Budget", "icon": "chart"},
			{"label": "Budget Variance", "target_type": "Report", "target": "Budget Variance Report", "icon": "report"},
			{"label": "Cost Centers", "target_type": "DocType", "target": "Cost Center", "icon": "layers"},
			{"label": "Journal Entries", "target_type": "DocType", "target": "Journal Entry", "icon": "clipboard"},
		),
	},
	{
		"key": "setup", "label": "Setup", "icon": "settings", "required_roles": ("System Manager",), "items": (
			{"label": "Settings", "target_type": "DocType", "target": "RetailEdge Settings", "icon": "settings"},
			{"label": "Branch Setup", "target_type": "DocType", "target": "RetailEdge Branch Profile", "icon": "building"},
			{"label": "Bank Accounts", "target_type": "DocType", "target": "Bank Account", "icon": "wallet"},
			{"label": "Modes of Payment", "target_type": "DocType", "target": "Mode of Payment", "icon": "wallet"},
			{"label": "Bank Statement Mapping", "target_type": "DocType", "target": "RetailEdge Statement Mapping Template", "icon": "settings"},
		),
	},
)

QUICK_ACTIONS: tuple[dict[str, Any], ...] = (
	{
		"key": "new-sales-invoice", "label": "New Sales Invoice", "description": "Create a formal cash, credit, wholesale, or account-customer invoice.", "doctype": "Sales Invoice", "icon": "file-text", "experience": "act", "mode": "available",
	},
	{
		"key": "receive-customer-payment", "label": "Receive Customer Payment", "description": "Record and allocate money received from a customer.", "doctype": "Payment Entry", "icon": "download", "experience": "act", "mode": "available",
	},
	{
		"key": "pay-supplier", "label": "Pay Supplier", "description": "Record a supplier payment and allocate outstanding invoices.", "doctype": "Payment Entry", "icon": "upload", "experience": "act", "mode": "available",
	},
	{
		"key": "deposit-cash", "label": "Deposit Cash", "description": "Deposit available cashier shift cash to an approved company bank account.", "doctype": "Payment Entry", "icon": "upload", "experience": "act", "mode": "available", "cashier_deposit": True,
	},
	{
		"key": "cash-transfer", "label": "Cash / Bank Transfer", "description": "Move money between permitted Cash and Bank accounts using an ERPNext internal-transfer draft.", "doctype": "Payment Entry", "icon": "repeat", "experience": "act", "mode": "available", "required_roles": tuple(sorted(FINANCE_TRANSFER_ROLES)),
	},
	{
		"key": "record-expense", "label": "Record Cashier Expense", "description": "Record a controlled expense arising during an open cashier shift.", "doctype": "RetailEdge Cashier Expense", "icon": "credit-card", "experience": "act", "mode": "available",
	},
	{
		"key": "record-purchase", "label": "Record Purchase", "description": "Create a purchase invoice for stock, services, or operating expenses.", "doctype": "Purchase Invoice", "icon": "shopping-bag", "experience": "act", "mode": "available",
	},
	{
		"key": "new-warranty-claim", "label": "New Warranty Claim", "description": "Open an unsaved native ERPNext warranty claim for a customer item or serial number.", "doctype": "Warranty Claim", "icon": "tool", "experience": "act", "mode": "native_fallback",
	},
	{
		"key": "transfer-stock", "label": "Transfer Stock", "description": "Move stock between permitted stock locations using a native Stock Entry.", "doctype": "Stock Entry", "icon": "repeat", "experience": "act", "mode": "available",
	},
	{
		"key": "adjust-stock", "label": "Stock Adjustment", "description": "Record a physical stock count using a native Stock Reconciliation draft.", "doctype": "Stock Reconciliation", "icon": "clipboard", "experience": "act", "mode": "available",
	},
)


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	roles = set(frappe.get_roles(frappe.session.user))
	target_cache: dict[tuple[str, str], bool] = {}
	permission_cache: dict[tuple[str, str], bool] = {}
	pos_capabilities = get_pos_runtime_capabilities(
		lambda target_type, target: _target_exists_cached(target_type, target, target_cache)
	)
	navigation_groups = _get_permitted_navigation_groups(
		roles,
		target_cache=target_cache,
		permission_cache=permission_cache,
		pos_capabilities=pos_capabilities,
	)
	quick_actions = _get_permitted_quick_actions(
		roles=roles,
		target_cache=target_cache,
		permission_cache=permission_cache,
	)
	return {
		"programme_experiences": deepcopy(PROGRAMME_EXPERIENCES),
		"navigation_groups": navigation_groups,
		"quick_actions": quick_actions,
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
			"guided_entries_stage": "active",
			"native_document_fallback_enabled": True,
			"performance_profile": "r2_request_cached",
		},
	}


def _get_permitted_navigation_groups(
	roles: set[str], *, target_cache: dict[tuple[str, str], bool] | None = None,
	permission_cache: dict[tuple[str, str], bool] | None = None, pos_capabilities=None,
) -> list[dict[str, Any]]:
	target_cache = target_cache if target_cache is not None else {}
	permission_cache = permission_cache if permission_cache is not None else {}
	if pos_capabilities is None:
		pos_capabilities = get_pos_runtime_capabilities(lambda target_type, target: _target_exists_cached(target_type, target, target_cache))
	groups: list[dict[str, Any]] = []
	for group in NAVIGATION_GROUPS:
		required_roles = set(group.get("required_roles") or ())
		if required_roles and not roles.intersection(required_roles):
			continue
		items: list[dict[str, Any]] = []
		for item in group["items"]:
			item_required_roles = set(item.get("required_roles") or ())
			if item_required_roles and not roles.intersection(item_required_roles):
				continue
			resolved = _resolve_navigation_item(item, pos_capabilities=pos_capabilities)
			if resolved is not None and _can_open_target(resolved, target_cache=target_cache, permission_cache=permission_cache):
				resolved.pop("required_roles", None)
				items.append(resolved)
		if items:
			groups.append({"key": group["key"], "label": _(group["label"]), "icon": group.get("icon") or "", "items": items})
	return groups


def _resolve_navigation_item(item: dict[str, Any], *, pos_capabilities=None) -> dict[str, Any] | None:
	resolved = deepcopy(item)
	runtime_target = resolved.pop("runtime_target", None)
	if runtime_target is None:
		return resolved
	if pos_capabilities is None:
		pos_capabilities = get_pos_runtime_capabilities(_target_exists)
	if runtime_target == "pos":
		if not pos_capabilities.start_link_type or not pos_capabilities.start_target:
			return None
		resolved["target_type"] = pos_capabilities.start_link_type
		resolved["target"] = pos_capabilities.start_target
		return resolved
	if runtime_target == "pos_opening":
		if not pos_capabilities.opening_doctype:
			return None
		resolved["label"] = pos_capabilities.opening_doctype
		resolved["target_type"] = "DocType"
		resolved["target"] = pos_capabilities.opening_doctype
		return resolved
	if runtime_target == "pos_closing":
		if not pos_capabilities.closing_doctype:
			return None
		resolved["label"] = pos_capabilities.closing_doctype
		resolved["target_type"] = "DocType"
		resolved["target"] = pos_capabilities.closing_doctype
		return resolved
	return resolved


def _get_permitted_quick_actions(*, roles=None, target_cache=None, permission_cache=None) -> list[dict[str, Any]]:
	roles = set(roles if roles is not None else frappe.get_roles(frappe.session.user))
	target_cache = target_cache if target_cache is not None else {}
	permission_cache = permission_cache if permission_cache is not None else {}
	actions: list[dict[str, Any]] = []
	for action in QUICK_ACTIONS:
		doctype = action["doctype"]
		if not _doctype_exists_cached(doctype, target_cache) or not _has_permission_cached(doctype, "create", permission_cache):
			continue
		required_roles = set(action.get("required_roles") or ())
		if required_roles and not roles.intersection(required_roles):
			continue
		if action.get("cashier_deposit") and not _cashier_deposit_available():
			continue
		actions.append(deepcopy(action))
	return actions


def _cashier_deposit_available() -> bool:
	try:
		from retailedge.cashier_context import get_current_cashier_context

		context = get_current_cashier_context(user=frappe.session.user) or {}
		return bool(context.get("linked_pos_opening_shift") and context.get("payment_account"))
	except Exception:
		return False


def _can_open_target(item: dict[str, Any], *, target_cache=None, permission_cache=None) -> bool:
	target_cache = target_cache if target_cache is not None else {}
	permission_cache = permission_cache if permission_cache is not None else {}
	target_type = item["target_type"]
	target = item["target"]
	if target_type == "URL":
		return True
	if target_type == "DocType":
		return _doctype_exists_cached(target, target_cache) and _has_permission_cached(target, "read", permission_cache)
	if target_type == "Report":
		return _target_exists_cached(target_type, target, target_cache) and _can_open_report_cached(target, permission_cache)
	if target_type == "Page":
		return _target_exists_cached(target_type, target, target_cache)
	return False


def _can_open_report_cached(report_name: str, cache: dict[tuple[str, str], bool]) -> bool:
	key = (f"Report:{report_name}", "open")
	if key not in cache:
		cache[key] = _can_open_report(report_name)
	return cache[key]


def _can_open_report(report_name: str) -> bool:
	try:
		from frappe.desk.query_report import get_report_doc

		get_report_doc(report_name)
		return True
	except Exception:
		return False


def _target_exists_cached(target_type: str, target: str, cache: dict[tuple[str, str], bool]) -> bool:
	key = (target_type, target)
	if key not in cache:
		cache[key] = _target_exists(target_type, target)
	return cache[key]


def _doctype_exists_cached(doctype: str, cache: dict[tuple[str, str], bool]) -> bool:
	return _target_exists_cached("DocType", doctype, cache)


def _has_permission_cached(doctype: str, permission_type: str, cache: dict[tuple[str, str], bool]) -> bool:
	key = (doctype, permission_type)
	if key not in cache:
		cache[key] = _has_permission(doctype, permission_type)
	return cache[key]


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
