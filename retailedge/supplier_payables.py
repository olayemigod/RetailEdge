from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from retailedge import purchase_reporting
from retailedge.transaction_branch_attribution import resolve_transaction_branch


def _current_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	resolved = frappe._dict(filters or {})
	today = nowdate()
	requested = str(resolved.get("as_of_date") or "").strip()
	if requested and getdate(requested) != getdate(today):
		frappe.throw(
			_(
				"Supplier Payables currently shows ERPNext's current outstanding balances. "
				"Historical payables as of a past date require ledger reconstruction and are not presented by this simplified report."
			)
		)
	resolved.as_of_date = today
	return resolved


def _with_current_balance_metadata(dataset: dict[str, Any]) -> dict[str, Any]:
	return {
		**dataset,
		"balance_basis": "current_outstanding",
		"ageing_date": nowdate(),
		"historical_balance_supported": False,
	}


def _branch_matches_condition(branch: str, condition: Any) -> bool:
	if condition is None:
		return True
	branch = str(branch or "").strip()
	if not branch:
		return False
	if isinstance(condition, (list, tuple)) and len(condition) >= 2:
		operator = str(condition[0] or "").strip().lower()
		values = condition[1]
		if operator == "in":
			allowed = {
				str(value or "").strip()
				for value in (values if isinstance(values, (list, tuple, set)) else [values])
				if str(value or "").strip()
			}
			return branch in allowed
	return branch == str(condition or "").strip()


def _branch_candidate_or_filters(branch_field: str | None, condition: Any) -> list[list[Any]]:
	if not branch_field or condition is None:
		return []
	if isinstance(condition, (list, tuple)) and len(condition) >= 2:
		stored_condition = [branch_field, condition[0], condition[1]]
	else:
		stored_condition = [branch_field, "=", condition]
	return [
		stored_condition,
		[branch_field, "is", "not set"],
		[branch_field, "=", ""],
	]


def _resolve_blank_invoice_branch(invoice_name: str) -> str:
	try:
		doc = frappe.get_doc("Purchase Invoice", invoice_name)
		if not frappe.has_permission("Purchase Invoice", "read", doc=doc):
			return ""
		resolution = resolve_transaction_branch(doc)
		return str(resolution.get("branch") or "").strip()
	except Exception:
		return ""


def _get_current_open_invoice_headers(filters: frappe._dict) -> tuple[list[frappe._dict], dict[str, int]]:
	branch_field, branch_condition = purchase_reporting._invoice_branch_scope(filters)
	if branch_condition == purchase_reporting.NO_BRANCH_SCOPE_SENTINEL:
		return [], {"legacy_branch_resolved": 0, "legacy_branch_unresolved": 0}

	query_filters: dict[str, Any] = {
		"docstatus": 1,
		"company": filters.company,
		"posting_date": ["<=", filters.as_of_date],
		"outstanding_amount": [">", 0],
		"is_return": 0,
	}
	if filters.get("supplier"):
		query_filters["supplier"] = filters.supplier
	if filters.get("supplier_group"):
		query_filters["supplier_group"] = filters.supplier_group
	if filters.get("status"):
		query_filters["status"] = filters.status

	fields = [
		"name",
		"posting_date",
		"due_date",
		"supplier",
		"supplier_name",
		"supplier_group",
		"currency",
		"conversion_rate",
		"outstanding_amount",
		"status",
		"is_return",
	]
	if branch_field:
		fields.append(branch_field)

	query_kwargs: dict[str, Any] = {
		"filters": query_filters,
		"fields": fields,
		"order_by": "posting_date desc, name desc",
		"limit": purchase_reporting.MAX_INVOICE_SCAN_ROWS + 1,
	}
	branch_candidates = _branch_candidate_or_filters(branch_field, branch_condition)
	if branch_candidates:
		query_kwargs["or_filters"] = branch_candidates

	rows = frappe.get_list("Purchase Invoice", **query_kwargs)
	if len(rows) > purchase_reporting.MAX_INVOICE_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} current open Purchase Invoices match these filters. Narrow the scope before loading Supplier Payables."
			).format(purchase_reporting.MAX_INVOICE_SCAN_ROWS)
		)

	resolved_count = 0
	unresolved_count = 0
	permitted: list[frappe._dict] = []
	for row in rows:
		stored_branch = str(row.get(branch_field) or "").strip() if branch_field else ""
		resolved_branch = stored_branch
		if branch_field and branch_condition is not None and not stored_branch:
			resolved_branch = _resolve_blank_invoice_branch(row.name)
			if resolved_branch:
				resolved_count += 1
			else:
				unresolved_count += 1
		if not _branch_matches_condition(resolved_branch, branch_condition):
			continue
		row["branch"] = resolved_branch
		permitted.append(row)

	return permitted, {
		"legacy_branch_resolved": resolved_count,
		"legacy_branch_unresolved": unresolved_count,
	}


def _build_current_supplier_payables_dataset(filters: frappe._dict) -> dict[str, Any]:
	purchase_reporting._validate_payables_filters(filters)
	purchase_reporting._assert_report_access(filters)
	headers, branch_scan = _get_current_open_invoice_headers(filters)
	currency = purchase_reporting._company_currency(filters.company)
	outstanding_is_base = purchase_reporting._outstanding_is_company_currency()
	as_of_date = getdate(filters.as_of_date)
	rows: list[dict[str, Any]] = []
	for row in headers:
		outstanding = flt(row.outstanding_amount)
		if not outstanding_is_base:
			outstanding *= flt(row.conversion_rate) or 1.0
		if cint(row.is_return) and outstanding > 0:
			outstanding = -abs(outstanding)
		if outstanding <= 0:
			continue
		due_date = getdate(row.due_date or row.posting_date)
		overdue_days = max(0, date_diff(as_of_date, due_date))
		bucket = purchase_reporting._ageing_bucket(overdue_days)
		if filters.get("ageing_bucket") not in (None, "", "All", bucket):
			continue
		if cint(filters.get("overdue_only")) and overdue_days <= 0:
			continue
		rows.append(
			{
				"invoice": row.name,
				"supplier": row.supplier,
				"supplier_name": row.supplier_name or row.supplier,
				"branch": row.get("branch") or "",
				"posting_date": row.posting_date,
				"due_date": row.due_date,
				"outstanding": outstanding,
				"overdue_days": overdue_days,
				"ageing_bucket": bucket,
				"status": row.status or "",
			}
		)
	rows.sort(key=lambda row: (row["overdue_days"], str(row["due_date"] or ""), row["invoice"]), reverse=True)
	bucket_totals = defaultdict(float)
	for row in rows:
		bucket_totals[row["ageing_bucket"]] += flt(row["outstanding"])
	return {
		"title": _("Supplier Payables"),
		"columns": purchase_reporting._supplier_payables_columns(currency),
		"rows": rows,
		"summary": [
			{
				"label": _("Total Payables"),
				"value": sum(flt(row["outstanding"]) for row in rows),
				"datatype": "Currency",
			},
			{"label": _("Open Bills"), "value": len(rows), "datatype": "Int"},
			{
				"label": _("Overdue"),
				"value": sum(flt(row["outstanding"]) for row in rows if row["overdue_days"] > 0),
				"datatype": "Currency",
			},
			{"label": _("Over 90 Days"), "value": bucket_totals["91+ Days"], "datatype": "Currency"},
		],
		"company_currency": currency,
		"scan": {
			"invoices": len(headers),
			"invoice_limit": purchase_reporting.MAX_INVOICE_SCAN_ROWS,
			**branch_scan,
		},
	}


@frappe.whitelist()
def get_supplier_payables(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = purchase_reporting.DEFAULT_PAGE_SIZE,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	resolved = _current_filters(filters)
	dataset = _build_current_supplier_payables_dataset(resolved)
	apply_materialized_report_sort(dataset, sort, "supplier-payables")
	return _with_current_balance_metadata(
		purchase_reporting._page_response(dataset, page=page, page_size=page_size)
	)


@frappe.whitelist()
def get_supplier_payables_export(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	resolved = _current_filters(filters)
	dataset = _build_current_supplier_payables_dataset(resolved)
	return _with_current_balance_metadata(purchase_reporting._export_response(dataset))
