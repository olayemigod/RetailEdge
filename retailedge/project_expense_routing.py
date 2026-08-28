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
	}


@frappe.whitelist()
def get_project_expense_routes(project: str) -> dict[str, Any]:
	"""Return available native ERPNext expense/cost entry routes for a Project.

	This endpoint never creates or posts accounting entries. It tells EdgeSuite
	which standard documents the current user can create and which Project/Company/
	Cost Center values can be safely prefilled at parent level. Child-level project
	allocation remains inside the native document UI.
	"""
	_assert_read(PROJECT_DOCTYPE, project)
	doc = frappe.get_doc(PROJECT_DOCTYPE, project)
	if not doc.company:
		frappe.throw(_("Project {0} has no Company.").format(project))

	routes: list[dict[str, Any]] = []

	if _can_create("Purchase Invoice"):
		routes.append(
			_route_option(
				key="purchase-invoice",
				label=_("Supplier / Service Expense"),
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
				label=_("Material Consumption / Transfer"),
				description=_("Use native Stock Entry when project cost arises from material issue, consumption or stock movement."),
				doctype="Stock Entry",
				project=project,
				company=doc.company,
				cost_center=doc.cost_center or "",
				project_prefill=True,
				kind="stock",
			)
		)

	# Expense Claim is supplied by HRMS on many sites rather than ERPNext itself.
	# Expose it only when installed and permitted. Project may live on a child row,
	# so we deliberately do not pretend a parent-level Project prefill is valid.
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
		"policy": "Use the native ERPNext/HRMS document that matches the business transaction; RetailEdge does not maintain a generic project expense ledger.",
	}
