from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.advanced_payments import _require_payment_branch_field
from retailedge.branch_context import validate_user_branch_access

MAX_ROWS = 2000


def execute(filters: dict[str, Any] | None = None):
	filters = frappe._dict(filters or {})
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if not frappe.has_permission("Payment Entry", "read"):
		frappe.throw(_("You do not have permission to read Payment Entries."), frappe.PermissionError)
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to read Company {0}.").format(company), frappe.PermissionError)

	branch = str(filters.get("branch") or "").strip()
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	query_filters: dict[str, Any] = {
		"docstatus": 1,
		"payment_type": "Receive",
		"party_type": "Customer",
		"company": company,
		"unallocated_amount": [">", 0],
	}
	if filters.get("customer"):
		query_filters["party"] = filters.customer
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."))
		query_filters["posting_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		query_filters["posting_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		query_filters["posting_date"] = ["<=", filters.to_date]

	branch_field = _require_payment_branch_field(branch)
	if branch and branch_field:
		query_filters[branch_field] = branch

	fields = [
		"name",
		"posting_date",
		"party",
		"company",
		"paid_amount",
		"unallocated_amount",
		"paid_from_account_currency",
		"mode_of_payment",
		"reference_no",
		"reference_date",
	]
	if branch_field:
		fields.append(branch_field)

	payments = frappe.get_list(
		"Payment Entry",
		filters=query_filters,
		fields=fields,
		order_by="posting_date desc, name desc",
		limit_page_length=MAX_ROWS,
	)
	rows = []
	for payment in payments:
		received = flt(payment.paid_amount)
		available = flt(payment.unallocated_amount)
		rows.append(
			{
				"payment_entry": payment.name,
				"posting_date": payment.posting_date,
				"customer": payment.party,
				"branch": getattr(payment, branch_field, "") if branch_field else "",
				"currency": payment.paid_from_account_currency or "",
				"received_amount": received,
				"allocated_amount": max(received - available, 0),
				"available_amount": available,
				"mode_of_payment": payment.mode_of_payment or "",
				"reference_no": payment.reference_no or "",
				"reference_date": payment.reference_date,
			}
		)

	columns = [
		{"fieldname": "payment_entry", "label": _("Payment Entry"), "fieldtype": "Link", "options": "Payment Entry", "width": 180},
		{"fieldname": "posting_date", "label": _("Posting Date"), "fieldtype": "Date", "width": 105},
		{"fieldname": "customer", "label": _("Customer"), "fieldtype": "Link", "options": "Customer", "width": 180},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data", "width": 140},
		{"fieldname": "currency", "label": _("Currency"), "fieldtype": "Data", "width": 85},
		{"fieldname": "received_amount", "label": _("Receipt Amount"), "fieldtype": "Currency", "options": "currency", "width": 130},
		{"fieldname": "allocated_amount", "label": _("Allocated"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "available_amount", "label": _("Available Advance"), "fieldtype": "Currency", "options": "currency", "width": 140},
		{"fieldname": "mode_of_payment", "label": _("Mode of Payment"), "fieldtype": "Link", "options": "Mode of Payment", "width": 130},
		{"fieldname": "reference_no", "label": _("Reference No"), "fieldtype": "Data", "width": 120},
		{"fieldname": "reference_date", "label": _("Reference Date"), "fieldtype": "Date", "width": 105},
	]

	message = _("Showing current submitted customer receipts with unapplied value. Allocated is the already-consumed portion of each currently open receipt; fully consumed receipts are intentionally excluded.")
	return columns, rows, message
