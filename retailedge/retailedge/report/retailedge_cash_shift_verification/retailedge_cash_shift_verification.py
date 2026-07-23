from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retailedge.branch_context import get_branch_query_filters, has_doctype
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


EXCEPTION_CASH_STATUSES = {
	"Shortage",
	"Overage",
	"Needs Review",
	"Missing Closing Shift",
	"Missing Opening Shift",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	rows = get_data(filters)
	summary = append_report_metadata(
		get_report_summary(rows),
		get_edgesuite_metadata(filters, rows),
	)
	return get_columns(), rows, None, None, summary


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 155},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("POS Profile"), "fieldname": "pos_profile", "fieldtype": "Link", "options": "POS Profile", "width": 145},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Link", "options": "User", "width": 150},
		{"label": _("Opening Shift"), "fieldname": "opening_shift", "fieldtype": "Link", "options": "POS Opening Shift", "width": 160},
		{"label": _("Closing Shift"), "fieldname": "closing_shift", "fieldtype": "Link", "options": "POS Closing Shift", "width": 160},
		{"label": _("Shift Date"), "fieldname": "shift_date", "fieldtype": "Date", "width": 100},
		{"label": _("Opening Cash"), "fieldname": "opening_cash", "fieldtype": "Currency", "width": 110},
		{"label": _("Cash Sales"), "fieldname": "cash_sales", "fieldtype": "Currency", "width": 110},
		{"label": _("Included Cashier Expenses"), "fieldname": "included_cashier_expenses", "fieldtype": "Currency", "width": 165},
		{"label": _("Expected Cash"), "fieldname": "expected_cash", "fieldtype": "Currency", "width": 115},
		{"label": _("Actual Closing Cash"), "fieldname": "actual_closing_cash", "fieldtype": "Currency", "width": 145},
		{"label": _("Cash Variance"), "fieldname": "cash_variance", "fieldtype": "Currency", "width": 110},
		{"label": _("Cash Status"), "fieldname": "cash_status", "fieldtype": "Data", "width": 130},
		{"label": _("Eligible Cash Invoices"), "fieldname": "eligible_cash_invoices", "fieldtype": "Int", "width": 135},
		{"label": _("Synced Cash Invoices"), "fieldname": "synced_cash_invoices", "fieldtype": "Int", "width": 135},
		{"label": _("Daily Sales Audit"), "fieldname": "daily_sales_audit", "fieldtype": "Link", "options": "RetailEdge Daily Sales Audit", "width": 170},
		{"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	if not has_doctype("RetailEdge Daily Sales Audit"):
		return []

	query_filters = {}
	query_filters.update(
		(
			get_branch_query_filters(
				"RetailEdge Daily Sales Audit",
				user=frappe.session.user,
				company=filters.get("company"),
				branch=filters.get("branch"),
			).get("filters")
			or {}
		)
	)

	for fieldname in ("company", "branch", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"):
		value = filters.get(fieldname)
		if value and fieldname not in query_filters:
			query_filters[fieldname] = value

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["audit_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["audit_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["audit_date"] = ["<=", filters.get("to_date")]

	rows = frappe.get_all(
		"RetailEdge Daily Sales Audit",
		filters=query_filters,
		fields=[
			"name",
			"audit_date",
			"company",
			"branch",
			"pos_profile",
			"cashier",
			"pos_opening_shift",
			"pos_closing_shift",
			"opening_cash_amount",
			"cash_sales_amount",
			"cashier_expense_amount",
			"expected_cash_amount",
			"actual_closing_cash_amount",
			"cash_variance_amount",
			"audit_status",
		],
		limit_page_length=0,
		order_by="audit_date desc, creation desc",
	)

	result = []
	for row in rows:
		report_row = {
			"company": row.get("company"),
			"branch": row.get("branch"),
			"pos_profile": row.get("pos_profile"),
			"cashier": row.get("cashier"),
			"opening_shift": row.get("pos_opening_shift"),
			"closing_shift": row.get("pos_closing_shift"),
			"shift_date": row.get("audit_date"),
			"opening_cash": flt(row.get("opening_cash_amount")),
			"cash_sales": flt(row.get("cash_sales_amount")),
			"included_cashier_expenses": flt(row.get("cashier_expense_amount")),
			"expected_cash": flt(row.get("expected_cash_amount")),
			"actual_closing_cash": flt(row.get("actual_closing_cash_amount")),
			"cash_variance": flt(row.get("cash_variance_amount")),
			"daily_sales_audit": row.get("name"),
			"review_status": row.get("audit_status"),
		}
		report_row["cash_status"] = get_cash_status(report_row)
		report_row["eligible_cash_invoices"], report_row["synced_cash_invoices"] = get_cash_invoice_sync_counts(
			row.get("name")
		)
		if filters.get("cash_status") and report_row["cash_status"] != filters.get("cash_status"):
			continue
		if filters.get("review_status") and report_row.get("review_status") != filters.get("review_status"):
			continue
		if cint(filters.get("only_unsynced")) and report_row["eligible_cash_invoices"] == report_row["synced_cash_invoices"]:
			continue
		result.append(report_row)
	return result


def get_cash_status(row):
	if not row.get("opening_shift"):
		return "Missing Opening Shift"
	if not row.get("closing_shift"):
		return "Missing Closing Shift"
	variance = flt(row.get("cash_variance"))
	if variance == 0:
		return "Balanced"
	if variance < 0:
		return "Shortage"
	if variance > 0:
		return "Overage"
	return "Needs Review"


def get_report_summary(rows):
	if not rows:
		return []
	return [
		{
			"value": sum(flt(row.get("expected_cash")) for row in rows),
			"label": _("Expected Cash"),
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"value": sum(flt(row.get("actual_closing_cash")) for row in rows),
			"label": _("Actual Closing Cash"),
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"value": sum(flt(row.get("cash_variance")) for row in rows),
			"label": _("Cash Variance"),
			"datatype": "Currency",
			"indicator": "Red" if any(flt(row.get("cash_variance")) for row in rows) else "Green",
		},
		{
			"value": len([row for row in rows if row.get("cash_status") in EXCEPTION_CASH_STATUSES]),
			"label": _("Exceptions"),
			"datatype": "Int",
			"indicator": "Orange",
		},
	]


def get_edgesuite_metadata(filters, rows):
	shortages = [row for row in rows if row.get("cash_status") == "Shortage"]
	overages = [row for row in rows if row.get("cash_status") == "Overage"]
	missing_shifts = [
		row
		for row in rows
		if row.get("cash_status") in {"Missing Opening Shift", "Missing Closing Shift"}
	]
	unsynced_invoices = sum(
		max(cint(row.get("eligible_cash_invoices")) - cint(row.get("synced_cash_invoices")), 0)
		for row in rows
	)
	absolute_variance = sum(abs(flt(row.get("cash_variance"))) for row in rows)
	recommendations = []
	if missing_shifts:
		recommendations.append(
			recommendation(
				_("Complete missing shift records"),
				_("{0} cash verification row(s) are missing an opening or closing shift. Resolve the shift evidence before audit sign-off.").format(len(missing_shifts)),
				"danger",
			)
		)
	if shortages:
		recommendations.append(
			recommendation(
				_("Investigate cash shortages"),
				_("Review {0} shortage row(s), confirm counted cash and supporting expenses, and document the outcome in the linked daily audit.").format(len(shortages)),
				"danger",
			)
		)
	if overages:
		recommendations.append(
			recommendation(
				_("Explain cash overages"),
				_("Review {0} overage row(s) for omitted sales, incorrect counts, or timing differences.").format(len(overages)),
				"warning",
			)
		)
	if unsynced_invoices:
		recommendations.append(
			recommendation(
				_("Complete cash invoice verification sync"),
				_("{0} eligible cash invoice(s) have not yet been reflected as cash verified by shift.").format(unsynced_invoices),
				"warning",
			)
		)

	if missing_shifts or shortages:
		status_label = _("Cash-control exceptions require action")
		status_tone = "danger"
	elif overages or unsynced_invoices or absolute_variance:
		status_label = _("Cash verification requires review")
		status_tone = "warning"
	else:
		status_label = _("Cash verification balanced in current view")
		status_tone = "success"

	return build_report_metadata(
		title=_("Cash Shift Verification"),
		icon="cash",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("pos_profile", _("POS Profile")),
			("cashier", _("Cashier")),
			("cash_status", _("Cash Status")),
			("review_status", _("Review Status")),
			("only_unsynced", _("Only Unsynced")),
		),
		row_count=len(rows),
		empty_message=_("No cash-shift verification rows matched the selected filters."),
		empty_suggestions=(
			_("Choose another date range, company, branch, POS Profile, cashier, or cash status."),
			_("Confirm that daily sales audits and their opening and closing shift links exist for the selected context."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Expected Cash"),
			_("Actual Closing Cash"),
			_("Cash Variance"),
			_("Exceptions"),
		),
		status_label=status_label,
		status_tone=status_tone,
	)


def get_cash_invoice_sync_counts(daily_sales_audit):
	if not daily_sales_audit or not has_doctype("RetailEdge Daily Sales Audit Invoice Line"):
		return 0, 0
	try:
		rows = frappe.get_all(
			"RetailEdge Daily Sales Audit Invoice Line",
			filters={"parent": daily_sales_audit, "parenttype": "RetailEdge Daily Sales Audit"},
			fields=["sales_invoice"],
			limit_page_length=0,
		)
	except Exception:
		return 0, 0
	invoices = [row.get("sales_invoice") for row in rows if row.get("sales_invoice")]
	if not invoices:
		return 0, 0
	try:
		docs = frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", invoices]},
			fields=["name", "retailedge_payment_verification_status"],
			limit_page_length=0,
		)
	except Exception:
		return len(invoices), 0
	eligible = len(docs)
	synced = len([row for row in docs if row.get("retailedge_payment_verification_status") == "Cash Verified by Shift"])
	return eligible, synced
