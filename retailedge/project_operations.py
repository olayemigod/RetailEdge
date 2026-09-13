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
	{"doctype": "Material Request", "kind": "Procurement", "label": "Material Request"},
	{"doctype": "Purchase Order", "kind": "Procurement", "label": "Purchase Order"},
	{"doctype": "Purchase Receipt", "kind": "Procurement", "label": "Purchase Receipt"},
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
				_("Payment Entry branch attribution is not available. Run bench migrate before using Branch-scoped Project Funds."),
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
	for fieldname in ("posting_date", "transaction_date", "schedule_date", "expense_approver_date", "creation"):
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

	Only parent DocTypes with an actual Project field participate. Procurement
	documents whose Project exists only on child rows are omitted rather than
	showing a whole-document amount that could include unrelated projects.
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
	"""Return a permission-aware project operations/funds snapshot from ERPNext truth."""
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

	project_cash_in_rows: list[dict[str, Any]] = []
	project_cash_out_rows: list[dict[str, Any]] = []
	project_cash_in = 0.0
	project_cash_out = 0.0
	customer_cash_in = 0.0
	supplier_cash_out = 0.0
	unallocated_receipts = 0.0
	branch_field = _payment_branch_field()

	for row in payments:
		payment_type = str(row.payment_type or "")
		party_type = str(row.party_type or "")
		base_received = flt(row.base_received_amount or row.received_amount)
		base_paid = flt(row.base_paid_amount or row.paid_amount)
		entry = {
			"name": row.name,
			"posting_date": row.posting_date,
			"payment_type": payment_type,
			"party_type": party_type,
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
			project_cash_in += base_received
			unallocated_receipts += flt(row.unallocated_amount)
			project_cash_in_rows.append(entry)
			if party_type == "Customer":
				customer_cash_in += base_received
		elif payment_type == "Pay":
			project_cash_out += base_paid
			project_cash_out_rows.append(entry)
			if party_type == "Supplier":
				supplier_cash_out += base_paid

	purchase_cost = flt(getattr(doc, "total_purchase_cost", 0))
	consumed_material_cost = flt(getattr(doc, "total_consumed_material_cost", 0))
	timesheet_cost = flt(getattr(doc, "total_costing_amount", 0))
	tracked_cost = purchase_cost + consumed_material_cost + timesheet_cost
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
		"purchase_cost": purchase_cost,
		"consumed_material_cost": consumed_material_cost,
		"timesheet_cost": timesheet_cost,
		"tracked_cost": tracked_cost,
		"tracked_cost_basis": "ERPNext Project cost components: purchase + consumed material + timesheet costing.",
		"gross_margin": flt(doc.gross_margin),
		"gross_margin_percent": flt(doc.per_gross_margin),
		"project_cash_in": project_cash_in,
		"project_cash_out": project_cash_out,
		"net_project_cash": project_cash_in - project_cash_out,
		"customer_cash_in": customer_cash_in,
		"supplier_cash_out": supplier_cash_out,
		"project_cash_in_rows": project_cash_in_rows,
		"project_cash_out_rows": project_cash_out_rows,
		"funds_received": project_cash_in,
		"funds_paid_out": project_cash_out,
		"cash_funds_position": project_cash_in - project_cash_out,
		"customer_receipts": project_cash_in_rows,
		"project_payments": project_cash_out_rows,
		"unallocated_receipts": unallocated_receipts,
		"payment_count": len(payments),
		"timeline": timeline,
		"timeline_count": len(timeline),
		"scope": {
			"branch": branch,
			"project_totals": "Whole Project across all branches",
			"cash_and_timeline": f"Branch {branch}" if branch else "Whole Project",
			"branch_scope_note": (
				"Branch filtering applies to branch-attributed Payment Entries and timeline documents only; ERPNext Project billing, costing and margin totals remain whole-project values."
				if branch
				else "No Branch filter is active; Project totals, cash movements and timeline use the whole Project scope."
			),
		},
		"source_of_truth": {
			"project": PROJECT_DOCTYPE,
			"cash": PAYMENT_ENTRY_DOCTYPE,
			"timeline": "Native ERPNext documents carrying a safe parent Project accounting/operational link.",
			"cash_policy": "Cash In/Out means submitted project-linked Payment Entry movement; it is not revenue, expense, profit, or a bank balance.",
			"cost_policy": "Tracked Cost is a transparent sum of ERPNext Project purchase, consumed-material and timesheet costing fields; ERPNext remains authoritative.",
			"ledger_policy": "ERPNext native documents only; no custom project wallet or shadow ledger.",
		},
		"routes": {
			"project": f"/app/project/{doc.name}",
			"payment_entries": f"/app/payment-entry?project={doc.name}",
		},
	}
