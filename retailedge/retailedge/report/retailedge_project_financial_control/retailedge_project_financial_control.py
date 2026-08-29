from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

MAX_PROJECT_ROWS = 500


def execute(filters: dict[str, Any] | None = None):
	filters = frappe._dict(filters or {})
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_require_read("Project")
	_require_read("Payment Entry")
	_require_read("Sales Invoice")
	_require_read("Purchase Invoice")
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to read Company {0}.").format(company), frappe.PermissionError)

	project_filters: dict[str, Any] = {"company": company}
	if filters.get("project"):
		project_filters["name"] = filters.project
	if filters.get("customer"):
		project_filters["customer"] = filters.customer
	if filters.get("status"):
		project_filters["status"] = filters.status

	projects = frappe.get_list(
		"Project",
		filters=project_filters,
		fields=[
			"name", "project_name", "status", "project_type", "customer", "company", "percent_complete",
			"estimated_costing", "total_sales_amount", "total_billed_amount", "total_purchase_cost",
			"total_consumed_material_cost", "total_costing_amount", "gross_margin", "per_gross_margin",
		],
		order_by="status asc, name asc",
		limit_page_length=MAX_PROJECT_ROWS,
	)
	if not projects:
		return _columns(), [], _("No Projects match the selected filters.")

	project_names = [row.name for row in projects]
	cash_in = _payment_totals(project_names, "Receive", "base_received_amount")
	cash_out = _payment_totals(project_names, "Pay", "base_paid_amount")
	receivables = _invoice_outstanding("Sales Invoice", project_names)
	payables = _invoice_outstanding("Purchase Invoice", project_names)
	budget_readable = bool(frappe.db.exists("DocType", "Budget") and frappe.has_permission("Budget", "read"))
	budgets = _submitted_project_budgets(project_names, company) if budget_readable else {}
	currency = str(frappe.db.get_value("Company", company, "default_currency") or "")

	rows: list[dict[str, Any]] = []
	for project in projects:
		purchase_cost = flt(project.total_purchase_cost)
		material_cost = flt(project.total_consumed_material_cost)
		timesheet_cost = flt(project.total_costing_amount)
		tracked_cost = purchase_cost + material_cost + timesheet_cost
		project_budget = budgets.get(project.name) if budget_readable else None
		rows.append(
			{
				"project": project.name,
				"project_name": project.project_name or project.name,
				"status": project.status or "",
				"project_type": project.project_type or "",
				"customer": project.customer or "",
				"percent_complete": flt(project.percent_complete),
				"currency": currency,
				"estimated_cost": flt(project.estimated_costing),
				"submitted_budget": project_budget,
				"sales_order_value": flt(project.total_sales_amount),
				"billed_amount": flt(project.total_billed_amount),
				"receivable_outstanding": receivables.get(project.name, 0.0),
				"payable_outstanding": payables.get(project.name, 0.0),
				"project_cash_in": cash_in.get(project.name, 0.0),
				"project_cash_out": cash_out.get(project.name, 0.0),
				"net_project_cash": cash_in.get(project.name, 0.0) - cash_out.get(project.name, 0.0),
				"purchase_cost": purchase_cost,
				"consumed_material_cost": material_cost,
				"timesheet_cost": timesheet_cost,
				"tracked_cost": tracked_cost,
				"budget_remaining": (project_budget - tracked_cost) if project_budget is not None else None,
				"gross_margin": flt(project.gross_margin),
				"gross_margin_percent": flt(project.per_gross_margin),
			}
		)

	message_parts = [
		_("Whole-project report: Branch filtering is intentionally not offered because ERPNext Project billing, costing, receivables, payables and margin are project-wide values."),
		_("Project Cash In/Out is submitted project-linked Payment Entry movement and is not revenue, expense, profit or bank balance."),
		_("Receivable/Payable Outstanding comes from submitted Sales/Purchase Invoices carrying the Project link."),
	]
	if budget_readable:
		message_parts.append(_("Submitted Budget comes from ERPNext Budget Against Project; ERPNext Stop/Warn/Ignore controls remain authoritative."))
	else:
		message_parts.append(_("ERPNext Project Budget values are hidden because the current user cannot read Budget."))
	return _columns(), rows, " ".join(message_parts)


def _require_read(doctype: str) -> None:
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _payment_totals(project_names: list[str], payment_type: str, amount_field: str) -> dict[str, float]:
	rows = frappe.get_list(
		"Payment Entry",
		filters={"docstatus": 1, "project": ["in", project_names], "payment_type": payment_type},
		fields=["project", f"sum({amount_field}) as total_amount"],
		group_by="project",
		limit_page_length=MAX_PROJECT_ROWS,
	)
	return {row.project: flt(row.total_amount) for row in rows if row.project}


def _invoice_outstanding(doctype: str, project_names: list[str]) -> dict[str, float]:
	meta = frappe.get_meta(doctype)
	if not meta.has_field("project") or not meta.has_field("outstanding_amount"):
		return {}
	rows = frappe.get_list(
		doctype,
		filters={"docstatus": 1, "project": ["in", project_names], "outstanding_amount": ["!=", 0]},
		fields=["project", "sum(outstanding_amount) as outstanding_amount"],
		group_by="project",
		limit_page_length=MAX_PROJECT_ROWS,
	)
	return {row.project: flt(row.outstanding_amount) for row in rows if row.project}


def _submitted_project_budgets(project_names: list[str], company: str) -> dict[str, float]:
	rows = frappe.get_list(
		"Budget",
		filters={
			"docstatus": 1,
			"budget_against": "Project",
			"company": company,
			"project": ["in", project_names],
		},
		fields=["project", "sum(budget_amount) as budget_amount"],
		group_by="project",
		limit_page_length=MAX_PROJECT_ROWS,
	)
	return {row.project: flt(row.budget_amount) for row in rows if row.project}


def _columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "project", "label": _("Project"), "fieldtype": "Link", "options": "Project", "width": 140},
		{"fieldname": "project_name", "label": _("Project Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 145},
		{"fieldname": "percent_complete", "label": _("Progress %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "width": 75},
		{"fieldname": "submitted_budget", "label": _("Submitted Budget"), "fieldtype": "Currency", "options": "currency", "width": 125},
		{"fieldname": "sales_order_value", "label": _("Sales Order Value"), "fieldtype": "Currency", "options": "currency", "width": 125},
		{"fieldname": "billed_amount", "label": _("Billed"), "fieldtype": "Currency", "options": "currency", "width": 105},
		{"fieldname": "receivable_outstanding", "label": _("Receivable Outstanding"), "fieldtype": "Currency", "options": "currency", "width": 145},
		{"fieldname": "payable_outstanding", "label": _("Payable Outstanding"), "fieldtype": "Currency", "options": "currency", "width": 140},
		{"fieldname": "project_cash_in", "label": _("Project Cash In"), "fieldtype": "Currency", "options": "currency", "width": 115},
		{"fieldname": "project_cash_out", "label": _("Project Cash Out"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "net_project_cash", "label": _("Net Project-linked Cash"), "fieldtype": "Currency", "options": "currency", "width": 145},
		{"fieldname": "purchase_cost", "label": _("Purchase Cost"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "consumed_material_cost", "label": _("Consumed Material Cost"), "fieldtype": "Currency", "options": "currency", "width": 145},
		{"fieldname": "timesheet_cost", "label": _("Timesheet Cost"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "tracked_cost", "label": _("Tracked Cost"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "budget_remaining", "label": _("Budget Remaining"), "fieldtype": "Currency", "options": "currency", "width": 125},
		{"fieldname": "gross_margin", "label": _("Gross Margin"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "gross_margin_percent", "label": _("Margin %"), "fieldtype": "Percent", "width": 85},
	]
