from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.branch_context import validate_user_branch_access
from retailedge.advanced_payments import _payment_branch_field

PROJECT_DOCTYPE = "Project"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
MAX_PAYMENT_ROWS = 2000


def _assert_read(doctype: str, name: str | None = None) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _project_company_currency(company: str) -> str:
	return str(frappe.db.get_value("Company", company, "default_currency") or "")


def _project_payment_rows(project: str, *, payment_type: str | None = None, branch: str | None = None) -> list[Any]:
	_assert_read(PAYMENT_ENTRY_DOCTYPE)
	filters: dict[str, Any] = {
		"docstatus": 1,
		"project": project,
	}
	if payment_type:
		filters["payment_type"] = payment_type

	branch_field = _payment_branch_field()
	if branch:
		if not branch_field:
			frappe.throw(
				_("RetailEdge Payment Entry branch attribution is not available. Run bench migrate before using Branch-scoped Project Funds."),
			)
		filters[branch_field] = branch

	fields = [
		"name",
		"posting_date",
		"payment_type",
		"party_type",
		"party",
		"company",
		"paid_amount",
		"received_amount",
		"base_paid_amount",
		"base_received_amount",
		"unallocated_amount",
		"mode_of_payment",
		"reference_no",
		"reference_date",
	]
	if branch_field:
		fields.append(branch_field)

	return frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=fields,
		order_by="posting_date desc, name desc",
		limit_page_length=MAX_PAYMENT_ROWS,
	)


@frappe.whitelist()
def get_project_funds_context(project: str, branch: str | None = None) -> dict[str, Any]:
	"""Return a permission-aware project operations/funds snapshot from ERPNext truth.

	RetailEdge does not maintain a project wallet or shadow ledger. Project billing,
	costing and margin come from the ERPNext Project document; cash receipts and
	payments come from submitted ERPNext Payment Entries explicitly linked to the
	Project accounting dimension.
	"""
	_assert_read(PROJECT_DOCTYPE, project)
	doc = frappe.get_doc(PROJECT_DOCTYPE, project)
	if not doc.company:
		frappe.throw(_("Project {0} has no Company.").format(project))
	_assert_read("Company", doc.company)

	branch = str(branch or "").strip()
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=doc.company, throw=True)

	payments = _project_payment_rows(project, branch=branch or None)
	company_currency = _project_company_currency(doc.company)

	customer_receipts = []
	project_payments = []
	funds_received = 0.0
	funds_paid_out = 0.0
	unallocated_receipts = 0.0

	for row in payments:
		payment_type = str(row.payment_type or "")
		base_received = flt(row.base_received_amount or row.received_amount)
		base_paid = flt(row.base_paid_amount or row.paid_amount)
		entry = {
			"name": row.name,
			"posting_date": row.posting_date,
			"payment_type": payment_type,
			"party_type": row.party_type or "",
			"party": row.party or "",
			"company": row.company,
			"received_amount": base_received,
			"paid_amount": base_paid,
			"unallocated_amount": flt(row.unallocated_amount),
			"mode_of_payment": row.mode_of_payment or "",
			"reference_no": row.reference_no or "",
			"reference_date": row.reference_date,
			"branch": getattr(row, _payment_branch_field(), "") if _payment_branch_field() else "",
			"route": f"/app/payment-entry/{row.name}",
		}
		if payment_type == "Receive":
			funds_received += base_received
			unallocated_receipts += flt(row.unallocated_amount)
			customer_receipts.append(entry)
		elif payment_type == "Pay":
			funds_paid_out += base_paid
			project_payments.append(entry)

	tracked_cost = (
		flt(getattr(doc, "total_purchase_cost", 0))
		+ flt(getattr(doc, "total_consumed_material_cost", 0))
		+ flt(getattr(doc, "total_costing_amount", 0))
	)

	return {
		"project": doc.name,
		"project_name": doc.project_name,
		"status": doc.status,
		"project_type": doc.project_type or "",
		"company": doc.company,
		"customer": doc.customer or "",
		"cost_center": doc.cost_center or "",
		"branch": branch,
		"currency": company_currency,
		"percent_complete": flt(doc.percent_complete),
		"expected_start_date": doc.expected_start_date,
		"expected_end_date": doc.expected_end_date,
		"estimated_cost": flt(doc.estimated_costing),
		"sales_order_value": flt(doc.total_sales_amount),
		"billed_amount": flt(doc.total_billed_amount),
		"timesheet_billable_amount": flt(doc.total_billable_amount),
		"purchase_cost": flt(doc.total_purchase_cost),
		"consumed_material_cost": flt(doc.total_consumed_material_cost),
		"timesheet_cost": flt(doc.total_costing_amount),
		"tracked_cost": tracked_cost,
		"gross_margin": flt(doc.gross_margin),
		"gross_margin_percent": flt(doc.per_gross_margin),
		"funds_received": funds_received,
		"funds_paid_out": funds_paid_out,
		"cash_funds_position": funds_received - funds_paid_out,
		"unallocated_receipts": unallocated_receipts,
		"customer_receipts": customer_receipts,
		"project_payments": project_payments,
		"payment_count": len(payments),
		"source_of_truth": {
			"project": PROJECT_DOCTYPE,
			"cash": PAYMENT_ENTRY_DOCTYPE,
			"ledger_policy": "ERPNext native documents only; no RetailEdge project wallet or shadow ledger.",
		},
		"routes": {
			"project": f"/app/project/{doc.name}",
			"payment_entries": f"/app/payment-entry?project={doc.name}",
		},
	}
