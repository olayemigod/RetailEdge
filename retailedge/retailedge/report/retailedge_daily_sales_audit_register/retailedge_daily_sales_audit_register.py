from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.branch_context import get_branch_query_filters
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_data(filters)
	summary = append_report_metadata(
		get_report_summary(data),
		get_edgesuite_metadata(filters, data),
	)
	return get_columns(), data, None, None, summary


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


def get_report_summary(rows):
	total_cash_sales = sum(flt(row.get("cash_sales_amount")) for row in rows)
	total_expected_cash = sum(flt(row.get("expected_cash_amount")) for row in rows)
	total_actual_cash = sum(flt(row.get("actual_closing_cash_amount")) for row in rows)
	total_absolute_variance = sum(abs(flt(row.get("net_variance_amount"))) for row in rows)
	review_required_count = sum(1 for row in rows if _truthy(row.get("review_required")))
	clarification_count = sum(1 for row in rows if _truthy(row.get("clarification_required")))
	return [
		{"value": total_cash_sales, "label": _("Cash Sales"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_expected_cash, "label": _("Expected Cash"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_actual_cash, "label": _("Actual Closing Cash"), "datatype": "Currency", "indicator": "Green"},
		{
			"value": total_absolute_variance,
			"label": _("Absolute Variance"),
			"datatype": "Currency",
			"indicator": "Red" if total_absolute_variance else "Green",
		},
		{
			"value": review_required_count,
			"label": _("Review Required"),
			"datatype": "Int",
			"indicator": "Orange" if review_required_count else "Green",
		},
		{
			"value": clarification_count,
			"label": _("Clarification Required"),
			"datatype": "Int",
			"indicator": "Orange" if clarification_count else "Green",
		},
	]


def get_edgesuite_metadata(filters, rows):
	total_absolute_variance = sum(abs(flt(row.get("net_variance_amount"))) for row in rows)
	review_required_count = sum(1 for row in rows if _truthy(row.get("review_required")))
	clarification_count = sum(1 for row in rows if _truthy(row.get("clarification_required")))
	recommendations = []
	if total_absolute_variance:
		recommendations.append(
			recommendation(
				_("Investigate cash variance"),
				_("Open the affected daily audits and reconcile opening cash, cash sales, expenses, expected cash, and closing count evidence."),
				"danger",
			)
		)
	if review_required_count:
		recommendations.append(
			recommendation(
				_("Complete audit review"),
				_("{0} daily audit(s) still require reviewer action.").format(review_required_count),
				"warning",
			)
		)
	if clarification_count:
		recommendations.append(
			recommendation(
				_("Resolve clarification requests"),
				_("Obtain and record supporting explanations for {0} daily audit(s).").format(clarification_count),
				"warning",
			)
		)

	return build_report_metadata(
		title=_("Daily Sales Audit Register"),
		icon="assessment",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("pos_profile", _("POS Profile")),
			("cashier", _("Cashier")),
			("audit_status", _("Audit Status")),
			("audit_result", _("Audit Result")),
		),
		row_count=len(rows),
		empty_message=_("No daily sales audit matched the selected filters."),
		empty_suggestions=(
			_("Choose another date range, branch, cashier, audit status, or audit result."),
			_("Confirm that daily audits were created from the correct POS opening and closing shifts."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Cash Sales"),
			_("Expected Cash"),
			_("Actual Closing Cash"),
			_("Absolute Variance"),
			_("Review Required"),
			_("Clarification Required"),
		),
		status_label=_("Review required") if recommendations else _("Audits clear in current view"),
		status_tone="warning" if recommendations else "success",
	)


def _truthy(value):
	return value is True or str(value or "").strip().lower() in {"1", "true", "yes"}
