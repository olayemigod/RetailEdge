from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from retailedge.branch_context import get_branch_query_filters

def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	return get_columns(), get_data(filters)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."))


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


def get_data(filters):
	query_filters = {}
	query_filters.update(
		(get_branch_query_filters(
			"RetailEdge Daily Sales Audit",
			user=frappe.session.user,
			company=filters.get("company"),
			branch=filters.get("branch"),
		).get("filters") or {})
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
	return frappe.get_all(
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
			"net_variance_amount",
			"audit_status",
			"audit_result",
			"clarification_required",
			"submitted_for_review_by",
			"submitted_for_review_on",
			"approved_by",
			"approved_on",
			"rejected_by",
			"rejected_on",
			"review_required",
		],
		limit_page_length=0,
		order_by="audit_date desc, creation desc",
	)
