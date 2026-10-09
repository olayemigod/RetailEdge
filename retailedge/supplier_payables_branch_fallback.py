from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate

from retailedge import purchase_reporting
from retailedge.transaction_branch_attribution import resolve_transaction_branch


BRANCH_PROFILE_WAREHOUSE_FIELDS = (
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
)


def _allowed_branches(condition: Any) -> set[str] | None:
	"""Return the Branches permitted by purchase_reporting scope.

	None means no Branch constraint is active, so the normal purchase-reporting
	query already includes blank historical attribution and no fallback is needed.
	"""
	if condition is None:
		return None
	if condition == purchase_reporting.NO_BRANCH_SCOPE_SENTINEL:
		return set()
	if isinstance(condition, (list, tuple)) and len(condition) >= 2:
		operator = str(condition[0] or "").strip().lower()
		values = condition[1]
		if operator == "in":
			return {
				str(value or "").strip()
				for value in (values if isinstance(values, (list, tuple, set)) else [values])
				if str(value or "").strip()
			}
		if operator in {"=", "=="}:
			value = str(values or "").strip()
			return {value} if value else set()
	value = str(condition or "").strip()
	return {value} if value else set()


def _legacy_candidate_filters(filters: frappe._dict) -> dict[str, Any]:
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
	return query_filters


def _branch_profile_branches_for_warehouse(company: str, warehouse: str) -> set[str]:
	company = str(company or "").strip()
	warehouse = str(warehouse or "").strip()
	if not company or not warehouse or not frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		return set()

	rows = frappe.get_all(
		"RetailEdge Branch Profile",
		filters={"company": company, "enabled": 1},
		fields=["branch", *BRANCH_PROFILE_WAREHOUSE_FIELDS],
		limit_page_length=0,
		order_by="branch asc",
	)
	branches = set()
	for row in rows:
		mapped_warehouses = {
			str(row.get(fieldname) or "").strip() for fieldname in BRANCH_PROFILE_WAREHOUSE_FIELDS
		}
		if warehouse in mapped_warehouses and row.get("branch"):
			branches.add(str(row.get("branch") or "").strip())
	return {branch for branch in branches if branch}


def _resolve_branch_profile_from_invoice_warehouses(doc) -> str:
	warehouses = []
	set_warehouse = str(getattr(doc, "set_warehouse", None) or "").strip()
	if set_warehouse:
		warehouses.append(set_warehouse)
	for row in getattr(doc, "items", []) or []:
		warehouse = str(getattr(row, "warehouse", None) or "").strip()
		if warehouse and warehouse not in warehouses:
			warehouses.append(warehouse)
	if not warehouses:
		return ""

	resolved_branches = set()
	for warehouse in warehouses:
		branches = _branch_profile_branches_for_warehouse(getattr(doc, "company", None), warehouse)
		if len(branches) != 1:
			return ""
		resolved_branches.update(branches)
	return next(iter(resolved_branches)) if len(resolved_branches) == 1 else ""


def _resolve_legacy_branch(invoice_name: str) -> str:
	doc = frappe.get_doc("Purchase Invoice", invoice_name)
	if not frappe.has_permission("Purchase Invoice", "read", doc=doc):
		return ""
	resolution = resolve_transaction_branch(doc)
	resolved_branch = str(resolution.get("branch") or "").strip()
	if resolved_branch:
		return resolved_branch
	return _resolve_branch_profile_from_invoice_warehouses(doc)


def _payable_row(candidate: frappe._dict, *, branch: str, filters: frappe._dict) -> dict[str, Any] | None:
	outstanding = flt(candidate.outstanding_amount)
	if not purchase_reporting._outstanding_is_company_currency():
		outstanding *= flt(candidate.conversion_rate) or 1.0
	if cint(candidate.is_return) and outstanding > 0:
		outstanding = -abs(outstanding)
	if outstanding <= 0:
		return None

	as_of_date = getdate(filters.as_of_date)
	due_date = getdate(candidate.due_date or candidate.posting_date)
	overdue_days = max(0, date_diff(as_of_date, due_date))
	bucket = purchase_reporting._ageing_bucket(overdue_days)
	if filters.get("ageing_bucket") not in (None, "", "All", bucket):
		return None
	if cint(filters.get("overdue_only")) and overdue_days <= 0:
		return None

	return {
		"invoice": candidate.name,
		"supplier": candidate.supplier,
		"supplier_name": candidate.supplier_name or candidate.supplier,
		"branch": branch,
		"posting_date": candidate.posting_date,
		"due_date": candidate.due_date,
		"outstanding": outstanding,
		"overdue_days": overdue_days,
		"ageing_bucket": bucket,
		"status": candidate.status or "",
	}


def _payables_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	bucket_totals = defaultdict(float)
	for row in rows:
		bucket_totals[row["ageing_bucket"]] += flt(row["outstanding"])
	return [
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
	]


def merge_legacy_branch_payables(dataset: dict[str, Any], filters: frappe._dict) -> dict[str, Any]:
	"""Recover safely resolvable historical open bills without mutating them.

	The standard Supplier Payables engine remains authoritative. This fallback is
	only active when a Branch constraint exists and therefore the standard query
	would exclude Purchase Invoices whose stored Branch attribution is blank.
	"""
	branch_field, branch_condition = purchase_reporting._invoice_branch_scope(filters)
	allowed = _allowed_branches(branch_condition)
	if not branch_field or allowed is None or not allowed:
		return dataset

	fields = [
		"name",
		"posting_date",
		"due_date",
		"supplier",
		"supplier_name",
		"currency",
		"conversion_rate",
		"outstanding_amount",
		"status",
		"is_return",
		branch_field,
	]
	candidates = frappe.get_list(
		"Purchase Invoice",
		filters=_legacy_candidate_filters(filters),
		or_filters=[
			[branch_field, "is", "not set"],
			[branch_field, "=", ""],
		],
		fields=fields,
		order_by="posting_date desc, name desc",
		limit=purchase_reporting.MAX_INVOICE_SCAN_ROWS + 1,
	)
	if len(candidates) > purchase_reporting.MAX_INVOICE_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} historical open Purchase Invoices need Branch resolution. "
				"Narrow Supplier or status before loading Supplier Payables."
			).format(purchase_reporting.MAX_INVOICE_SCAN_ROWS)
		)

	rows = list(dataset.get("rows") or [])
	existing_invoices = {str(row.get("invoice") or "") for row in rows}
	in_scope_headers = 0
	added_count = 0

	for candidate in candidates:
		resolved_branch = _resolve_legacy_branch(candidate.name)
		if not resolved_branch or resolved_branch not in allowed:
			continue
		in_scope_headers += 1
		if candidate.name in existing_invoices:
			continue
		row = _payable_row(candidate, branch=resolved_branch, filters=filters)
		if row is None:
			continue
		rows.append(row)
		existing_invoices.add(candidate.name)
		added_count += 1

	rows.sort(
		key=lambda row: (row["overdue_days"], str(row.get("due_date") or ""), row["invoice"]),
		reverse=True,
	)
	scan = dict(dataset.get("scan") or {})
	scan["invoices"] = int(scan.get("invoices") or 0) + in_scope_headers
	scan["legacy_branch_rows_added"] = added_count
	return {
		**dataset,
		"rows": rows,
		"summary": _payables_summary(rows),
		"scan": scan,
	}
