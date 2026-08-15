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
	"Purchases",
	"Inventory",
	"Cash & Banking",
	"Expenses",
	"Customers & Suppliers",
	"Reviews & Controls",
	"Reports & Insights",
	"Setup",
)

# Business-facing launchpad order. Technical maintenance DocTypes remain available
# through normal Desk search and role permissions rather than the everyday workspace.
HOME_WORKSPACE_ITEMS: tuple[WorkspaceHomeItem, ...] = (
	WorkspaceHomeItem(
		"Salesperson Performance",
		"Page",
		"salesperson-performance-dashboard",
		"Dashboard",
		10,
		"manager",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Branch Performance",
		"Report",
		"RetailEdge Branch Performance Summary",
		"Dashboard",
		20,
		"manager",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		START_POS_LABEL,
		"URL",
		POSNEXT_POS_URL,
		"Sales & POS",
		10,
		"cashier",
		"POS Runtime",
		"Green",
		POSNEXT_POS_URL,
	),
	WorkspaceHomeItem(
		"POS Opening",
		"DocType",
		POSNEXT_OPENING_SHIFT,
		"Sales & POS",
		20,
		"cashier",
		"POS Runtime",
	),
	WorkspaceHomeItem(
		"POS Closing",
		"DocType",
		POSNEXT_CLOSING_SHIFT,
		"Sales & POS",
		30,
		"cashier",
		"POS Runtime",
	),
	WorkspaceHomeItem(
		"Sales Invoices",
		"DocType",
		"Sales Invoice",
		"Sales & POS",
		40,
		"operations",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Sales Orders",
		"DocType",
		"Sales Order",
		"Sales & POS",
		50,
		"operations",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Delivery Notes",
		"DocType",
		"Delivery Note",
		"Sales & POS",
		60,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Purchase Invoices",
		"DocType",
		"Purchase Invoice",
		"Purchases",
		10,
		"purchasing",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Purchase Orders",
		"DocType",
		"Purchase Order",
		"Purchases",
		20,
		"purchasing",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Purchase Receipts",
		"DocType",
		"Purchase Receipt",
		"Purchases",
		30,
		"purchasing",
		"ERPNext Link",
	),
	WorkspaceHomeItem("Items", "DocType", "Item", "Inventory", 10, "stock", "ERPNext Link"),
	WorkspaceHomeItem(
		"Warehouses",
		"DocType",
		"Warehouse",
		"Inventory",
		20,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Stock Movement History",
		"Report",
		"RetailEdge Stock Movement History",
		"Inventory",
		30,
		"stock",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Stock Balance",
		"Report",
		"Stock Balance",
		"Inventory",
		40,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Stock Transfers",
		"DocType",
		"Stock Entry",
		"Inventory",
		50,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Stock Count",
		"DocType",
		"Stock Reconciliation",
		"Inventory",
		60,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Material Requests",
		"DocType",
		"Material Request",
		"Inventory",
		70,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Payment Entries",
		"DocType",
		"Payment Entry",
		"Cash & Banking",
		10,
		"bank_ops",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Bank Transactions",
		"DocType",
		"Bank Transaction",
		"Cash & Banking",
		20,
		"bank_ops",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Import Bank Statement",
		"DocType",
		"RetailEdge Payment Statement Import",
		"Cash & Banking",
		30,
		"bank_ops",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Bank Matching",
		"Report",
		"RetailEdge Bank Transaction Matching",
		"Cash & Banking",
		40,
		"bank_ops",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Cashier Expenses",
		"DocType",
		"RetailEdge Cashier Expense",
		"Expenses",
		10,
		"cashier",
		"RetailEdge Native",
		"Green",
	),
	WorkspaceHomeItem(
		"Expense Claims",
		"DocType",
		"Expense Claim",
		"Expenses",
		20,
		"operations",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Customers",
		"DocType",
		"Customer",
		"Customers & Suppliers",
		10,
		"operations",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Suppliers",
		"DocType",
		"Supplier",
		"Customers & Suppliers",
		20,
		"operations",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Accounts Receivable",
		"Report",
		"Accounts Receivable",
		"Customers & Suppliers",
		30,
		"accounts",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Accounts Payable",
		"Report",
		"Accounts Payable",
		"Customers & Suppliers",
		40,
		"accounts",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Bank Match Reviews",
		"DocType",
		"RetailEdge Bank Transaction Match",
		"Reviews & Controls",
		10,
		"reviewer",
		"RetailEdge Overlay",
		"Blue",
	),
	WorkspaceHomeItem(
		"Daily Sales Audit",
		"DocType",
		"RetailEdge Daily Sales Audit",
		"Reviews & Controls",
		20,
		"operations",
		"RetailEdge Native",
		"Green",
	),
	WorkspaceHomeItem(
		"Cashier Expense Review",
		"Report",
		"RetailEdge Cashier Expense Review",
		"Reviews & Controls",
		30,
		"approver",
		"RetailEdge Native",
		"Green",
	),
	WorkspaceHomeItem(
		"Cash Shift Verification",
		"Report",
		"RetailEdge Cash Shift Verification",
		"Reviews & Controls",
		40,
		"reviewer",
		"RetailEdge Native",
		"Green",
	),
	WorkspaceHomeItem(
		"Invoice Payment Audit",
		"Report",
		"RetailEdge Invoice Payment Audit",
		"Reviews & Controls",
		50,
		"reviewer",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"POS Closing Variance vs Expenses",
		"Report",
		"POS Closing Variance vs Expenses",
		"Reviews & Controls",
		60,
		"manager",
		"RetailEdge Native",
		"Green",
	),
	WorkspaceHomeItem(
		"Unmatched Bank Transactions",
		"Report",
		"RetailEdge Unmatched Bank Transactions",
		"Reviews & Controls",
		70,
		"bank_ops",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Unmatched Bank Payments",
		"Report",
		"RetailEdge Unmatched Bank Payment Events",
		"Reviews & Controls",
		80,
		"bank_ops",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Reconciliation Readiness",
		"Report",
		"RetailEdge Bank Match Reconciliation Readiness",
		"Reviews & Controls",
		90,
		"reviewer",
		"RetailEdge Overlay",
		"Blue",
	),
	WorkspaceHomeItem(
		"Reconciliation Handoff",
		"Report",
		"RetailEdge Reconciliation Handoff",
		"Reviews & Controls",
		100,
		"reviewer",
		"RetailEdge Overlay",
		"Blue",
	),
	WorkspaceHomeItem(
		"Daily Sales Audit Register",
		"Report",
		"RetailEdge Daily Sales Audit Register",
		"Reports & Insights",
		10,
		"manager",
		"RetailEdge Native",
		"Blue",
	),
	WorkspaceHomeItem(
		"Stock Ledger",
		"Report",
		"Stock Ledger",
		"Reports & Insights",
		20,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Stock Projected Qty",
		"Report",
		"Stock Projected Qty",
		"Reports & Insights",
		30,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Stock Ageing",
		"Report",
		"Stock Ageing",
		"Reports & Insights",
		40,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Batch-Wise Balance History",
		"Report",
		"Batch-Wise Balance History",
		"Reports & Insights",
		50,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Serial No and Batch Traceability",
		"Report",
		"Serial No and Batch Traceability",
		"Reports & Insights",
		60,
		"stock",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"RetailEdge Settings",
		"DocType",
		"RetailEdge Settings",
		"Setup",
		10,
		"admin",
		"RetailEdge Native",
	),
	WorkspaceHomeItem(
		"Branch Profiles",
		"DocType",
		"RetailEdge Branch Profile",
		"Setup",
		20,
		"admin",
		"RetailEdge Native",
	),
	WorkspaceHomeItem(
		"Expense Categories",
		"DocType",
		"RetailEdge Expense Category",
		"Setup",
		30,
		"admin",
		"RetailEdge Native",
	),
	WorkspaceHomeItem(
		"Bank Accounts",
		"DocType",
		"Bank Account",
		"Setup",
		40,
		"admin",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Modes of Payment",
		"DocType",
		"Mode of Payment",
		"Setup",
		50,
		"admin",
		"ERPNext Link",
	),
	WorkspaceHomeItem(
		"Bank Statement Mapping",
		"DocType",
		"RetailEdge Statement Mapping Template",
		"Setup",
		60,
		"admin",
		"RetailEdge Native",
	),
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


def get_home_workspace_items(
	workspace_data: dict, check_dependencies: bool = True
) -> list[WorkspaceHomeItem]:
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


def build_home_workspace_shortcuts(
	workspace_data: dict, check_dependencies: bool = True
) -> list[dict]:
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
				"text": (
					'<div class="retailedge-home-title"><span>RetailEdge</span>'
					"<small>ProcessEdge operational workspace</small></div>"
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
