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
# primary shell and carries the full role-aware navigation.
HOME_SECTIONS: tuple[str, ...] = (
	"Home",
	"Point of Sale",
	"Sales",
	"Purchases",
	"Stock",
	"Money & Banking",
	"Expenses",
	"Customers",
	"Suppliers & Payables",
	"Operations Review",
	"Banking & Reconciliation",
	"Insights & Dashboards",
	"Reports",
	"Selling Setup",
	"Stock Setup",
	"Finance Setup",
	"Business Setup",
)

HOME_WORKSPACE_ITEMS: tuple[WorkspaceHomeItem, ...] = (
	WorkspaceHomeItem("Business Hub", "Page", "retailedge-business-hub", "Home", 10, "all", "Business Workspace", "Blue"),

	WorkspaceHomeItem(START_POS_LABEL, "URL", POSNEXT_POS_URL, "Point of Sale", 10, "cashier", "POS Runtime", "Green", POSNEXT_POS_URL),
	WorkspaceHomeItem("POS Opening Shift", "DocType", POSNEXT_OPENING_SHIFT, "Point of Sale", 20, "cashier", "POS Runtime"),
	WorkspaceHomeItem("POS Closing Shift", "DocType", POSNEXT_CLOSING_SHIFT, "Point of Sale", 30, "cashier", "POS Runtime"),

	WorkspaceHomeItem("Sales Invoices", "DocType", "Sales Invoice", "Sales", 10, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Sales Orders", "DocType", "Sales Order", "Sales", 20, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Delivery Notes", "DocType", "Delivery Note", "Sales", 30, "stock", "ERPNext Link"),

	WorkspaceHomeItem("Purchase Operations", "Page", "professional-purchasing", "Purchases", 5, "purchasing", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Purchase Orders", "DocType", "Purchase Order", "Purchases", 10, "purchasing", "ERPNext Link"),
	WorkspaceHomeItem("Purchase Receipts", "DocType", "Purchase Receipt", "Purchases", 20, "purchasing", "ERPNext Link"),
	WorkspaceHomeItem("Purchase Invoices", "DocType", "Purchase Invoice", "Purchases", 30, "purchasing", "ERPNext Link"),

	WorkspaceHomeItem("Stock Position", "Page", "stock-position", "Stock", 10, "stock", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Stock Transfers", "DocType", "Stock Entry", "Stock", 20, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Count", "DocType", "Stock Reconciliation", "Stock", 30, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Reorder Requests", "DocType", "Material Request", "Stock", 40, "stock", "ERPNext Link"),

	WorkspaceHomeItem("Payments", "DocType", "Payment Entry", "Money & Banking", 10, "bank_ops", "ERPNext Link"),
	WorkspaceHomeItem("Cash Movement", "Page", "cash-movement", "Money & Banking", 20, "accounts", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Bank Transactions", "DocType", "Bank Transaction", "Money & Banking", 30, "bank_ops", "ERPNext Link"),
	WorkspaceHomeItem("Import Bank Statement", "Page", "bank-statement-imports", "Money & Banking", 40, "bank_ops", "Business Workspace", "Blue"),

	WorkspaceHomeItem("Business Expenses", "Page", "business-expenses", "Expenses", 10, "operations", "Business Workspace", "Green"),
	WorkspaceHomeItem("Cashier Expenses", "Page", "cashier-expenses", "Expenses", 20, "cashier", "Business Workspace", "Green"),

	WorkspaceHomeItem("Customers", "DocType", "Customer", "Customers", 10, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Customer Receivables", "Page", "customer-receivables", "Customers", 20, "accounts", "Business Workspace", "Blue"),

	WorkspaceHomeItem("Suppliers", "DocType", "Supplier", "Suppliers & Payables", 10, "operations", "ERPNext Link"),
	WorkspaceHomeItem("Supplier Payables", "Page", "supplier-payables", "Suppliers & Payables", 20, "accounts", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Payment Orders", "DocType", "Payment Order", "Suppliers & Payables", 30, "accounts", "ERPNext Link"),

	WorkspaceHomeItem("Daily Sales Audit", "Page", "daily-sales-audit", "Operations Review", 10, "operations", "Business Workspace", "Green"),
	WorkspaceHomeItem("Cashier Expense Review", "Page", "expense-review", "Operations Review", 20, "approver", "Business Workspace", "Green"),
	WorkspaceHomeItem("Cash Shift Verification", "Page", "cash-shift-verification", "Operations Review", 30, "reviewer", "Business Workspace", "Green"),
	WorkspaceHomeItem("POS Closing Variance & Expenses", "Page", "pos-closing-variance", "Operations Review", 40, "manager", "Business Workspace", "Green"),

	WorkspaceHomeItem("Bank Matching & Reconciliation", "Page", "bank-matching-reconciliation", "Banking & Reconciliation", 10, "bank_ops", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Banking Readiness", "Page", "banking-readiness", "Banking & Reconciliation", 20, "reviewer", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Unmatched Bank Transactions", "Page", "unmatched-bank-transactions", "Banking & Reconciliation", 30, "bank_ops", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Unmatched Bank Payments", "Page", "unmatched-bank-payments", "Banking & Reconciliation", 40, "bank_ops", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Reconciliation Handoff", "Page", "reconciliation-handoff", "Banking & Reconciliation", 50, "reviewer", "Business Workspace", "Blue"),

	WorkspaceHomeItem("Financial Dashboard", "Page", "owner-dashboard", "Insights & Dashboards", 10, "manager", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Branch Performance", "Page", "branch-performance-dashboard", "Insights & Dashboards", 20, "manager", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Salesperson Performance", "Page", "salesperson-performance-dashboard", "Insights & Dashboards", 30, "manager", "Business Workspace", "Blue"),

	WorkspaceHomeItem("Reports Centre", "Page", "reports-centre", "Reports", 10, "all", "Business Workspace", "Blue"),

	WorkspaceHomeItem("Sales Team & Targets", "Page", "sales-team-control", "Selling Setup", 10, "manager", "Business Workspace", "Blue"),
	WorkspaceHomeItem("Sales People", "DocType", "Sales Person", "Selling Setup", 20, "manager", "ERPNext Link"),
	WorkspaceHomeItem("Sales Partners", "DocType", "Sales Partner", "Selling Setup", 30, "manager", "ERPNext Link"),

	WorkspaceHomeItem("Products", "DocType", "Item", "Stock Setup", 10, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Stock Locations", "DocType", "Warehouse", "Stock Setup", 20, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Batches", "DocType", "Batch", "Stock Setup", 30, "stock", "ERPNext Link"),
	WorkspaceHomeItem("Serial Numbers", "DocType", "Serial No", "Stock Setup", 40, "stock", "ERPNext Link"),

	WorkspaceHomeItem("Bank Accounts", "DocType", "Bank Account", "Finance Setup", 10, "admin", "ERPNext Link"),
	WorkspaceHomeItem("Modes of Payment", "DocType", "Mode of Payment", "Finance Setup", 20, "admin", "ERPNext Link"),
	WorkspaceHomeItem("Cost Centers", "DocType", "Cost Center", "Finance Setup", 30, "admin", "ERPNext Link"),
	WorkspaceHomeItem("Bank Statement Mapping", "DocType", "RetailEdge Statement Mapping Template", "Finance Setup", 40, "admin", "Business Workspace"),

	WorkspaceHomeItem("Settings", "DocType", "RetailEdge Settings", "Business Setup", 10, "admin", "Business Workspace"),
	WorkspaceHomeItem("Branch Setup", "DocType", "RetailEdge Branch Profile", "Business Setup", 20, "admin", "Business Workspace"),
	WorkspaceHomeItem("Expense Categories", "DocType", "RetailEdge Expense Category", "Business Setup", 30, "admin", "Business Workspace"),
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
	if item.section != "Point of Sale":
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
			label="POS Opening Shift",
			link_to=pos_capabilities.opening_doctype,
			source="POSNext Link" if pos_capabilities.provider == "posnext" else "ERPNext Link",
			url=None,
		)

	if item.link_to in {POSNEXT_CLOSING_SHIFT, ERPNEXT_POS_CLOSING_ENTRY}:
		if not pos_capabilities.closing_doctype:
			return None
		return replace(
			item,
			label="POS Closing Shift",
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
					'<div class="retailedge-home-title"><span>ProcessEdge Retail</span>'
					"<small>Structured for Scale.</small></div>"
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