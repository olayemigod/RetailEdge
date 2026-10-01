from __future__ import annotations

from collections import Counter

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime, time_diff_in_hours

from retailedge.coreedge_sales_quota import OPERATION_DOCTYPE


_MAX_ROWS = 1000


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_validate_filters(filters)
	rows, truncated = get_data(filters)
	message = (
		_("Showing the first {0} matching quota operations. Narrow the filters for a complete view.").format(
			_MAX_ROWS
		)
		if truncated
		else None
	)
	return (
		get_columns(),
		rows,
		message,
		get_chart_data(rows),
		get_report_summary(rows, truncated=truncated),
	)


def _validate_filters(filters) -> None:
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."), frappe.ValidationError)


def get_columns():
	return [
		{
			"label": _("Operation"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": OPERATION_DOCTYPE,
			"width": 185,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 125},
		{"label": _("Source Type"), "fieldname": "source_doctype", "fieldtype": "Data", "width": 115},
		{
			"label": _("Source Document"),
			"fieldname": "source_name",
			"fieldtype": "Dynamic Link",
			"options": "source_doctype",
			"width": 175,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 160,
		},
		{
			"label": _("Branch"),
			"fieldname": "branch",
			"fieldtype": "Link",
			"options": "Branch",
			"width": 140,
		},
		{"label": _("Entitlement"), "fieldname": "entitlement_key", "fieldtype": "Data", "width": 170},
		{
			"label": _("Reservation"),
			"fieldname": "reservation_reference",
			"fieldtype": "Data",
			"width": 175,
		},
		{"label": _("Reserved On"), "fieldname": "reserved_on", "fieldtype": "Datetime", "width": 150},
		{
			"label": _("Reservation Expires"),
			"fieldname": "reservation_expires_on",
			"fieldtype": "Datetime",
			"width": 150,
		},
		{"label": _("Finalized On"), "fieldname": "finalized_on", "fieldtype": "Datetime", "width": 150},
		{"label": _("Attempts"), "fieldname": "attempt_count", "fieldtype": "Int", "width": 85},
		{"label": _("Age Hours"), "fieldname": "age_hours", "fieldtype": "Float", "precision": 1, "width": 90},
		{"label": _("Reason Code"), "fieldname": "reason_code", "fieldtype": "Data", "width": 190},
		{"label": _("Last Error"), "fieldname": "last_error", "fieldtype": "Small Text", "width": 260},
		{"label": _("Next Action"), "fieldname": "next_action", "fieldtype": "Data", "width": 210},
	]


def get_data(filters) -> tuple[list[dict], bool]:
	query_filters = _query_filters(filters)
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=query_filters,
		fields=[
			"name",
			"status",
			"source_doctype",
			"source_name",
			"company",
			"branch",
			"entitlement_key",
			"reservation_reference",
			"reservation_expires_on",
			"warning",
			"reason_code",
			"remote_message",
			"reserved_on",
			"finalized_on",
			"last_attempt_on",
			"attempt_count",
			"last_error",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=_MAX_ROWS + 1,
	)
	truncated = len(rows) > _MAX_ROWS
	rows = rows[:_MAX_ROWS]
	now = get_datetime(now_datetime())
	for row in rows:
		created = get_datetime(row.get("creation")) if row.get("creation") else now
		row["age_hours"] = round(max(0.0, time_diff_in_hours(now, created)), 1)
		row["next_action"] = get_next_action(row)
	return rows, truncated


def _query_filters(filters) -> dict:
	query_filters: dict = {}
	status = str(filters.get("status") or "").strip()
	if status:
		query_filters["status"] = status
	elif _is_truthy(filters.get("needs_attention_only", 1)):
		query_filters["status"] = ["in", ["Pending Finalize", "Needs Review"]]

	for fieldname in ("company", "branch", "source_doctype", "entitlement_key"):
		value = str(filters.get(fieldname) or "").strip()
		if value:
			query_filters[fieldname] = value

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	if from_date and to_date:
		query_filters["creation"] = [
			"between",
			[f"{getdate(from_date)} 00:00:00", f"{getdate(to_date)} 23:59:59"],
		]
	elif from_date:
		query_filters["creation"] = [">=", f"{getdate(from_date)} 00:00:00"]
	elif to_date:
		query_filters["creation"] = ["<=", f"{getdate(to_date)} 23:59:59"]
	return query_filters


def get_next_action(row) -> str:
	status = str(row.get("status") or "")
	reason = str(row.get("reason_code") or "")
	last_error = str(row.get("last_error") or "")

	if status == "Pending Finalize":
		return _("Retry Finalize")
	if status == "Finalized":
		return _("No action")
	if reason == "FAIL_OPEN_UNRESERVED":
		return _("Reconcile central usage")
	if reason in {"RESERVATION_EXPIRED", "RESERVATION_ALREADY_RELEASED", "RESERVATION_NOT_FOUND"}:
		return _("Platform review required")
	if reason == "USAGE_RESERVATION_ACCESS_DENIED":
		return _("Check Service Client access")
	if "source document" in last_error.lower():
		return _("Verify source document")
	return _("Investigate and reconcile")


def get_report_summary(rows, *, truncated: bool):
	counts = Counter(str(row.get("status") or "Unknown") for row in rows)
	return [
		{
			"value": len(rows),
			"label": _("Visible Operations"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": counts.get("Needs Review", 0),
			"label": _("Needs Review"),
			"datatype": "Int",
			"indicator": "Red" if counts.get("Needs Review", 0) else "Green",
		},
		{
			"value": counts.get("Pending Finalize", 0),
			"label": _("Pending Finalize"),
			"datatype": "Int",
			"indicator": "Orange" if counts.get("Pending Finalize", 0) else "Green",
		},
		{
			"value": counts.get("Finalized", 0),
			"label": _("Finalized"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"value": 1 if truncated else 0,
			"label": _("Results Truncated"),
			"datatype": "Check",
			"indicator": "Orange" if truncated else "Green",
		},
	]


def get_chart_data(rows):
	if not rows:
		return None
	counts = Counter(str(row.get("status") or "Unknown") for row in rows)
	return {
		"data": {
			"labels": list(counts.keys()),
			"datasets": [{"name": _("Quota Operations"), "values": list(counts.values())}],
		},
		"type": "bar",
		"height": 250,
	}


def _is_truthy(value) -> bool:
	return value is True or str(value or "").strip().lower() in {"1", "true", "yes", "on"}
