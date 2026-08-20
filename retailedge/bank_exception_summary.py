from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from retailedge.branch_context import validate_user_branch_access

MAX_BANK_MATCH_SUMMARY_ROWS = 2000
REVIEW_DECISION_STATUSES = {"Draft", "Suggested", "Needs Review", "Reopened"}
RECONCILIATION_EXCEPTION_STATUSES = {"Blocked", "Failed"}


@frappe.whitelist()
def get_bank_exception_summary(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	branch = str(filters.get("branch") or "").strip()
	from_date = str(filters.get("from_date") or "").strip()
	to_date = str(filters.get("to_date") or nowdate()).strip()
	_assert_access(company=company, branch=branch)

	query_filters: dict[str, Any] = {"company": company}
	if branch:
		query_filters["branch"] = branch
	if from_date and to_date:
		query_filters["transaction_date"] = ["between", [from_date, to_date]]
	elif from_date:
		query_filters["transaction_date"] = [">=", from_date]
	elif to_date:
		query_filters["transaction_date"] = ["<=", to_date]

	rows = frappe.get_list(
		"RetailEdge Bank Transaction Match",
		filters=query_filters,
		fields=[
			"name",
			"transaction_date",
			"bank_amount",
			"decision_status",
			"execution_status",
			"confirmed_on",
		],
		order_by="transaction_date asc, modified asc",
		limit=MAX_BANK_MATCH_SUMMARY_ROWS + 1,
	)
	if len(rows) > MAX_BANK_MATCH_SUMMARY_ROWS:
		frappe.throw(
			_("More than {0} bank-match records are in scope. Narrow the date range or Branch before loading Action Centre banking exceptions.").format(
				MAX_BANK_MATCH_SUMMARY_ROWS
			)
		)

	needs_review = [row for row in rows if str(row.get("decision_status") or "").strip() in REVIEW_DECISION_STATUSES]
	ready = [
		row
		for row in rows
		if str(row.get("decision_status") or "").strip() == "Confirmed"
		and str(row.get("execution_status") or "Not Executed").strip() == "Not Executed"
	]
	exceptions = [
		row
		for row in rows
		if str(row.get("execution_status") or "").strip() in RECONCILIATION_EXCEPTION_STATUSES
	]

	return {
		"summary": [
			{"label": _("Bank Matches Need Review"), "value": len(needs_review), "datatype": "Int"},
			{"label": _("Ready for Reconciliation"), "value": len(ready), "datatype": "Int"},
			{"label": _("Reconciliation Exceptions"), "value": len(exceptions), "datatype": "Int"},
		],
		"oldest_days": {
			"needs_review": _oldest_days(needs_review),
			"ready": _oldest_days(ready),
			"exceptions": _oldest_days(exceptions),
		},
		"scope": {"company": company, "branch": branch, "from_date": from_date, "to_date": to_date},
		"scan": {"rows": len(rows), "row_limit": MAX_BANK_MATCH_SUMMARY_ROWS},
		"metadata": {
			"candidate_discovery": False,
			"read_only": True,
			"truth": "RetailEdge Bank Transaction Match review and reconciliation execution state",
		},
	}


def _assert_access(*, company: str, branch: str) -> None:
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to view this Company."), frappe.PermissionError)
	if not frappe.has_permission("RetailEdge Bank Transaction Match", "read"):
		frappe.throw(_("You do not have permission to view bank matching controls."), frappe.PermissionError)
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)


def _oldest_days(rows: list[dict[str, Any]]) -> int:
	ages = []
	today = getdate(nowdate())
	for row in rows:
		value = row.get("transaction_date")
		if not value:
			continue
		ages.append(max((today - getdate(value)).days, 0))
	return max(ages, default=0)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
