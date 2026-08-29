from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.project_operations import _assert_read, _has_field

PROJECT_DOCTYPE = "Project"


def _can_create(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "create"))
	except Exception:
		return False


def _route_option(
	*,
	key: str,
	label: str,
	description: str,
	doctype: str,
	project: str,
	company: str,
	cost_center: str,
	project_prefill: bool,
	kind: str,
) -> dict[str, Any]:
	defaults: dict[str, str] = {}
	if company and _has_field(doctype, "company"):
		defaults["company"] = company
	if cost_center and _has_field(doctype, "cost_center"):
		defaults["cost_center"] = cost_center
	if project_prefill and _has_field(doctype, "project"):
		defaults["project"] = project
	return {
		"key": key,
		"label": label,
		"description": description,
		"doctype": doctype,
		"kind": kind,
		"defaults": defaults,
		"project_prefill": bool(defaults.get("project")),
		"project_link_scope": "parent" if defaults.get("project") else "native-document",
	}


@frappe.whitelist()
def get_project_expense_routes(project: str) -> dict[str, Any]:
	"""Return permitted native ERPNext project spend/material operation routes.

	This endpoint never creates, submits or posts transactions. It only exposes
	native ERPNext/HRMS documents the current user can create. Project/Company/Cost
	Center defaults are supplied only when those parent fields exist on the installed
	DocType. Child-row project allocation remains inside the native document UI.
	"""
	_assert_read(PROJECT_DOCTYPE, project)
	doc = frappe.get_doc(PROJECT_DOCTYPE, project)
	if not doc.company:
		frappe.throw(_("Project {0} has no Company.").format(project))

	routes: list[dict[str, Any]] = []

	if _can_create("Material Request"):
		routes.append(
			_route_option(
				key="material-request",
				label=_("Plan / Request Materials"),
				description=_("Create a native Material Request for project procurement or material planning. Assign the Project on the native document or item rows where required by ERPNext."),
				doctype="Material Request",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=True,
				kind="procurement-planning",
			)
		)

	if _can_create("Purchase Order"):
		routes.append(
			_route_option(
				key="purchase-order",
				label=_("Order Project Goods / Services"),
				description=_("Create a native Purchase Order for approved project goods or services. ERPNext Budget controls remain authoritative."),
				doctype="Purchase Order",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=True,
				kind="procurement-order",
			)
		)

	if _can_create("Purchase Receipt"):
		routes.append(
			_route_option(
				key="purchase-receipt",
				label=_("Receive Project Materials"),
				description=_("Use native Purchase Receipt when project materials or goods are physically received against purchasing documents."),
				doctype="Purchase Receipt",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=True,
				kind="procurement-receipt",
			)
		)

	if _can_create("Purchase Invoice"):
		routes.append(
			_route_option(
				key="purchase-invoice",
				label=_("Book Supplier / Service Cost"),
				description=_("Create a native Purchase Invoice for supplier bills, services, materials or other project costs."),
				doctype="Purchase Invoice",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=True,
				kind="expense",
			)
		)

	if _can_create("Stock Entry"):
		routes.append(
			_route_option(
				key="stock-entry",
				label=_("Consume / Transfer Project Materials"),
				description=_("Use native Stock Entry for project material issue, consumption, transfer or other stock movement."),
				doctype="Stock Entry",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=True,
				kind="stock",
			)
		)

	if _can_create("Expense Claim"):
		routes.append(
			_route_option(
				key="expense-claim",
				label=_("Employee Reimbursement"),
				description=_("Open the native Expense Claim workflow. Assign the Project on the applicable expense rows where supported by the installed HRMS version."),
				doctype="Expense Claim",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=False,
				kind="employee-expense",
			)
		)

	if _can_create("Journal Entry"):
		routes.append(
			_route_option(
				key="journal-entry",
				label=_("Accounting Adjustment"),
				description=_("Use Journal Entry only for accounting adjustments that do not belong in purchasing, stock or employee expense workflows."),
				doctype="Journal Entry",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=False,
				kind="accounting-adjustment",
			)
		)

	return {
		"project": doc.name,
		"company": doc.company,
		"cost_center": doc.cost_center or "",
		"routes": routes,
		"policy": "Choose the native ERPNext/HRMS document that matches the business event. Purchasing, stock, Budget and accounting controls remain authoritative; RetailEdge does not maintain a generic project expense or procurement ledger.",
	}
