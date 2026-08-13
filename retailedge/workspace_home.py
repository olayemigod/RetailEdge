from __future__ import annotations

import json
from dataclasses import dataclass, replace

import frappe

from retailedge.pos_runtime import (
	ERPNEXT_POS_CLOSING_ENTRY,
	ERPNEXT_POS_OPENING_ENTRY,
	ERPNEXT_POS_PAGE,
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


HOME_SECTIONS: tuple[str, ...] = (
	"Dashboard",
	"Sales & POS",
	"Cash, Bank & Reconciliation",
	"Inventory & Purchasing",
	"Expenses, Payables & Receivables",
	"Reviews & Exceptions",
	"Reports & Insights",
	"Setup & Configuration",
	"Admin & Maintenance",
)

# Dense Home launchpad order. Sidebar grouping remains in workspace_sidebar JSON.
HOME_WORKSPACE_ITEMS: tuple[WorkspaceHomeItem, ...] = (
	WorkspaceHomeItem("Salesperson Performance Dashboard", "Page", "salesperson-performance-dashboard", "Dashboard", 10, "manager", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Branch Performance Summary", "Report", "RetailEdge Branch Performance Summary", "Dashboard", 20, "manager", "RetailEdge Native", "Blue"),

	WorkspaceHomeItem(START_POS_LABEL, "URL", POSNEXT_POS_URL, "Sales & POS", 10, "cashier", "POS Runtime", "Green", POSNEXT_POS_URL),
	WorkspaceHomeItem("POS Opening", "DocType", POSNEXT_OPENING_SHIFT, "Sales & POS", 20, "cashier", "POS Runtime", "Grey"),
	WorkspaceHomeItem("POS Closing", "DocType", POSNEXT_CLOSING_SHIFT, "Sales & POS", 30, "cashier", "POS Runtime", "Grey"),
	WorkspaceHomeItem("Sales Invoice", "DocType", "Sales Invoice", "Sales & POS", 40, "operations", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Customer", "DocType", "Customer", "Sales & POS", 50, "cashier", "ERPNext Link", "Grey"),

	WorkspaceHomeItem("Payment Entry", "DocType", "Payment Entry", "Cash, Bank & Reconciliation", 10, "bank_ops", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Bank Transaction", "DocType", "Bank Transaction", "Cash, Bank & Reconciliation", 20, "bank_ops", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Payment Statement Import", "DocType", "RetailEdge Payment Statement Import", "Cash, Bank & Reconciliation", 30, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Bank Match Review", "DocType", "RetailEdge Bank Transaction Match", "Cash, Bank & Reconciliation", 40, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Bank Transaction Matching", "Report", "RetailEdge Bank Transaction Matching", "Cash, Bank & Reconciliation", 50, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Cashier Expense", "DocType", "RetailEdge Cashier Expense", "Cash, Bank & Reconciliation", 60, "cashier", "RetailEdge Native", "Green"),

	WorkspaceHomeItem("Item", "DocType", "Item", "Inventory & Purchasing", 10, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Warehouse", "DocType", "Warehouse", "Inventory & Purchasing", 20, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Entry", "DocType", "Stock Entry", "Inventory & Purchasing", 30, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Reconciliation", "DocType", "Stock Reconciliation", "Inventory & Purchasing", 40, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Material Request", "DocType", "Material Request", "Inventory & Purchasing", 50, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Purchase Receipt", "DocType", "Purchase Receipt", "Inventory & Purchasing", 60, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Delivery Note", "DocType", "Delivery Note", "Inventory & Purchasing", 70, "stock", "ERPNext Link", "Grey"),

	WorkspaceHomeItem("Journal Entry", "DocType", "Journal Entry", "Expenses, Payables & Receivables", 10, "accounts", "ERPNext Link", "Grey"),

	WorkspaceHomeItem("Daily Sales Audit", "DocType", "RetailEdge Daily Sales Audit", "Reviews & Exceptions", 10, "operations", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Cashier Expense Review", "Report", "RetailEdge Cashier Expense Review", "Reviews & Exceptions", 20, "approver", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Cash Shift Verification", "Report", "RetailEdge Cash Shift Verification", "Reviews & Exceptions", 30, "reviewer", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Invoice Payment Audit", "Report", "RetailEdge Invoice Payment Audit", "Reviews & Exceptions", 40, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("POS Closing Variance vs Expenses", "Report", "POS Closing Variance vs Expenses", "Reviews & Exceptions", 50, "manager", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Daily Sales Audit Register", "Report", "RetailEdge Daily Sales Audit Register", "Reviews & Exceptions", 60, "manager", "RetailEdge Native", "Blue"),

	WorkspaceHomeItem("Stock Ledger", "Report", "Stock Ledger", "Reports & Insights", 10, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Balance", "Report", "Stock Balance", "Reports & Insights", 20, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Projected Qty", "Report", "Stock Projected Qty", "Reports & Insights", 30, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Ageing", "Report", "Stock Ageing", "Reports & Insights", 40, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Batch-Wise Balance History", "Report", "Batch-Wise Balance History", "Reports & Insights", 50, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Serial No and Batch Traceability", "Report", "Serial No and Batch Traceability", "Reports & Insights", 60, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Unmatched Bank Transactions", "Report", "RetailEdge Unmatched Bank Transactions", "Reports & Insights", 70, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Unmatched Bank Payment Events", "Report", "RetailEdge Unmatched Bank Payment Events", "Reports & Insights", 80, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Reconciliation Readiness Review", "Report", "RetailEdge Bank Match Reconciliation Readiness", "Reports & Insights", 90, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Reconciliation Handoff", "Report", "RetailEdge Reconciliation Handoff", "Reports & Insights", 100, "reviewer", "RetailEdge Overlay", "Blue"),

	WorkspaceHomeItem("Settings", "DocType", "RetailEdge Settings", "Setup & Configuration", 10, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Branch Profile", "DocType", "RetailEdge Branch Profile", "Setup & Configuration", 20, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Branch Profile User", "DocType", "RetailEdge Branch Profile User", "Setup & Configuration", 30, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Expense Category", "DocType", "RetailEdge Expense Category", "Setup & Configuration", 40, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Statement Mapping Template", "DocType", "RetailEdge Statement Mapping Template", "Setup & Configuration", 50, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Bank Account", "DocType", "Bank Account", "Setup & Configuration", 60, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Mode of Payment", "DocType", "Mode of Payment", "Setup & Configuration", 70, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Item Group", "DocType", "Item Group", "Setup & Configuration", 80, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("UOM", "DocType", "UOM", "Setup & Configuration", 90, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Batch", "DocType", "Batch", "Setup & Configuration", 100, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Serial No", "DocType", "Serial No", "Setup & Configuration", 110, "admin", "ERPNext Link", "Grey"),

	WorkspaceHomeItem("Bank Match Batch Jobs", "DocType", "RetailEdge Bank Match Batch Job", "Admin & Maintenance", 10, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Error Log", "DocType", "Error Log", "Admin & Maintenance", 20, "admin", "ERPNext Link", "Grey"),

	WorkspaceHomeItem("EdgePay Handoff Log", "DocType", "RetailEdge EdgePay Handoff Log", "EdgePay Review", 120, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("EdgePay Payment Evidence", "DocType", "RetailEdge EdgePay Payment Evidence", "EdgePay Review", 130, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("EdgePay Reconciliation Readiness", "Report", "RetailEdge EdgePay Reconciliation Readiness", "EdgePay Review", 110, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("EdgePay Evidence Summary", "Report", "RetailEdge EdgePay Payment Evidence Summary", "EdgePay Review", 120, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("EdgePay Lifecycle Status", "Report", "RetailEdge EdgePay Lifecycle Status", "EdgePay Review", 130, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("EdgePay Rollout Monitor", "Report", "RetailEdge EdgePay Rollout Monitor", "EdgePay Review", 140, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("EdgePay Readiness Checklist", "Report", "RetailEdge EdgePay Readiness Checklist", "EdgePay Review", 145, "admin", "RetailEdge Native", "Grey"),
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


def target_exists(item: WorkspaceHomeItem) -> bool:
	if item.link_type == "URL":
		return bool(item.url or item.link_to)
	return _target_exists(item.link_type, item.link_to)


def _resolve_runtime_item(item: WorkspaceHomeItem) -> WorkspaceHomeItem | None:
	if item.section != "Sales & POS":
		return item

	capabilities = get_pos_runtime_capabilities(_target_exists)
	if item.label == START_POS_LABEL:
		if not capabilities.start_link_type or not capabilities.start_target:
			return None
		return replace(
			item,
			link_type=capabilities.start_link_type,
			link_to=capabilities.start_target,
			source="POSNext Link" if capabilities.provider == "posnext" else "ERPNext Link",
			url=capabilities.start_url,
		)

	if item.link_to in {POSNEXT_OPENING_SHIFT, ERPNEXT_POS_OPENING_ENTRY}:
		if not capabilities.opening_doctype:
			return None
		return replace(
			item,
			label=capabilities.opening_doctype,
			link_to=capabilities.opening_doctype,
			source="POSNext Link" if capabilities.provider == "posnext" else "ERPNext Link",
			url=None,
		)

	if item.link_to in {POSNEXT_CLOSING_SHIFT, ERPNEXT_POS_CLOSING_ENTRY}:
		if not capabilities.closing_doctype:
			return None
		return replace(
			item,
			label=capabilities.closing_doctype,
			link_to=capabilities.closing_doctype,
			source="POSNext Link" if capabilities.provider == "posnext" else "ERPNext Link",
			url=None,
		)
	return item


def get_home_workspace_items(workspace_data: dict, check_dependencies: bool = True) -> list[WorkspaceHomeItem]:
	seen: set[tuple[str, str]] = set()
	items: list[WorkspaceHomeItem] = []
	for section in HOME_SECTIONS:
		section_items = sorted(
			(item for item in HOME_WORKSPACE_ITEMS if item.section == section),
			key=lambda item: item.priority,
		)
		for base_item in section_items:
			item = _resolve_runtime_item(base_item)
			if item is None:
				continue
			key = (item.link_type, item.url or item.link_to)
			if key in seen or (check_dependencies and not target_exists(item)):
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
	return [
		_shortcut_row(item)
		for item in get_home_workspace_items(workspace_data, check_dependencies=check_dependencies)
	]


def _items_by_section(
	workspace_data: dict, check_dependencies: bool = True, include_urls: bool = False
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
				"text": '<div class="retailedge-home-title"><span>RetailEdge</span><small>ProcessEdge operational workspace</small></div>',
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
	for idx, section in enumerate(_items_by_section(workspace_data, check_dependencies=check_dependencies), start=1):
		content.append(
			{
				"id": f"retailedge_home_section_{idx}",
				"type": "card",
				"data": {"card_name": section, "col": 4},
			}
		)
	return json.dumps(content, separators=(",", ":"))
