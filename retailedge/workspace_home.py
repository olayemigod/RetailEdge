from __future__ import annotations

import json
from dataclasses import dataclass, replace

import frappe

from retailedge.pos_runtime import (
	ERPNEXT_POS_CLOSING_ENTRY,
	ERPNEXT_POS_OPENING_ENTRY,
	POSNEXT_CLOSING_SHIFT,
	POSNEXT_OPENING_SHIFT,
	POSNEXT_POS_URL,
	START_POS_LABEL,
	get_pos_runtime_capabilities,
)


@dataclass(frozen=True)
class WorkspaceHomeItem:
	label: str
	link_type: str
	link_to: str
	section: str
	priority: int
	audience: str
	source: str
	color: str = "Grey"
	url: str | None = None


# Native Frappe workspace is a compact fallback. The EdgeSuite Business Hub is the
# primary shell and carries the role-aware Home and Accounting groups.
HOME_SECTIONS: tuple[str, ...] = (
	"Home",
	"Sell",
	"Buy",
	"Stock",
	"Money",
	"Expenses",
	"Customers",
	"Suppliers & Payables",
	"Insights",
	"Review & Approvals",
	"Setup",
)

HOME_WORKSPACE_ITEMS: tuple[WorkspaceHomeItem, ...] = (
	WorkspaceHomeItem("RetailEdge Business Hub", "Page", "retailedge-business-hub", "Home", 10, "all", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem(START_POS_LABEL, "URL", POSNEXT_POS_URL, "Sell", 10, "cashier", "POS Runtime", "Green", POSNEXT_POS_URL),
	WorkspaceHomeItem("POS Opening", "DocType", POSNEXT_OPENING_SHIFT, "Sell", 20, "cashier", "POS Runtime"),
	WorkspaceHomeItem("POS Closing", "DocType", POSNEXT_CLOSING_SHIFT, "Sell", 30, "cashier", "POS Runtime"),
	WorkspaceHomeItem("Sales Invoices", "DocType", "Sales Invoice", "Sell", 40, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Sales Orders", "DocType", "Sales Order", "Sell", 50, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Delivery Notes", "DocType", "Delivery Note", "Sell", 60, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Purchase Invoices", "DocType", "Purchase Invoice", "Buy", 10, "purchasing", "ERPNext Link"),
	WorkspaceHomeItem("Purchase Orders", "DocType", "Purchase Order", "Buy", 20, "purchasing", "ERPNext Link"),
	WorkspaceHomeItem("Purchase Receipts", "DocType", "Purchase Receipt", "Buy", 30, "purchasing", "ERPNext Link"),
	WorkspaceHomeItem("Products", "DocType", "Item", "Stock", 10, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Warehouses", "DocType", "Warehouse", "Stock", 20, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Movement History", "Report", "RetailEdge Stock Movement History", "Stock", 30, "stock", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Stock Balance", "Report", "Stock Balance", "Stock", 40, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Transfers", "DocType", "Stock Entry", "Stock", 50, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Count", "DocType", "Stock Reconciliation", "Stock", 60, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Reorder Requests", "DocType", "Material Request", "Stock", 70, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Ledger", "Report", "Stock Ledger", "Stock", 80, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Projected Stock", "Report", "Stock Projected Qty", "Stock", 90, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Ageing", "Report", "Stock Ageing", "Stock", 100, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Payments", "DocType", "Payment Entry", "Money", 10, "bank_ops", "ERPNext Link"),
	WorkspaceHomeItem("Bank Transactions", "DocType", "Bank Transaction", "Money", 20, "bank_ops", "ERPNext Link"),
	WorkspaceHomeItem("Import Bank Statement", "DocType", "RetailEdge Payment Statement Import", "Money", 30, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Bank Matching", "Report", "RetailEdge Bank Transaction Matching", "Money", 40, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Cashier Expenses", "DocType", "RetailEdge Cashier Expense", "Expenses", 10, "cashier", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Customers", "DocType", "Customer", "Customers", 10, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Customer Receivables", "Page", "customer-receivables", "Customers", 20, "accounts", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Accounts Receivable (Detailed)", "Report", "Accounts Receivable", "Customers", 30, "accounts", "ERPNext Link"),
	WorkspaceHomeItem("Suppliers", "DocType", "Supplier", "Suppliers & Payables", 10, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Payables", "Report", "Accounts Payable", "Suppliers & Payables", 20, "accounts", "ERPNext Link"),
	WorkspaceHomeItem("Branch Performance", "Page", "branch-performance-dashboard", "Insights", 10, "manager", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Salesperson Performance", "Page", "salesperson-performance-dashboard", "Insights", 20, "manager", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Bank Match Reviews", "DocType", "RetailEdge Bank Transaction Match", "Review & Approvals", 10, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Daily Sales Audit", "DocType", "RetailEdge Daily Sales Audit", "Review & Approvals", 20, "operations", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Cashier Expense Review", "Report", "RetailEdge Cashier Expense Review", "Review & Approvals", 30, "approver", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Cash Shift Verification", "Report", "RetailEdge Cash Shift Verification", "Review & Approvals", 40, "reviewer", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Invoice Payment Audit", "Report", "RetailEdge Invoice Payment Audit", "Review & Approvals", 50, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("POS Closing Variance vs Expenses", "Report", "POS Closing Variance vs Expenses", "Review & Approvals", 60, "manager", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Unmatched Bank Transactions", "Report", "RetailEdge Unmatched Bank Transactions", "Review & Approvals", 70, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Unmatched Bank Payments", "Report", "RetailEdge Unmatched Bank Payment Events", "Review & Approvals", 80, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Reconciliation Readiness", "Report", "RetailEdge Bank Match Reconciliation Readiness", "Review & Approvals", 90, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Reconciliation Handoff", "Report", "RetailEdge Reconciliation Handoff", "Review & Approvals", 100, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Daily Sales Audit Register", "Report", "RetailEdge Daily Sales Audit Register", "Review & Approvals", 110, "manager", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("RetailEdge Settings", "DocType", "RetailEdge Settings", "Setup", 10, "admin", "RetailEdge Native"),
	WorkspaceHomeItem("Branch Profiles", "DocType", "RetailEdge Branch Profile", "Setup", 20, "admin", "RetailEdge Native"),
	WorkspaceHomeItem("Expense Categories", "DocType", "RetailEdge Expense Category", "Setup", 30, "admin", "RetailEdge Native"),
	WorkspaceHomeItem("Bank Accounts", "DocType", "Bank Account", "Setup", 40, "admin", "ERPNext Link"),
	WorkspaceHomeItem("Modes of Payment", "DocType", "Mode of Payment", "Setup", 50, "admin", "ERPNext Link"),
	WorkspaceHomeItem("Bank Statement Mapping", "DocType", "RetailEdge Statement Mapping Template", "Setup", 60, "admin", "RetailEdge Native"),
)


def _target_exists(link_type: str, link_to: str) -> bool:
	if link_type == "URL":
		return bool(link_to)
	if link_type not in {"DocType", "Report", "Page", "Workspace"}:
		return True
	try:
		return bool(frappe.db.exists(link_type, link_to))
	except Exception:
		return False


def _target_exists_cached(link_type: str, link_to: str, cache: dict[tuple[str, str], bool]) -> bool:
	key = (link_type, link_to)
	if key not in cache:
		cache[key] = _target_exists(link_type, link_to)
	return cache[key]


def target_exists(item: WorkspaceHomeItem, cache: dict[tuple[str, str], bool] | None = None) -> bool:
	if item.link_type == "URL":
		return bool(item.url or item.link_to)
	if cache is None:
		return _target_exists(item.link_type, item.link_to)
	return _target_exists_cached(item.link_type, item.link_to, cache)


def _resolve_runtime_item(item: WorkspaceHomeItem, *, pos_capabilities=None) -> WorkspaceHomeItem | None:
	if item.section != "Sell":
		return item

	if pos_capabilities is None:
		pos_capabilities = get_pos_runtime_capabilities(_target_exists)
	if item.label == START_POS_LABEL:
		if not pos_capabilities.start_link_type or not pos_capabilities.start_target:
			return None
		return replace(
			item,
			link_type=pos_capabilities.start_link_type,
			link_to=pos_capabilities.start_target,
			source="POSNext Link" if pos_capabilities.provider == "posnext" else "ERPNext Link",
			url=pos_capabilities.start_url,
		)

	if item.link_to in {POSNEXT_OPENING_SHIFT, ERPNEXT_POS_OPENING_ENTRY}:
		if not pos_capabilities.opening_doctype:
			return None
		return replace(
			item,
			label=pos_capabilities.opening_doctype,
			link_to=pos_capabilities.opening_doctype,
			source="POSNext Link" if pos_capabilities.provider == "posnext" else "ERPNext Link",
			url=None,
		)

	if item.link_to in {POSNEXT_CLOSING_SHIFT, ERPNEXT_POS_CLOSING_ENTRY}:
		if not pos_capabilities.closing_doctype:
			return None
		return replace(
			item,
			label=pos_capabilities.closing_doctype,
			link_to=pos_capabilities.closing_doctype,
			source="POSNext Link" if pos_capabilities.provider == "posnext" else "ERPNext Link",
			url=None,
		)
	return item


def get_home_workspace_items(workspace_data: dict, check_dependencies: bool = True) -> list[WorkspaceHomeItem]:
	del workspace_data  # retained for API compatibility with workspace sync callers
	seen: set[tuple[str, str]] = set()
	items: list[WorkspaceHomeItem] = []
	target_cache: dict[tuple[str, str], bool] = {}
	pos_capabilities = get_pos_runtime_capabilities(
		lambda link_type, link_to: _target_exists_cached(link_type, link_to, target_cache)
	)
	items_by_section: dict[str, list[WorkspaceHomeItem]] = {section: [] for section in HOME_SECTIONS}
	for item in HOME_WORKSPACE_ITEMS:
		if item.section in items_by_section:
			items_by_section[item.section].append(item)

	for section in HOME_SECTIONS:
		for base_item in sorted(items_by_section[section], key=lambda item: item.priority):
			item = _resolve_runtime_item(base_item, pos_capabilities=pos_capabilities)
			if item is None:
				continue
			key = (item.link_type, item.url or item.link_to)
			if key in seen or (check_dependencies and not target_exists(item, target_cache)):
				continue
			seen.add(key)
			items.append(item)
	return items


def _shortcut_row(item: WorkspaceHomeItem) -> dict:
	row = {
		"color": item.color,
		"doc_view": "" if item.link_type in {"Report", "URL"} else "List",
		"label": item.label,
		"stats_filter": "[]",
		"type": item.link_type,
	}
	if item.link_type == "URL":
		row["url"] = item.url or item.link_to
	else:
		row["link_to"] = item.link_to
	return row


def build_home_workspace_shortcuts(workspace_data: dict, check_dependencies: bool = True) -> list[dict]:
	return [_shortcut_row(item) for item in get_home_workspace_items(workspace_data, check_dependencies=check_dependencies)]


def _items_by_section(
	workspace_data: dict,
	check_dependencies: bool = True,
	include_urls: bool = False,
) -> dict[str, list[WorkspaceHomeItem]]:
	sections = {section: [] for section in HOME_SECTIONS}
	for item in get_home_workspace_items(workspace_data, check_dependencies=check_dependencies):
		if item.label == START_POS_LABEL and not include_urls:
			continue
		sections.setdefault(item.section, []).append(item)
	return {section: items for section, items in sections.items() if items}


def build_home_workspace_links(workspace_data: dict, check_dependencies: bool = True) -> list[dict]:
	links: list[dict] = []
	for section, items in _items_by_section(workspace_data, check_dependencies=check_dependencies).items():
		links.append(
			{
				"hidden": 0,
				"is_query_report": 0,
				"label": section,
				"link_count": len(items),
				"link_type": items[0].link_type if items else "DocType",
				"onboard": 0,
				"type": "Card Break",
				"close": 1,
			}
		)
		for item in items:
			row = {
				"hidden": 0,
				"is_query_report": 1 if item.link_type == "Report" else 0,
				"label": item.label,
				"link_count": 0,
				"link_type": item.link_type,
				"onboard": 0,
				"type": "Link",
			}
			if item.link_type == "URL":
				row["url"] = item.url or item.link_to
			else:
				row["link_to"] = item.link_to
			links.append(row)
	return links


def build_home_workspace_content(workspace_data: dict, check_dependencies: bool = True) -> str:
	content: list[dict] = [
		{
			"id": "retailedge_home_header",
			"type": "header",
			"data": {
				"text": (
					'<div class="retailedge-home-title"><span>RetailEdge</span>'
					"<small>Business operations, controls and insights</small></div>"
				),
				"col": 12,
			},
		}
	]
	for item in get_home_workspace_items(workspace_data, check_dependencies=check_dependencies):
		if item.label == START_POS_LABEL:
			content.append(
				{
					"id": "retailedge_home_start_pos",
					"type": "shortcut",
					"data": {"shortcut_name": item.label, "col": 4},
				}
			)
			break
	for idx, section in enumerate(
		_items_by_section(workspace_data, check_dependencies=check_dependencies), start=1
	):
		content.append(
			{
				"id": f"retailedge_home_section_{idx}",
				"type": "card",
				"data": {"card_name": section, "col": 4},
			}
		)
	return json.dumps(content, separators=(",", ":"))