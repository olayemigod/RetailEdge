from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retailedge.business_expense_register import MAX_EXPORT_ROWS, get_consolidated_expense_export
from retailedge.reporting_capabilities import require_report_action
from retailedge.reporting_scope import constrain_report_filters

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
DEFAULT_GROUP_BY = "Month"
PERIOD_GROUPS = frozenset({"Day", "Week", "Month", "Quarter", "Year"})
SUPPORTED_GROUP_BY = (
	"Day",
	"Week",
	"Month",
	"Quarter",
	"Year",
	"Expense Category",
	"Expense Account",
	"Branch",
	"Source",
	"Cost Center",
	"Payment Account",
	"Cashier",
	"Expense Status",
)


@frappe.whitelist()
def get_expense_analysis(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	resolved = _resolve_filters(filters)
	dataset = _build_expense_analysis_dataset(resolved)
	apply_materialized_report_sort(dataset, sort, "expense-analysis")
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_expense_analysis_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	dataset = _build_expense_analysis_dataset(_resolve_filters(filters))
	return {
		"columns": dataset.get("columns") or [],
		"rows": dataset.get("rows") or [],
		"summary": dataset.get("summary") or [],
		"company_currency": dataset.get("company_currency") or "",
		"group_by": dataset.get("group_by") or DEFAULT_GROUP_BY,
		"scan": dataset.get("scan") or {},
		"scope": dataset.get("scope") or {},
		"metadata": dataset.get("metadata") or {},
	}


def _resolve_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	if filters and not isinstance(filters, dict):
		frappe.throw(_("Invalid Expense Analysis filters."))

	resolved = frappe._dict(filters or {})
	resolved.view_mode = "consolidated"
	resolved = frappe._dict(
		constrain_report_filters(
			resolved,
			require_branch_when_restricted=True,
		)
	)
	company = str(resolved.get("company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	require_report_action(
		"expense-analysis",
		action="view",
		company=company,
		branch=str(resolved.get("branch") or ""),
	)
	resolved.group_by = _normalise_group_by(resolved.get("group_by"))
	return resolved


def _build_expense_analysis_dataset(filters: frappe._dict) -> dict[str, Any]:
	source = get_consolidated_expense_export(filters)
	group_by = _normalise_group_by(filters.get("group_by"))
	buckets: dict[str, dict[str, Any]] = {}

	for row in source.get("rows") or []:
		group_key, group_label = _group_entry(group_by, row)
		bucket = buckets.setdefault(group_key, _new_bucket(group_key, group_label))
		_add_expense_row(bucket, row)

	rows = [_finalise_bucket(bucket) for bucket in buckets.values()]
	if group_by in PERIOD_GROUPS:
		rows.sort(key=lambda row: str(row.get("group_key") or ""))
	else:
		rows.sort(key=lambda row: (-flt(row.get("net_expense")), str(row.get("group_label") or "")))

	company = str(filters.company)
	currency = str(frappe.get_cached_value("Company", company, "default_currency") or "")
	source_metadata = dict(source.get("metadata") or {})
	return {
		"title": _("Expense Analysis"),
		"columns": _columns(currency),
		"rows": rows,
		"summary": _summary(rows),
		"company_currency": currency,
		"group_by": group_by,
		"scan": {
			"source_rows": len(source.get("rows") or []),
			"source_limit": MAX_EXPORT_ROWS,
		},
		"scope": source.get("scope") or {},
		"metadata": {
			**source_metadata,
			"source": "RetailEdge Consolidated Expense Register",
			"accounting_truth": (
				"Posted expense rows from the consolidated Expense Register remain the financial reporting truth."
			),
			"unposted_policy": (
				"Unposted Cashier Expenses are excluded by default and, when explicitly included, are shown "
				"separately as operational exposure rather than accounting expense."
			),
			"de_duplication": "Inherited from the consolidated Expense Register source model.",
			"payment_account_policy": "Payment Account is an accounting account dimension, not a payment-method inference.",
			"project_payee_policy": "Project and Payee are not exposed until the consolidated source provides authoritative fields for every supported expense source.",
		},
	}


def _normalise_group_by(value: Any) -> str:
	raw = str(value or DEFAULT_GROUP_BY).strip()
	lookup = {item.casefold(): item for item in SUPPORTED_GROUP_BY}
	resolved = lookup.get(raw.casefold())
	if not resolved:
		frappe.throw(_("Group By must be one of: {0}.").format(", ".join(SUPPORTED_GROUP_BY)))
	return resolved


def _group_entry(group_by: str, row: dict[str, Any]) -> tuple[str, str]:
	if group_by in PERIOD_GROUPS:
		return _period_group(row.get("expense_date"), group_by)
	field_map = {
		"Expense Category": "expense_category",
		"Expense Account": "expense_account",
		"Branch": "branch",
		"Source": "source_type",
		"Cost Center": "cost_center",
		"Payment Account": "payment_account",
		"Cashier": "cashier",
		"Expense Status": "expense_status",
	}
	fieldname = field_map.get(group_by)
	if not fieldname:
		frappe.throw(_("Unsupported Expense Analysis dimension."))
	value = str(row.get(fieldname) or "").strip()
	if not value:
		value = _("Non-cashier Expense") if group_by == "Cashier" else _("Unspecified {0}").format(group_by)
	return value, value


def _period_group(value: Any, group_by: str) -> tuple[str, str]:
	resolved = getdate(value)
	if group_by == "Day":
		key = resolved.isoformat()
		return key, key
	if group_by == "Week":
		iso_year, iso_week, _weekday = resolved.isocalendar()
		key = f"{iso_year}-W{iso_week:02d}"
		return key, _("Week {0}, {1}").format(iso_week, iso_year)
	if group_by == "Month":
		key = f"{resolved.year}-{resolved.month:02d}"
		return key, resolved.strftime("%b %Y")
	if group_by == "Quarter":
		quarter = ((resolved.month - 1) // 3) + 1
		key = f"{resolved.year}-Q{quarter}"
		return key, _("Q{0} {1}").format(quarter, resolved.year)
	if group_by == "Year":
		key = str(resolved.year)
		return key, key
	frappe.throw(_("Unsupported Expense Analysis period."))


def _new_bucket(group_key: str, group_label: str) -> dict[str, Any]:
	return {
		"group_key": group_key,
		"group_label": group_label,
		"expense_lines": 0,
		"posted_lines": 0,
		"unposted_cashier_lines": 0,
		"gross_spend": 0.0,
		"credits_reversals": 0.0,
		"net_expense": 0.0,
		"posted_net_expense": 0.0,
		"unposted_cashier_exposure": 0.0,
		"posting_blocked_count": 0,
	}


def _add_expense_row(bucket: dict[str, Any], row: dict[str, Any]) -> None:
	amount = flt(row.get("amount"))
	source_type = str(row.get("source_type") or "").strip()
	ledger_status = str(row.get("ledger_status") or "").strip()
	is_unposted_cashier = source_type == "Cashier / POS" and ledger_status != "Posted"
	is_posted = not is_unposted_cashier

	bucket["expense_lines"] += 1
	bucket["net_expense"] += amount
	if amount >= 0:
		bucket["gross_spend"] += amount
	else:
		bucket["credits_reversals"] += abs(amount)

	if is_posted:
		bucket["posted_lines"] += 1
		bucket["posted_net_expense"] += amount
	else:
		bucket["unposted_cashier_lines"] += 1
		bucket["unposted_cashier_exposure"] += amount
		if not cint(row.get("posting_ready")):
			bucket["posting_blocked_count"] += 1


def _finalise_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
	row = dict(bucket)
	row["average_expense"] = (
		flt(row["net_expense"]) / cint(row["expense_lines"])
		if cint(row["expense_lines"])
		else 0.0
	)
	return row


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	expense_lines = sum(cint(row.get("expense_lines")) for row in rows)
	net_expense = sum(flt(row.get("net_expense")) for row in rows)
	return [
		{"label": _("Posted Net Expense"), "value": sum(flt(row.get("posted_net_expense")) for row in rows), "datatype": "Currency"},
		{"label": _("Unposted Cashier Exposure"), "value": sum(flt(row.get("unposted_cashier_exposure")) for row in rows), "datatype": "Currency"},
		{"label": _("Gross Spend"), "value": sum(flt(row.get("gross_spend")) for row in rows), "datatype": "Currency"},
		{"label": _("Credits / Reversals"), "value": sum(flt(row.get("credits_reversals")) for row in rows), "datatype": "Currency"},
		{"label": _("Net Expense"), "value": net_expense, "datatype": "Currency"},
		{"label": _("Expense Lines"), "value": expense_lines, "datatype": "Int"},
		{"label": _("Average Expense"), "value": net_expense / expense_lines if expense_lines else 0.0, "datatype": "Currency"},
		{"label": _("Posting Blocked"), "value": sum(cint(row.get("posting_blocked_count")) for row in rows), "datatype": "Int"},
	]


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "group_label", "label": _("Group"), "fieldtype": "Data"},
		{"fieldname": "expense_lines", "label": _("Expense Lines"), "fieldtype": "Int"},
		{"fieldname": "posted_lines", "label": _("Posted Lines"), "fieldtype": "Int"},
		{"fieldname": "unposted_cashier_lines", "label": _("Unposted Cashier Lines"), "fieldtype": "Int"},
		{"fieldname": "gross_spend", "label": _("Gross Spend"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "credits_reversals", "label": _("Credits / Reversals"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "net_expense", "label": _("Net Expense"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "posted_net_expense", "label": _("Posted Net Expense"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "unposted_cashier_exposure", "label": _("Unposted Cashier Exposure"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "average_expense", "label": _("Avg Expense"), "fieldtype": "Currency", "options": currency},
		{"fieldname": "posting_blocked_count", "label": _("Posting Blocked"), "fieldtype": "Int"},
	]


def _page_response(
	dataset: dict[str, Any],
	*,
	page: int | str,
	page_size: int | str,
) -> dict[str, Any]:
	rows = list(dataset.get("rows") or [])
	resolved_page_size = max(25, min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))
	resolved_page = max(cint(page), 1)
	total_rows = len(rows)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	resolved_page = min(resolved_page, total_pages)
	start = (resolved_page - 1) * resolved_page_size
	return {
		**dataset,
		"rows": rows[start : start + resolved_page_size],
		"pagination": {
			"page": resolved_page,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": resolved_page > 1,
			"has_next": resolved_page < total_pages,
		},
	}
