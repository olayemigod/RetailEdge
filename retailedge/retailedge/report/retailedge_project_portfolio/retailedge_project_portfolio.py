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
	if not frappe.has_permission("Project", "read"):
		frappe.throw(_("You do not have permission to read Projects."), frappe.PermissionError)
	if not frappe.has_permission("Payment Entry", "read"):
		frappe.throw(_("You do not have permission to read Payment Entries."), frappe.PermissionError)
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to read Company {0}.").format(company), frappe.PermissionError)

	project_filters: dict[str, Any] = {"company": company}
	if filters.get("customer"):
		project_filters["customer"] = filters.customer
	if filters.get("status"):
		project_filters["status"] = filters.status

	projects = frappe.get_list(
		"Project",
		filters=project_filters,
		fields=[
			"name",
			"project_name",
			"status",
			"project_type",
			"customer",
			"company",
			"percent_complete",
			"expected_start_date",
			"expected_end_date",
			"estimated_costing",
			"total_sales_amount",
			"total_billed_amount",
			"total_purchase_cost",
			"total_consumed_material_cost",
			"total_costing_amount",
			"gross_margin",
			"per_gross_margin",
		],
		order_by="status asc, expected_end_date asc, name asc",
		limit_page_length=MAX_PROJECT_ROWS,
	)
	if not projects:
		return _columns(), [], _("No Projects match the selected filters.")

	project_names = [row.name for row in projects]
	receipts = _payment_totals(project_names, "Receive", "base_received_amount")
	payments = _payment_totals(project_names, "Pay", "base_paid_amount")
	currency = str(frappe.db.get_value("Company", company, "default_currency") or "")

	rows = []
	for project in projects:
		funds_received = receipts.get(project.name, 0.0)
		funds_paid = payments.get(project.name, 0.0)
		tracked_cost = (
			flt(project.total_purchase_cost)
			+ flt(project.total_consumed_material_cost)
			+ flt(project.total_costing_amount)
		)
		rows.append(
			{
				"project": project.name,
				"project_name": project.project_name,
				"status": project.status,
				"project_type": project.project_type or "",
				"customer": project.customer or "",
				"percent_complete": flt(project.percent_complete),
				"expected_start_date": project.expected_start_date,
				"expected_end_date": project.expected_end_date,
				"currency": currency,
				"estimated_cost": flt(project.estimated_costing),
				"sales_order_value": flt(project.total_sales_amount),
				"billed_amount": flt(project.total_billed_amount),
				"funds_received": funds_received,
				"funds_paid": funds_paid,
				"cash_funds_position": funds_received - funds_paid,
				"tracked_cost": tracked_cost,
				"gross_margin": flt(project.gross_margin),
				"gross_margin_percent": flt(project.per_gross_margin),
			}
		)

	message = _(
		"Project billing, costing and margin come from ERPNext Project. Funds Received and Funds Paid are grouped submitted Payment Entries carrying the Project accounting dimension. Cash Funds Position is a management view, not a bank balance or separate ledger."
	)
	return _columns(), rows, message


def _payment_totals(project_names: list[str], payment_type: str, amount_field: str) -> dict[str, float]:
	if not project_names:
		return {}
	rows = frappe.get_list(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"project": ["in", project_names],
			"payment_type": payment_type,
		},
		fields=["project", f"sum({amount_field}) as total_amount"],
		group_by="project",
		limit_page_length=MAX_PROJECT_ROWS,
	)
	return {row.project: flt(row.total_amount) for row in rows if row.project}


def _columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "project", "label": _("Project"), "fieldtype": "Link", "options": "Project", "width": 145},
		{"fieldname": "project_name", "label": _("Project Name"), "fieldtype": "Data", "width": 180},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 90},
		{"fieldname": "project_type", "label": _("Type"), "fieldtype": "Link", "options": "Project Type", "width": 110},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 150},
		{"fieldname": "percent_complete", "label": _("Progress %"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "expected_start_date", "label": _("Start"), "fieldtype": "Date", "width": 95},
		{"fieldname": "expected_end_date", "label": _("Expected End"), "fieldtype": "Date", "width": 105},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "width": 75},
		{"fieldname": "sales_order_value", "label": _("Sales Order Value"), "fieldtype": "Currency", "options": "currency", "width": 125},
		{"fieldname": "billed_amount", "label": _("Billed"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "funds_received", "label": _("Funds Received"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "funds_paid", "label": _("Funds Paid"), "fieldtype": "Currency", "options": "currency", "width": 110},
		{"fieldname": "cash_funds_position", "label": _("Cash Funds Position"), "fieldtype": "Currency", "options": "currency", "width": 135},
		{"fieldname": "tracked_cost", "label": _("Tracked Cost"), "fieldtype": "Currency", "options": "currency", "width": 115},
		{"fieldname": "gross_margin", "label": _("Gross Margin"), "fieldtype": "Currency", "options": "currency", "width": 115},
		{"fieldname": "gross_margin_percent", "label": _("Margin %"), "fieldtype": "Percent", "width": 90},
	]
