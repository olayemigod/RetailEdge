from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

MAX_PROJECT_BUDGET_ROWS = 200


def _assert_project_read(project: str) -> Any:
	if not frappe.has_permission("Project", "read", doc=project):
		frappe.throw(_("You do not have permission to read this Project."), frappe.PermissionError)
	return frappe.get_doc("Project", project)


@frappe.whitelist()
def get_project_budget_context(project: str, limit: int = 100) -> dict[str, Any]:
	"""Return native ERPNext Project Budget governance for one Project.

	Budget remains the governance authority. RetailEdge only exposes permitted
	Project-targeted Budget rows and their configured control actions.
	"""
	doc = _assert_project_read(project)
	if not frappe.db.exists("DocType", "Budget"):
		return {"available": False, "budgets": [], "submitted_budget": 0.0, "draft_budget": 0.0, "can_create_budget": False}
	if not frappe.has_permission("Budget", "read"):
		return {
			"available": True,
			"readable": False,
			"budgets": [],
			"submitted_budget": 0.0,
			"draft_budget": 0.0,
			"can_create_budget": False,
			"scope": "Whole Project",
			"source_of_truth": "ERPNext Budget",
		}

	page_length = max(1, min(cint(limit) or 100, MAX_PROJECT_BUDGET_ROWS))
	fields = [
		"name", "docstatus", "company", "project", "account", "budget_amount",
		"from_fiscal_year", "to_fiscal_year", "distribution_frequency",
		"applicable_on_material_request", "action_if_annual_budget_exceeded_on_mr",
		"applicable_on_purchase_order", "action_if_annual_budget_exceeded_on_po",
		"applicable_on_booking_actual_expenses", "action_if_annual_budget_exceeded",
		"applicable_on_cumulative_expense", "action_if_annual_exceeded_on_cumulative_expense",
	]
	rows = frappe.get_list(
		"Budget",
		filters={"budget_against": "Project", "project": project, "company": doc.company, "docstatus": ["<", 2]},
		fields=fields,
		order_by="docstatus desc, from_fiscal_year desc, account asc",
		limit_page_length=page_length,
	)

	budgets: list[dict[str, Any]] = []
	for row in rows:
		controls: list[str] = []
		if cint(row.applicable_on_material_request):
			controls.append(f"Material Request: {row.action_if_annual_budget_exceeded_on_mr or 'Configured'}")
		if cint(row.applicable_on_purchase_order):
			controls.append(f"Purchase Order: {row.action_if_annual_budget_exceeded_on_po or 'Configured'}")
		if cint(row.applicable_on_booking_actual_expenses):
			controls.append(f"Actual Expense: {row.action_if_annual_budget_exceeded or 'Configured'}")
		if cint(row.applicable_on_cumulative_expense):
			controls.append(f"Cumulative Expense: {row.action_if_annual_exceeded_on_cumulative_expense or 'Configured'}")
		budgets.append(
			{
				"name": row.name,
				"status": "Submitted" if cint(row.docstatus) == 1 else "Draft",
				"docstatus": cint(row.docstatus),
				"account": row.account or "",
				"budget_amount": flt(row.budget_amount),
				"from_fiscal_year": row.from_fiscal_year or "",
				"to_fiscal_year": row.to_fiscal_year or "",
				"distribution_frequency": row.distribution_frequency or "",
				"controls": controls,
				"route": f"/app/budget/{row.name}",
			}
		)

	return {
		"available": True,
		"readable": True,
		"project": doc.name,
		"company": doc.company,
		"budgets": budgets,
		"budget_count": len(budgets),
		"submitted_budget": sum(row["budget_amount"] for row in budgets if row["docstatus"] == 1),
		"draft_budget": sum(row["budget_amount"] for row in budgets if row["docstatus"] == 0),
		"controlled_budget_count": sum(1 for row in budgets if row["docstatus"] == 1 and row["controls"]),
		"can_create_budget": bool(frappe.has_permission("Budget", "create")),
		"scope": "Whole Project",
		"scope_note": "ERPNext Project Budgets are whole-project controls. Branch filtering does not alter Budget scope.",
		"source_of_truth": "ERPNext Budget",
		"policy": "Budget enforcement remains ERPNext-native; RetailEdge does not bypass Stop/Warn/Ignore controls.",
	}
