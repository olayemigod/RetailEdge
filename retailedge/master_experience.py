from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe

from retailedge.company_profile import resolve_company_profile
from retailedge.edgesuite_ui import get_retailedge_business_hub_context as _base_business_hub_context
from retailedge.operating_context import get_allowed_operating_branches, get_operating_context

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

COMPANY_PROFILE_ITEM: dict[str, Any] = {
	"label": "Company Profile",
	"description": "Maintain the active ERPNext Company identity, logo and business contact profile used across ProcessEdge Retail.",
	"target_type": "Page",
	"target": "company-profile",
	"icon": "building",
}

BRANCH_ASSIGNMENTS_ITEM: dict[str, Any] = {
	"label": "Branch Assignments",
	"description": "Assign users to operational Branches and preserve effective-dated transfer history.",
	"target_type": "Page",
	"target": "branch-assignments",
	"icon": "users",
}

TRANSACTION_WORKSPACE_ITEM: dict[str, Any] = {
	"label": "Transaction Workspace",
	"description": "Start sales, purchasing, stock and POS work inside the ProcessEdge Retail operating shell.",
	"target_type": "Page",
	"target": "transaction-workspace",
	"icon": "shopping-cart",
}

MAKE_SALE_ITEM: dict[str, Any] = {
	"label": "Make Sale",
	"description": "Create larger or multi-item Sales Invoices in a resilient full-page workspace.",
	"target_type": "Page",
	"target": "make-sale",
	"icon": "shopping-cart",
}

RECORD_PURCHASE_ITEM: dict[str, Any] = {
	"label": "Record Purchase",
	"description": "Create larger or multi-item Purchase Invoices in a resilient full-page workspace.",
	"target_type": "Page",
	"target": "record-purchase",
	"icon": "shopping-bag",
}

TRANSFER_STOCK_ITEM: dict[str, Any] = {
	"label": "Transfer Stock",
	"description": "Move larger item sets between permitted Stock Locations in a resilient full-page workspace.",
	"target_type": "Page",
	"target": "transfer-stock",
	"icon": "repeat",
}

STOCK_ADJUSTMENT_ITEM: dict[str, Any] = {
	"label": "Stock Adjustment",
	"description": "Record larger physical stock counts in a resilient full-page workspace.",
	"target_type": "Page",
	"target": "stock-adjustment",
	"icon": "clipboard",
}

PROFESSIONAL_SELLING_ITEM: dict[str, Any] = {
	"label": "Professional Selling",
	"description": "Prepare Quotations, Sales Orders and Delivery Notes in one guided selling flow.",
	"target_type": "Page",
	"target": "professional-selling",
	"icon": "shopping-bag",
}

SELLING_NATIVE_PEER_DOCTYPES = {"Sales Invoice", "Sales Order", "Delivery Note"}

PROFESSIONAL_PURCHASING_ITEM: dict[str, Any] = {
	"label": "Professional Purchasing",
	"description": "Operate Purchase Orders and prepare draft Purchase Receipts through ERPNext buying truth.",
	"target_type": "Page",
	"target": "professional-purchasing",
	"icon": "shopping-bag",
}

PURCHASE_ORDER_NATIVE_PEER_DOCTYPE = "Purchase Order"
PURCHASE_REGISTER_PAGE_TARGET = "purchase-register"
PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE = "Purchase Invoice"
EXPENSE_REGISTER_PAGE_TARGET = "expense-register"
CASHIER_EXPENSE_NATIVE_PEER_DOCTYPE = "RetailEdge Cashier Expense"
STOCK_MOVEMENT_HISTORY_REPORT_TARGET = "RetailEdge Stock Movement History"
STOCK_MOVEMENT_HISTORY_PAGE_TARGET = "stock-movement-history"

BUSINESS_EXPENSE_ITEM: dict[str, Any] = {
	"label": "Business Expenses",
	"description": "Record and review non-POS business spending with evidence and workflow controls.",
	"target_type": "Page",
	"target": "business-expenses",
	"icon": "credit-card",
}
BUSINESS_EXPENSE_NATIVE_PEER_DOCTYPE = "RetailEdge Business Expense"
EXPENSE_CATEGORY_NATIVE_PEER_DOCTYPE = "RetailEdge Expense Category"

BUSINESS_EXPENSE_QUICK_ACTION: dict[str, Any] = {
	"key": "record-expense",
	"label": "Record Expense",
	"description": "Record a non-POS business expense with evidence, approval and accounting controls.",
	"doctype": BUSINESS_EXPENSE_NATIVE_PEER_DOCTYPE,
	"icon": "credit-card",
	"experience": "act",
	"mode": "page",
	"target_type": "Page",
	"target": "business-expenses",
}

PRICING_PROMOTIONS_PAGE_TARGET = "pricing-promotions-control"
PRICING_PROMOTIONS_NATIVE_PEERS = {
	"Price List",
	"Item Price",
	"Pricing Rule",
	"Promotional Scheme",
	"Coupon Code",
	"Loyalty Program",
}


DOCUMENT_OUTPUT_ITEM: dict[str, Any] = {
	"label": "Document Output & Sharing",
	"description": "Print, download and share customer documents using ERPNext Print Formats and permissions.",
	"target_type": "Page",
	"target": "document-output-sharing",
	"icon": "share-2",
}

PAYMENT_MANAGEMENT_ITEM: dict[str, Any] = {
	"label": "Payment Management",
	"description": "Record customer advances, review unapplied receipts and apply advances through ERPNext reconciliation.",
	"target_type": "Page",
	"target": "payment-management",
	"icon": "wallet",
}

CUSTOMER_ADVANCE_REPORT_ITEM: dict[str, Any] = {
	"label": "Customer Advance Register",
	"description": "Review current unapplied customer receipts, allocated portions and available advance balances.",
	"target_type": "Report",
	"target": "RetailEdge Customer Advance Register",
	"icon": "report",
}

BANKING_READINESS_ITEM: dict[str, Any] = {
	"label": "Banking Setup & Readiness",
	"description": "Review permitted Bank Accounts, branch attribution and matching readiness before reconciliation work.",
	"target_type": "Page",
	"target": "banking-readiness",
	"icon": "shield-check",
}

PROJECT_OPERATIONS_ITEM: dict[str, Any] = {
	"label": "Project Operations",
	"description": "Manage project progress, funds, receipts and linked ERPNext transactions from one operational view.",
	"target_type": "Page",
	"target": "project-operations",
	"icon": "briefcase",
}

PROJECT_PORTFOLIO_REPORT_ITEM: dict[str, Any] = {
	"label": "Project Portfolio",
	"description": "Review project billing, project-linked cash, cost, margin and completion across the permitted portfolio.",
	"target_type": "Report",
	"target": "RetailEdge Project Portfolio",
	"icon": "report",
}

PROJECT_FINANCIAL_CONTROL_REPORT_ITEM: dict[str, Any] = {
	"label": "Project Financial Control",
	"description": "Control project budget, billing, receivables, payables, project-linked cash, cost and margin from ERPNext truth.",
	"target_type": "Report",
	"target": "RetailEdge Project Financial Control",
	"icon": "report",
}

PROJECT_LIST_ITEM: dict[str, Any] = {
	"label": "Projects",
	"description": "Open the native ERPNext Project list and full project forms.",
	"target_type": "DocType",
	"target": "Project",
	"icon": "briefcase",
}

REPORTS_CENTRE_ITEM: dict[str, Any] = {
	"label": "Reports Centre",
	"description": "Find permitted operational, management and financial reports from one place.",
	"target_type": "Page",
	"target": "reports-centre",
	"icon": "report",
}


SETUP_HUB_ITEM: dict[str, Any] = {
	"label": "Setup",
	"description": "Configure ProcessEdge Retail business rules, Branch Setup, payment masters and statement mappings.",
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
	"""Promote the R4 pages already accepted into final RetailEdge composition.

	Stock Movement History is promoted separately by _promote_stock_movement_history()
	because its hardened Page now owns the 1.0 everyday experience when permitted.
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
		if not frappe.db.exists("Page", target):
			return False
		return bool(frappe.get_doc("Page", target).is_permitted())
	except Exception:
		return False


def _can_open_report(target: str) -> bool:
	try:
		return bool(frappe.db.exists("Report", target) and frappe.has_permission("Report", "read", doc=target))
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


def _add_company_profile_navigation(navigation_groups: list[dict[str, Any]]) -> None:
	if not _can_open_page(COMPANY_PROFILE_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "home":
			continue
		items = list(group.get("items") or [])
		if any(item.get("target") == COMPANY_PROFILE_ITEM["target"] for item in items):
			return
		operating_index = next(
			(index for index, item in enumerate(items) if item.get("target") == OPERATING_CONTEXT_ITEM["target"]),
			-1,
		)
		items.insert(operating_index + 1 if operating_index >= 0 else 0, deepcopy(COMPANY_PROFILE_ITEM))
		group["items"] = items
		return


def _add_branch_assignment_navigation(navigation_groups: list[dict[str, Any]]) -> None:
	if not _can_open_page(BRANCH_ASSIGNMENTS_ITEM["target"]):
		return

	setup_group = next((group for group in navigation_groups if group.get("key") == "setup"), None)
	if setup_group is None:
		setup_group = {
			"key": "setup",
			"label": "Setup",
			"icon": "settings",
			"items": [],
		}
		navigation_groups.append(setup_group)

	items = list(setup_group.get("items") or [])
	if any(item.get("target") == BRANCH_ASSIGNMENTS_ITEM["target"] for item in items):
		return

	branch_setup_index = next(
		(index for index, item in enumerate(items) if item.get("target") == "RetailEdge Branch Profile"),
		-1,
	)
	items.insert(branch_setup_index + 1 if branch_setup_index >= 0 else 0, deepcopy(BRANCH_ASSIGNMENTS_ITEM))
	setup_group["items"] = items


def _promote_transaction_workspace(navigation_groups: list[dict[str, Any]]) -> None:
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


def _promote_make_sale(navigation_groups: list[dict[str, Any]]) -> None:
	"""Expose the full-page Sales Invoice entry workspace when create access exists."""
	if not _can_open_page(MAKE_SALE_ITEM["target"]):
		return
	try:
		if not frappe.db.exists("DocType", "Sales Invoice") or not frappe.has_permission("Sales Invoice", "create"):
			return
	except Exception:
		return
	sell_group = next((group for group in navigation_groups if group.get("key") == "sell"), None)
	if sell_group is None:
		sell_group = {"key": "sell", "label": "Sell", "icon": "shopping-cart", "items": []}
		home_index = next((index for index, group in enumerate(navigation_groups) if group.get("key") == "home"), -1)
		navigation_groups.insert(home_index + 1 if home_index >= 0 else 0, sell_group)
	items = list(sell_group.get("items") or [])
	if any(item.get("target_type") == "Page" and item.get("target") == MAKE_SALE_ITEM["target"] for item in items):
		return
	workspace_index = next(
		(index for index, item in enumerate(items) if item.get("target") == TRANSACTION_WORKSPACE_ITEM["target"]),
		-1,
	)
	items.insert(workspace_index + 1 if workspace_index >= 0 else 0, deepcopy(MAKE_SALE_ITEM))
	sell_group["items"] = items


def _promote_long_transaction_pages(navigation_groups: list[dict[str, Any]]) -> None:
	"""Expose full-page entry owners while keeping quick-entry actions separate."""
	specs = (
		("buy", RECORD_PURCHASE_ITEM, "Purchase Invoice"),
		("stock", TRANSFER_STOCK_ITEM, "Stock Entry"),
		("stock", STOCK_ADJUSTMENT_ITEM, "Stock Reconciliation"),
	)
	for group_key, page_item, doctype in specs:
		if not _can_open_page(page_item["target"]):
			continue
		try:
			if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "create"):
				continue
		except Exception:
			continue
		group = next((row for row in navigation_groups if row.get("key") == group_key), None)
		if group is None:
			group_meta = {
				"buy": {"label": "Buy", "icon": "shopping-bag"},
				"stock": {"label": "Stock", "icon": "layers"},
			}[group_key]
			group = {"key": group_key, **group_meta, "items": []}
			insert_at = next(
				(index for index, row in enumerate(navigation_groups) if row.get("key") in {"money", "operations", "insights", "reports", "setup"}),
				len(navigation_groups),
			)
			navigation_groups.insert(insert_at, group)
		items = list(group.get("items") or [])
		if any(item.get("target_type") == "Page" and item.get("target") == page_item["target"] for item in items):
			continue
		items.insert(0, deepcopy(page_item))
		group["items"] = items


def _promote_professional_selling(navigation_groups: list[dict[str, Any]]) -> None:
	"""Make Professional Selling the everyday owner of supported selling documents.

	The base registry keeps native ERPNext DocTypes as compatibility fallbacks. Once
	Professional Selling is permission-available, final RetailEdge composition removes
	those peer routes so normal navigation is EdgeSuite-first. ERPNext permissions and
	Native Desk remain unchanged for deliberate advanced use.
	"""
	if not _can_open_page(PROFESSIONAL_SELLING_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "sell":
			continue
		items = list(group.get("items") or [])
		existing_page = next(
			(
				item
				for item in items
				if item.get("target_type") == "Page" and item.get("target") == PROFESSIONAL_SELLING_ITEM["target"]
			),
			None,
		)
		items = [
			item
			for item in items
			if not (
				item.get("target_type") == "DocType"
				and item.get("target") in SELLING_NATIVE_PEER_DOCTYPES
			)
			and not (
				item.get("target_type") == "Page"
				and item.get("target") == PROFESSIONAL_SELLING_ITEM["target"]
			)
		]
		workspace_index = next(
			(index for index, item in enumerate(items) if item.get("target") == TRANSACTION_WORKSPACE_ITEM["target"]),
			-1,
		)
		items.insert(
			workspace_index + 1 if workspace_index >= 0 else 0,
			deepcopy(existing_page or PROFESSIONAL_SELLING_ITEM),
		)
		group["items"] = items
		return


def _promote_pricing_promotions_ownership(navigation_groups: list[dict[str, Any]]) -> None:
	"""Use the Pricing & Promotions Page as the everyday owner of pricing masters."""
	if not _can_open_page(PRICING_PROMOTIONS_PAGE_TARGET):
		return
	for group in navigation_groups:
		if group.get("key") != "pricing-promotions":
			continue
		items = list(group.get("items") or [])
		page_item = next(
			(
				item
				for item in items
				if item.get("target_type") == "Page"
				and item.get("target") == PRICING_PROMOTIONS_PAGE_TARGET
			),
			None,
		)
		if page_item is None:
			return
		group["items"] = [
			page_item,
			*[
				item
				for item in items
				if not (
					item.get("target_type") == "DocType"
					and item.get("target") in PRICING_PROMOTIONS_NATIVE_PEERS
				)
				and item is not page_item
			],
		]
		return


def _promote_professional_purchasing(navigation_groups: list[dict[str, Any]]) -> None:
	"""Make Professional Purchasing the everyday owner of Purchase Orders.

	The base registry retains native ERPNext Purchase Order as a compatibility fallback.
	Once the Professional Purchasing Page is permission-available, final RetailEdge
	composition removes that peer route while preserving native Purchase Receipt and
	advanced purchasing routes. ERPNext permissions and document semantics are unchanged.
	"""
	if not _can_open_page(PROFESSIONAL_PURCHASING_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "buy":
			continue
		items = list(group.get("items") or [])
		existing_page = next(
			(
				item
				for item in items
				if item.get("target_type") == "Page" and item.get("target") == PROFESSIONAL_PURCHASING_ITEM["target"]
			),
			None,
		)
		items = [
			item
			for item in items
			if not (
				item.get("target_type") == "DocType"
				and item.get("target") == PURCHASE_ORDER_NATIVE_PEER_DOCTYPE
			)
			and not (
				item.get("target_type") == "Page"
				and item.get("target") == PROFESSIONAL_PURCHASING_ITEM["target"]
			)
		]
		purchase_invoice_index = next(
			(
				index
				for index, item in enumerate(items)
				if item.get("target_type") == "DocType" and item.get("target") == PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE
			),
			0,
		)
		items.insert(purchase_invoice_index, deepcopy(existing_page or PROFESSIONAL_PURCHASING_ITEM))
		group["items"] = items
		return


def _promote_purchase_invoice_ownership(navigation_groups: list[dict[str, Any]]) -> None:
	"""Use the EdgeSuite Purchase Register as the everyday Purchase Invoice read surface.

	The native Purchase Invoice peer is removed only when the current user may open the
	Purchase Register and that Page is already present in the Buy composition. This keeps
	legacy/native compatibility fail-safe when the EdgeSuite owner is unavailable.
	"""
	if not _can_open_page(PURCHASE_REGISTER_PAGE_TARGET):
		return
	for group in navigation_groups:
		if group.get("key") != "buy":
			continue
		items = list(group.get("items") or [])
		if not any(
			item.get("target_type") == "Page" and item.get("target") == PURCHASE_REGISTER_PAGE_TARGET
			for item in items
		):
			return
		group["items"] = [
			item
			for item in items
			if not (
				item.get("target_type") == "DocType"
				and item.get("target") == PURCHASE_INVOICE_NATIVE_PEER_DOCTYPE
			)
		]
		return



def _promote_stock_movement_history(navigation_groups: list[dict[str, Any]]) -> None:
	"""Use the hardened EdgeSuite Page as the everyday Stock Movement History owner."""
	if not _can_open_page(STOCK_MOVEMENT_HISTORY_PAGE_TARGET):
		return
	for group in navigation_groups:
		if group.get("key") != "stock":
			continue
		for item in group.get("items") or []:
			if (
				item.get("target_type") == "Report"
				and item.get("target") == STOCK_MOVEMENT_HISTORY_REPORT_TARGET
			):
				item["target_type"] = "Page"
				item["target"] = STOCK_MOVEMENT_HISTORY_PAGE_TARGET
				return
		return

def _business_expenses_enabled() -> bool:
	try:
		from retailedge.business_expense import get_business_expense_settings

		return bool(get_business_expense_settings().get("enabled"))
	except Exception:
		return False


def _promote_business_expense_ownership(navigation_groups: list[dict[str, Any]]) -> None:
	page_available = _business_expenses_enabled() and _can_open_page(BUSINESS_EXPENSE_ITEM["target"])
	setup_available = _can_open_page(SETUP_HUB_ITEM["target"])
	for group in navigation_groups:
		if group.get("key") != "expenses":
			continue
		items = list(group.get("items") or [])
		if page_available:
			items = [
				item
				for item in items
				if not (
					item.get("target_type") == "DocType"
					and item.get("target") == BUSINESS_EXPENSE_NATIVE_PEER_DOCTYPE
				)
			]
			if not any(
				item.get("target_type") == "Page"
				and item.get("target") == BUSINESS_EXPENSE_ITEM["target"]
				for item in items
			):
				register_index = next(
					(index for index, item in enumerate(items) if item.get("target") == EXPENSE_REGISTER_PAGE_TARGET),
					0,
				)
				items.insert(register_index, deepcopy(BUSINESS_EXPENSE_ITEM))
		if setup_available:
			items = [
				item
				for item in items
				if not (
					item.get("target_type") == "DocType"
					and item.get("target") == EXPENSE_CATEGORY_NATIVE_PEER_DOCTYPE
				)
			]
		group["items"] = items
		return


def _promote_cashier_expense_ownership(navigation_groups: list[dict[str, Any]]) -> None:
	"""Use Expense Register as the everyday owner of RetailEdge Cashier Expense.

	The base registry keeps the DocType for compatibility. Once the permission-aware
	Expense Register Page is present, remove the raw DocType from normal navigation.
	The underlying DocType remains the system of record and Native Desk access remains
	available only through deliberate advanced paths.
	"""
	if not _can_open_page(EXPENSE_REGISTER_PAGE_TARGET):
		return
	for group in navigation_groups:
		if group.get("key") != "expenses":
			continue
		items = list(group.get("items") or [])
		if not any(
			item.get("target_type") == "Page" and item.get("target") == EXPENSE_REGISTER_PAGE_TARGET
			for item in items
		):
			return
		group["items"] = [
			item
			for item in items
			if not (
				item.get("target_type") == "DocType"
				and item.get("target") == CASHIER_EXPENSE_NATIVE_PEER_DOCTYPE
			)
		]
		return


def _promote_document_output(navigation_groups: list[dict[str, Any]]) -> None:
	if not _can_open_page(DOCUMENT_OUTPUT_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "sell":
			continue
		items = list(group.get("items") or [])
		if any(item.get("target_type") == "Page" and item.get("target") == DOCUMENT_OUTPUT_ITEM["target"] for item in items):
			return
		selling_index = next((index for index, item in enumerate(items) if item.get("target") == PROFESSIONAL_SELLING_ITEM["target"]), -1)
		items.insert(selling_index + 1 if selling_index >= 0 else 0, deepcopy(DOCUMENT_OUTPUT_ITEM))
		group["items"] = items
		return


def _promote_payment_management(navigation_groups: list[dict[str, Any]]) -> None:
	page_available = _can_open_page(PAYMENT_MANAGEMENT_ITEM["target"])
	report_available = _can_open_report(CUSTOMER_ADVANCE_REPORT_ITEM["target"])
	if not page_available and not report_available:
		return
	for group in navigation_groups:
		if group.get("key") != "money":
			continue
		items = list(group.get("items") or [])
		payment_index = next((index for index, item in enumerate(items) if item.get("target_type") == "DocType" and item.get("target") == "Payment Entry"), len(items))
		if page_available and not any(item.get("target_type") == "Page" and item.get("target") == PAYMENT_MANAGEMENT_ITEM["target"] for item in items):
			items.insert(payment_index, deepcopy(PAYMENT_MANAGEMENT_ITEM))
			payment_index += 1
		if report_available and not any(item.get("target_type") == "Report" and item.get("target") == CUSTOMER_ADVANCE_REPORT_ITEM["target"] for item in items):
			items.insert(payment_index, deepcopy(CUSTOMER_ADVANCE_REPORT_ITEM))
		group["items"] = items
		return


def _promote_banking_readiness(navigation_groups: list[dict[str, Any]]) -> None:
	"""Expose the hardened readiness Page only when the current reader may open it."""
	if not _can_open_page(BANKING_READINESS_ITEM["target"]):
		return
	for group in navigation_groups:
		if group.get("key") != "money":
			continue
		items = list(group.get("items") or [])
		if any(
			item.get("target_type") == "Page" and item.get("target") == BANKING_READINESS_ITEM["target"]
			for item in items
		):
			return
		bank_matching_index = next(
			(index for index, item in enumerate(items) if item.get("target") == "bank-matching-reconciliation"),
			len(items),
		)
		items.insert(bank_matching_index, deepcopy(BANKING_READINESS_ITEM))
		group["items"] = items
		return


def _promote_project_operations(navigation_groups: list[dict[str, Any]]) -> None:
	page_available = _can_open_page(PROJECT_OPERATIONS_ITEM["target"])
	portfolio_available = _can_open_report(PROJECT_PORTFOLIO_REPORT_ITEM["target"])
	financial_control_available = _can_open_report(PROJECT_FINANCIAL_CONTROL_REPORT_ITEM["target"])
	if not page_available and not portfolio_available and not financial_control_available:
		return
	existing_group = next((group for group in navigation_groups if group.get("key") == "projects"), None)
	if existing_group is not None:
		items = list(existing_group.get("items") or [])
	else:
		items = []

	if page_available and not any(item.get("target") == PROJECT_OPERATIONS_ITEM["target"] for item in items):
		items.append(deepcopy(PROJECT_OPERATIONS_ITEM))
	if portfolio_available and not any(item.get("target") == PROJECT_PORTFOLIO_REPORT_ITEM["target"] for item in items):
		items.append(deepcopy(PROJECT_PORTFOLIO_REPORT_ITEM))
	if financial_control_available and not any(item.get("target") == PROJECT_FINANCIAL_CONTROL_REPORT_ITEM["target"] for item in items):
		items.append(deepcopy(PROJECT_FINANCIAL_CONTROL_REPORT_ITEM))
	try:
		if frappe.db.exists("DocType", "Project") and frappe.has_permission("Project", "read") and not any(item.get("target_type") == "DocType" and item.get("target") == "Project" for item in items):
			items.append(deepcopy(PROJECT_LIST_ITEM))
	except Exception:
		pass

	if existing_group is not None:
		existing_group["items"] = items
		return
	project_group = {"key": "projects", "label": "Projects", "icon": "briefcase", "items": items}
	insert_at = next((index for index, group in enumerate(navigation_groups) if group.get("key") == "insights"), len(navigation_groups))
	navigation_groups.insert(insert_at, project_group)


def _promote_reports_centre(navigation_groups: list[dict[str, Any]]) -> None:
	if not _can_open_page(REPORTS_CENTRE_ITEM["target"]):
		return

	existing_group = next(
		(group for group in navigation_groups if group.get("key") == "reports"),
		None,
	)
	if existing_group is not None:
		items = list(existing_group.get("items") or [])
		if not any(item.get("target") == REPORTS_CENTRE_ITEM["target"] for item in items):
			items.insert(0, deepcopy(REPORTS_CENTRE_ITEM))
			existing_group["items"] = items
		return

	report_group = {
		"key": "reports",
		"label": "Reports",
		"icon": "report",
		"items": [deepcopy(REPORTS_CENTRE_ITEM)],
	}
	insert_at = next(
		(
			index
			for index, group in enumerate(navigation_groups)
			if group.get("key") == "insights"
		),
		len(navigation_groups),
	)
	navigation_groups.insert(insert_at, report_group)

def _consolidate_setup_navigation(navigation_groups: list[dict[str, Any]]) -> None:
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


def _contain_native_navigation_for_edgesuite_only(context: dict[str, Any]) -> None:
	"""Remove native Desk routes from final ordinary-user composition.

	The base registry already applies permission and access filtering. This final sweep
	protects against native DocType/Report routes appended by later master promotions.
	It changes presentation only; underlying Frappe permissions and native routes remain.
	"""
	access = dict(context.get("access") or {})
	if bool(access.get("can_use_native_desk")):
		return

	contained_groups: list[dict[str, Any]] = []
	for group in context.get("navigation_groups") or []:
		items = [
			item
			for item in list(group.get("items") or [])
			if item.get("target_type") not in {"DocType", "Report"}
		]
		if not items:
			continue
		group["items"] = items
		contained_groups.append(group)
	context["navigation_groups"] = contained_groups


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	context = deepcopy(_base_business_hub_context() or {})
	navigation_groups = context.get("navigation_groups") or []
	_promote_browser_approved_r4_pages(navigation_groups)
	_add_operating_context_navigation(navigation_groups)
	_add_company_profile_navigation(navigation_groups)
	_add_branch_assignment_navigation(navigation_groups)
	_promote_transaction_workspace(navigation_groups)
	_promote_make_sale(navigation_groups)
	_promote_long_transaction_pages(navigation_groups)
	_promote_professional_selling(navigation_groups)
	_promote_pricing_promotions_ownership(navigation_groups)
	_promote_professional_purchasing(navigation_groups)
	_promote_purchase_invoice_ownership(navigation_groups)
	_promote_stock_movement_history(navigation_groups)
	_promote_business_expense_ownership(navigation_groups)
	_promote_cashier_expense_ownership(navigation_groups)
	_promote_document_output(navigation_groups)
	_promote_payment_management(navigation_groups)
	_promote_banking_readiness(navigation_groups)
	_promote_project_operations(navigation_groups)
	_promote_reports_centre(navigation_groups)
	_consolidate_setup_navigation(navigation_groups)
	_contain_native_navigation_for_edgesuite_only(context)

	quick_actions = list(context.get("quick_actions") or [])
	if (
		_business_expenses_enabled()
		and _can_open_page(BUSINESS_EXPENSE_ITEM["target"])
		and frappe.db.exists("DocType", BUSINESS_EXPENSE_NATIVE_PEER_DOCTYPE)
		and frappe.has_permission(BUSINESS_EXPENSE_NATIVE_PEER_DOCTYPE, "create")
	):
		quick_actions = [
			deepcopy(BUSINESS_EXPENSE_QUICK_ACTION)
			if action.get("key") == "record-expense"
			else action
			for action in quick_actions
		]

	existing_keys = {action.get("key") for action in quick_actions}
	for action in MASTER_ACTIONS:
		if action["key"] in existing_keys or not _can_create_master(action["doctype"]):
			continue
		quick_actions.append(deepcopy(action))
		existing_keys.add(action["key"])
	context["quick_actions"] = quick_actions

	operating = get_operating_context()
	company = operating.get("company") or ""
	identity = resolve_company_profile(company)
	try:
		branches = get_allowed_operating_branches(company=company) if company else []
	except Exception:
		branches = []
	user_context = dict(context.get("context") or {})
	user_context.update({
		"company": operating.get("company") or "",
		"company_label": identity.get("label") or company,
		"company_logo": identity.get("logo") or "",
		"company_currency": identity.get("currency") or "",
		"company_profile": identity,
		"branch": operating.get("branch") or "",
		"branch_options": list(branches),
		"can_switch_branch": len(branches) > 1,
		"operating_context_source": operating.get("source") or "",
		"default_pos_profile": operating.get("default_pos_profile") or "",
		"default_stock_location": operating.get("default_stock_location") or "",
	})
	context["context"] = user_context

	feature_flags = dict(context.get("feature_flags") or {})
	feature_flags["simple_master_data_stage"] = "customer_supplier_item"
	feature_flags["r4_browser_promoted_pages"] = sorted(PROMOTED_R4_PAGE_TARGETS.values())
	feature_flags["operating_branch_context"] = "phase2_active"
	feature_flags["setup_route_consolidation"] = "edgesuite_setup"
	feature_flags["transaction_workspace"] = "edgesuite_host"
	feature_flags["make_sale"] = "full_page_with_quick_sale_companion"
	feature_flags["record_purchase"] = "full_page_with_quick_purchase_companion"
	feature_flags["transfer_stock"] = "full_page_with_quick_transfer_companion"
	feature_flags["stock_adjustment"] = "full_page_with_quick_adjustment_companion"
	feature_flags["professional_selling"] = "edgesuite_primary"
	feature_flags["pricing_promotions_ownership"] = "application_workspace"
	feature_flags["professional_purchasing"] = "edgesuite_primary_purchase_order"
	feature_flags["purchase_invoice_ownership"] = "edgesuite_purchase_register"
	feature_flags["stock_movement_history_ownership"] = "edgesuite_page"
	feature_flags["cashier_expense_ownership"] = "edgesuite_expense_register"
	feature_flags["business_expense_ownership"] = "edgesuite_business_expenses"
	feature_flags["document_output_sharing"] = "erpnext_native_output"
	feature_flags["advanced_payment_management"] = "erpnext_native_reconciliation"
	feature_flags["customer_advance_reporting"] = "current_open_receipts"
	feature_flags["banking_readiness"] = "permission_scoped_inventory"
	feature_flags["project_operations"] = "erpnext_native_project_funds"
	feature_flags["project_portfolio_reporting"] = "erpnext_project_plus_payment_entries"
	feature_flags["project_financial_control"] = "whole_project_erpnext_financial_control"
	feature_flags["reports_centre"] = "permission_filtered_catalogue"
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