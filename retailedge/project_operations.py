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
MAX_TIMELINE_ROWS = 200

TIMELINE_DOCTYPES: tuple[dict[str, str], ...] = (
	{"doctype": "Sales Order", "kind": "Revenue", "label": "Sales Order"},
	{"doctype": "Sales Invoice", "kind": "Revenue", "label": "Sales Invoice"},
	{"doctype": "Purchase Invoice", "kind": "Cost", "label": "Purchase Invoice"},
	{"doctype": "Expense Claim", "kind": "Cost", "label": "Expense Claim"},
	{"doctype": "Stock Entry", "kind": "Stock", "label": "Stock Entry"},
)


def _assert_read(doctype: str, name: str | None = None) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to read {0}.").format(_(doctype)), frappe.PermissionError)


def _project_company_currency(company: str) -> str:
	return str(frappe.db.get_value("Company", company, "default_currency") or "")


def _has_field(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _project_payment_rows(project: str, *, payment_type: str | None = None, branch: str | None = None) -> list[Any]:
	_assert_read(PAYMENT_ENTRY_DOCTYPE)
	filters: dict[str, Any] = {"docstatus": 1, "project": project}
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


def _date_field_for(doctype: str) -> str:
	for fieldname in ("posting_date", "transaction_date", "expense_approver_date", "creation"):
		if fieldname == "creation" or _has_field(doctype, fieldname):
			return fieldname
	return "creation"


def _branch_field_for(doctype: str) -> str | None:
	for fieldname in ("retailedge_branch", "branch"):
		if _has_field(doctype, fieldname):
			return fieldname
	return None


def _project_timeline_rows(project: str, *, branch: str | None = None) -> list[dict[str, Any]]:
	"""Build a read-only timeline from native ERPNext documents carrying Project.

	When Branch scope is requested, document types without a branch attribution
	field are omitted rather than widened to company/project-wide results.
	Cancelled documents are always excluded.
	"""
	rows: list[dict[str, Any]] = []
	for spec in TIMELINE_DOCTYPES:
		doctype = spec["doctype"]
		if not frappe.db.exists("DocType", doctype) or not _has_field(doctype, "project"):
			continue
		if not frappe.has_permission(doctype, "read"):
			continue

		branch_field = _branch_field_for(doctype)
		if branch and not branch_field:
			continue

		date_field = _date_field_for(doctype)
		filters: dict[str, Any] = {"project": project, "docstatus": ["<", 2]}
		if branch and branch_field:
			filters[branch_field] = branch

		fields = ["name", "docstatus", date_field]
		for candidate in ("status", "company", "customer", "supplier", "grand_total", "base_grand_total"):
			if _has_field(doctype, candidate):
				fields.append(candidate)
		if branch_field:
			fields.append(branch_field)

		for row in frappe.get_list(
			doctype,
			filters=filters,
			fields=fields,
			order_by=f"{date_field} desc, name desc",
			limit_page_length=MAX_TIMELINE_ROWS,
		):
			amount = flt(getattr(row, "base_grand_total", 0) or getattr(row, "grand_total", 0))
			rows.append(
				{
					"doctype": doctype,
					"name": row.name,
					"kind": spec["kind"],
					"label": spec["label"],
					"date": getattr(row, date_field, None),
					"status": getattr(row, "status", "") or ("Submitted" if getattr(row, "docstatus", 0) == 1 else "Draft"),
					"party": getattr(row, "customer", "") or getattr(row, "supplier", "") or "",
					"amount": amount,
					"branch": getattr(row, branch_field, "") if branch_field else "",
					"route": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{row.name}",
				}
			)

	rows.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("name") or "")), reverse=True)
	return rows[:MAX_TIMELINE_ROWS]


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
	branch_field = _payment_branch_field()

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
			"branch": getattr(row, branch_field, "") if branch_field else "",
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
	timeline = _project_timeline_rows(project, branch=branch or None)

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
		"timeline": timeline,
		"timeline_count": len(timeline),
		"source_of_truth": {
			"project": PROJECT_DOCTYPE,
			"cash": PAYMENT_ENTRY_DOCTYPE,
			"timeline": "Native ERPNext documents carrying the Project accounting/operational link.",
			"ledger_policy": "ERPNext native documents only; no RetailEdge project wallet or shadow ledger.",
		},
		"routes": {
			"project": f"/app/project/{doc.name}",
			"payment_entries": f"/app/payment-entry?project={doc.name}",
		},
	}
