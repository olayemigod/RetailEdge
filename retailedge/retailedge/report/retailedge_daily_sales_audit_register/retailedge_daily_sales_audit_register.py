from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.branch_context import get_branch_query_filters
from retailedge.cash_deposit_audit import get_submitted_deposit_totals


def execute(filters=None):
	filters = frappe._dict(filters or {})
	preset = filters.get("date_range_preset")
	if preset and preset != "Custom Period":
		from retailedge.reporting.date_ranges import get_preset_dates

		preset_from, preset_to = get_preset_dates(preset)
		if preset_from and preset_to:
			filters["from_date"] = str(preset_from)
			filters["to_date"] = str(preset_to)

	validate_filters(filters)
	return get_columns(), get_data(filters)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."))
		if (getdate(filters.to_date) - getdate(filters.from_date)).days + 1 > 60:
			frappe.msgprint(_("Large date ranges may take longer to load."), alert=True)


def get_columns():
	return [
		{"label": _("Audit"), "fieldname": "name", "fieldtype": "Link", "options": "RetailEdge Daily Sales Audit", "width": 180},
		{"label": _("Audit Date"), "fieldname": "audit_date", "fieldtype": "Date", "width": 105},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("POS Profile"), "fieldname": "pos_profile", "fieldtype": "Link", "options": "POS Profile", "width": 150},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Opening Shift"), "fieldname": "pos_opening_shift", "fieldtype": "Link", "options": "POS Opening Shift", "width": 160},
		{"label": _("Closing Shift"), "fieldname": "pos_closing_shift", "fieldtype": "Link", "options": "POS Closing Shift", "width": 160},
		{"label": _("Opening Cash"), "fieldname": "opening_cash_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cash Sales"), "fieldname": "cash_sales_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cashier Expenses"), "fieldname": "cashier_expense_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Cash Deposits"), "fieldname": "cash_deposit_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Expected Cash"), "fieldname": "expected_cash_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual Closing Cash"), "fieldname": "actual_closing_cash_amount", "fieldtype": "Currency", "width": 150},
		{"label": _("Cash Variance"), "fieldname": "cash_variance_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Net Variance"), "fieldname": "net_variance_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Audit Status"), "fieldname": "audit_status", "fieldtype": "Data", "width": 130},
		{"label": _("Audit Result"), "fieldname": "audit_result", "fieldtype": "Data", "width": 130},
		{"label": _("Clarification Required"), "fieldname": "clarification_required", "fieldtype": "Check", "width": 130},
		{"label": _("Submitted By"), "fieldname": "submitted_for_review_by", "fieldtype": "Link", "options": "User", "width": 130},
		{"label": _("Submitted On"), "fieldname": "submitted_for_review_on", "fieldtype": "Datetime", "width": 145},
		{"label": _("Approved By"), "fieldname": "approved_by", "fieldtype": "Link", "options": "User", "width": 130},
		{"label": _("Approved On"), "fieldname": "approved_on", "fieldtype": "Datetime", "width": 145},
		{"label": _("Rejected By"), "fieldname": "rejected_by", "fieldtype": "Link", "options": "User", "width": 130},
		{"label": _("Rejected On"), "fieldname": "rejected_on", "fieldtype": "Datetime", "width": 145},
		{"label": _("Review Required"), "fieldname": "review_required", "fieldtype": "Check", "width": 110},
	]


def get_data(filters, limit_page_length=0):
	query_filters = {}
	query_filters.update(
		get_branch_query_filters(
			"RetailEdge Daily Sales Audit",
			user=frappe.session.user,
			company=filters.get("company"),
			branch=filters.get("branch"),
		).get("filters")
		or {}
	)
	for fieldname in ("company", "branch", "pos_profile", "cashier", "audit_status", "audit_result"):
		value = filters.get(fieldname)
		if value and fieldname not in query_filters:
			query_filters[fieldname] = value
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["audit_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["audit_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["audit_date"] = ["<=", filters["to_date"]]
	rows = frappe.get_all(
		"RetailEdge Daily Sales Audit",
		filters=query_filters,
		fields=[
			"name", "audit_date", "company", "branch", "pos_profile", "cashier",
			"pos_opening_shift", "pos_closing_shift", "opening_cash_amount", "cash_sales_amount",
			"cashier_expense_amount", "expected_cash_amount", "actual_closing_cash_amount",
			"cash_variance_amount", "net_variance_amount", "audit_status", "audit_result",
			"clarification_required", "submitted_for_review_by", "submitted_for_review_on",
			"approved_by", "approved_on", "rejected_by", "rejected_on", "review_required",
		],
		limit_page_length=limit_page_length,
		order_by="audit_date desc, creation desc",
	)
	deposit_totals = get_submitted_deposit_totals(
		[row.get("pos_opening_shift") for row in rows],
		company=filters.get("company"),
	)
	for row in rows:
		deposit_amount = flt(deposit_totals.get(row.get("pos_opening_shift")))
		row["cash_deposit_amount"] = deposit_amount
		row["expected_cash_amount"] = (
			flt(row.get("opening_cash_amount"))
			+ flt(row.get("cash_sales_amount"))
			- flt(row.get("cashier_expense_amount"))
			- deposit_amount
		)
		row["cash_variance_amount"] = flt(row.get("actual_closing_cash_amount")) - flt(row.get("expected_cash_amount"))
		row["net_variance_amount"] = flt(row.get("cash_variance_amount"))
	return rows
