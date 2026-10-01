from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from retailedge.coreedge_sales_quota_reconciliation import get_quota_reconciliation_rows


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("company", frappe.defaults.get_user_default("Company") or "")
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("include_finalized", 0)

	result = get_quota_reconciliation_rows(filters, limit=500)
	rows = result.get("rows") or []
	for row in rows:
		row["quota_operation"] = row.get("name")

	message = None
	if result.get("truncated"):
		message = _(
			"Showing the first 500 scoped quota operations. Narrow the filters before making review decisions."
		)
	elif not rows:
		message = _("No sales quota reconciliation rows were found for the selected filters.")

	return (
		get_columns(),
		rows,
		message,
		None,
		get_report_summary(result.get("summary") or {}),
	)


def get_columns():
	return [
		{
			"label": _("Quota Operation"),
			"fieldname": "quota_operation",
			"fieldtype": "Link",
			"options": "RetailEdge CoreEdge Quota Operation",
			"width": 190,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{
			"label": _("Source Type"),
			"fieldname": "source_doctype",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Source Document"),
			"fieldname": "source_name",
			"fieldtype": "Dynamic Link",
			"options": "source_doctype",
			"width": 170,
		},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Entitlement"), "fieldname": "entitlement_key", "fieldtype": "Data", "width": 160},
		{"label": _("Units"), "fieldname": "units", "fieldtype": "Int", "width": 70},
		{
			"label": _("Reservation"),
			"fieldname": "reservation_reference",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Reservation Expires"),
			"fieldname": "reservation_expires_on",
			"fieldtype": "Datetime",
			"width": 155,
		},
		{
			"label": _("CoreEdge Case"),
			"fieldname": "reconciliation_case_reference",
			"fieldtype": "Data",
			"width": 190,
		},
		{
			"label": _("Case Status"),
			"fieldname": "reconciliation_case_status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Case Submitted"),
			"fieldname": "reconciliation_submitted_on",
			"fieldtype": "Datetime",
			"width": 155,
		},
		{"label": _("Reason Code"), "fieldname": "reason_code", "fieldtype": "Data", "width": 190},
		{"label": _("Finalize Attempts"), "fieldname": "attempt_count", "fieldtype": "Int", "width": 110},
		{
			"label": _("Last Attempt"),
			"fieldname": "last_attempt_on",
			"fieldtype": "Datetime",
			"width": 150,
		},
		{"label": _("Last Error"), "fieldname": "last_error", "fieldtype": "Small Text", "width": 260},
		{
			"label": _("Recommended Action"),
			"fieldname": "recommended_action",
			"fieldtype": "Small Text",
			"width": 250,
		},
	]


def get_report_summary(summary):
	return [
		{
			"label": _("Needs Review"),
			"value": summary.get("needs_review", 0),
			"datatype": "Int",
			"indicator": "Red",
		},
		{
			"label": _("Pending Finalize"),
			"value": summary.get("pending_finalize", 0),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"label": _("Finalized"),
			"value": summary.get("finalized", 0),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"label": _("Visible Rows"),
			"value": summary.get("visible_rows", 0),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]
