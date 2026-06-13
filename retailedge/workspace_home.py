from __future__ import annotations

import json
from dataclasses import dataclass
import frappe


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
	"Operations",
	"Review & Approvals",
	"Reports & Analytics",
	"Accounting / Ledger Bridge",
	"Setup / Configuration",
	"Admin / Maintenance",
)

# Dense Home launchpad order. Sidebar grouping remains in workspace_sidebar JSON.
HOME_WORKSPACE_ITEMS: tuple[WorkspaceHomeItem, ...] = (
	WorkspaceHomeItem("Start POS", "URL", "/pos/", "Operations", 1, "cashier", "POSNext Link", "Green", "/pos/"),
	WorkspaceHomeItem("Cashier Expense", "DocType", "RetailEdge Cashier Expense", "Operations", 10, "cashier", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Daily Sales Audit", "DocType", "RetailEdge Daily Sales Audit", "Operations", 20, "operations", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Payment Statement Import", "DocType", "RetailEdge Payment Statement Import", "Operations", 30, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Bank Transaction Matching", "Report", "RetailEdge Bank Transaction Matching", "Operations", 40, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("POS Opening Shift", "DocType", "POS Opening Shift", "Operations", 80, "cashier", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("POS Closing Shift", "DocType", "POS Closing Shift", "Operations", 90, "cashier", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Bank Transaction", "DocType", "Bank Transaction", "Operations", 100, "bank_ops", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Payment Entry", "DocType", "Payment Entry", "Operations", 110, "bank_ops", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Sales Invoice", "DocType", "Sales Invoice", "Operations", 120, "operations", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Item", "DocType", "Item", "Operations", 200, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Warehouse", "DocType", "Warehouse", "Operations", 210, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Entry", "DocType", "Stock Entry", "Operations", 220, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Reconciliation", "DocType", "Stock Reconciliation", "Operations", 230, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Material Request", "DocType", "Material Request", "Operations", 240, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Purchase Receipt", "DocType", "Purchase Receipt", "Operations", 250, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Delivery Note", "DocType", "Delivery Note", "Operations", 260, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Bank Match Review", "DocType", "RetailEdge Bank Transaction Match", "Review & Approvals", 10, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Reconciliation Readiness Review", "Report", "RetailEdge Bank Match Reconciliation Readiness", "Review & Approvals", 20, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Reconciliation Handoff", "Report", "RetailEdge Reconciliation Handoff", "Review & Approvals", 30, "reviewer", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Invoice Payment Audit", "Report", "RetailEdge Invoice Payment Audit", "Review & Approvals", 40, "reviewer", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Cashier Expense Review", "Report", "RetailEdge Cashier Expense Review", "Review & Approvals", 50, "approver", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Cash Shift Verification", "Report", "RetailEdge Cash Shift Verification", "Review & Approvals", 60, "reviewer", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Branch Performance Summary", "Report", "RetailEdge Branch Performance Summary", "Reports & Analytics", 10, "manager", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Daily Sales Audit Register", "Report", "RetailEdge Daily Sales Audit Register", "Reports & Analytics", 20, "manager", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Unmatched Bank Transactions", "Report", "RetailEdge Unmatched Bank Transactions", "Reports & Analytics", 30, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Unmatched Bank Payment Events", "Report", "RetailEdge Unmatched Bank Payment Events", "Reports & Analytics", 40, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Bank Transaction Matching Report", "Report", "RetailEdge Bank Transaction Matching", "Reports & Analytics", 50, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Reconciliation Handoff Report", "Report", "RetailEdge Reconciliation Handoff", "Reports & Analytics", 60, "bank_ops", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("POS Closing Variance vs Expenses", "Report", "POS Closing Variance vs Expenses", "Reports & Analytics", 70, "manager", "RetailEdge Native", "Green"),
	WorkspaceHomeItem("Payment Statement Import Register", "DocType", "RetailEdge Payment Statement Import", "Reports & Analytics", 80, "bank_ops", "RetailEdge Native", "Blue"),
	WorkspaceHomeItem("Stock Ledger", "Report", "Stock Ledger", "Reports & Analytics", 150, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Balance", "Report", "Stock Balance", "Reports & Analytics", 160, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Projected Qty", "Report", "Stock Projected Qty", "Reports & Analytics", 170, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Stock Ageing", "Report", "Stock Ageing", "Reports & Analytics", 180, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Batch-Wise Balance History", "Report", "Batch-Wise Balance History", "Reports & Analytics", 190, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Serial No and Batch Traceability", "Report", "Serial No and Batch Traceability", "Reports & Analytics", 200, "stock", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Journal Entry", "DocType", "Journal Entry", "Accounting / Ledger Bridge", 10, "accounts", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Reconciliation Readiness", "Report", "RetailEdge Bank Match Reconciliation Readiness", "Accounting / Ledger Bridge", 20, "accounts", "RetailEdge Overlay", "Blue"),
	WorkspaceHomeItem("Settings", "DocType", "RetailEdge Settings", "Setup / Configuration", 10, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Branch Profile", "DocType", "RetailEdge Branch Profile", "Setup / Configuration", 20, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Branch Profile User", "DocType", "RetailEdge Branch Profile User", "Setup / Configuration", 30, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Expense Category", "DocType", "RetailEdge Expense Category", "Setup / Configuration", 40, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Statement Mapping Template", "DocType", "RetailEdge Statement Mapping Template", "Setup / Configuration", 50, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Bank Account", "DocType", "Bank Account", "Setup / Configuration", 100, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Mode of Payment", "DocType", "Mode of Payment", "Setup / Configuration", 110, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Item Group", "DocType", "Item Group", "Setup / Configuration", 120, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("UOM", "DocType", "UOM", "Setup / Configuration", 130, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Batch", "DocType", "Batch", "Setup / Configuration", 140, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Serial No", "DocType", "Serial No", "Setup / Configuration", 150, "admin", "ERPNext Link", "Grey"),
	WorkspaceHomeItem("Sales Invoice Verification Sync", "Report", "RetailEdge Invoice Payment Audit", "Admin / Maintenance", 10, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Bank Match Integrity Check", "Report", "RetailEdge Bank Match Reconciliation Readiness", "Admin / Maintenance", 20, "admin", "RetailEdge Overlay", "Grey"),
	WorkspaceHomeItem("Bank Match Batch Jobs", "DocType", "RetailEdge Bank Match Batch Job", "Admin / Maintenance", 25, "admin", "RetailEdge Native", "Grey"),
	WorkspaceHomeItem("Failed Reconciliation Repair", "Report", "RetailEdge Reconciliation Handoff", "Admin / Maintenance", 30, "admin", "RetailEdge Overlay", "Grey"),
	WorkspaceHomeItem("Error Log", "DocType", "Error Log", "Admin / Maintenance", 100, "admin", "ERPNext Link", "Grey"),
)


def target_exists(item: WorkspaceHomeItem) -> bool:
	if item.link_type == "URL":
		return bool(item.url or item.link_to)
	if item.link_type in {"DocType", "Report", "Page", "Workspace"}:
		return bool(frappe.db.exists(item.link_type, item.link_to))
	return True


def _json_link_index(workspace_data: dict) -> set[tuple[str, str, str]]:
	link_index = {
		(row.get("label"), row.get("link_type"), row.get("link_to"))
		for row in workspace_data.get("links", []) or []
		if row.get("type") == "Link"
	}
	link_index.update(
		(row.get("label"), row.get("type"), row.get("url") or row.get("link_to"))
		for row in workspace_data.get("shortcuts", []) or []
		if row.get("type") == "URL"
	)
	return link_index


def get_home_workspace_items(workspace_data: dict, check_dependencies: bool = True) -> list[WorkspaceHomeItem]:
	available = _json_link_index(workspace_data)
	seen: set[tuple[str, str, str]] = set()
	items: list[WorkspaceHomeItem] = []
	for section in HOME_SECTIONS:
		section_items = sorted(
			(item for item in HOME_WORKSPACE_ITEMS if item.section == section),
			key=lambda item: item.priority,
		)
		for item in section_items:
			key = (item.label, item.link_type, item.url or item.link_to)
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
		if item.link_type == "URL" and not include_urls:
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
		if item.link_type == "URL":
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
