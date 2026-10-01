from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	queue_sales_quota_finalization,
)
from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_allowed_operating_contexts,
	get_operating_context,
	get_operational_branch_scope,
	validate_operating_branch,
)


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_DATASET_ROWS = 2000
READ_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
RETRY_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
}
STATUS_OPTIONS = {
	"Open": ["Pending Finalize", "Needs Review"],
	"Pending Finalize": ["Pending Finalize"],
	"Needs Review": ["Needs Review"],
	"Finalized": ["Finalized"],
	"All": [],
}
SOURCE_DOCTYPES = {"Sales Invoice", "POS Invoice"}


@frappe.whitelist()
def get_quota_operations_center_context() -> dict[str, Any]:
	_require_read_access()
	current = get_operating_context() or {}
	company = str(
		current.get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	branch = str(current.get("branch") or "").strip()
	return {
		"default_filters": {
			"company": company,
			"branch": branch,
			"status": "Open",
			"source_doctype": "",
			"search": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name")
		or frappe.session.user,
		"can_retry": _user_can_retry(),
		"limits": {
			"rows": MAX_DATASET_ROWS,
			"page_size": MAX_PAGE_SIZE,
		},
		"metadata": {
			"read_only_needs_review": True,
			"accounting_mutation": False,
			"quota_mutation_from_browser": False,
		},
	}


@frappe.whitelist()
def search_quota_operations_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
	_require_read_access()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip().lower()
	company = str(company or "").strip()

	if kind == "company":
		contexts = get_allowed_operating_contexts()
		return [
			{"value": value, "label": value}
			for value in contexts.get("companies") or []
			if not txt or txt in str(value).lower()
		][:20]

	if kind == "branch":
		if not company:
			return []
		# Validate Company access before revealing its Branch options.
		get_allowed_operating_contexts(company=company)
		return [
			{"value": value, "label": value}
			for value in get_allowed_operating_branches(company=company)
			if not txt or txt in str(value).lower()
		][:20]

	frappe.throw(_("Unsupported Quota Operations search type."), frappe.ValidationError)


@frappe.whitelist()
def get_quota_operations(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	_require_read_access()
	resolved = _coerce_filters(filters)
	query_filters = _build_query_filters(resolved)
	status_name = str(resolved.get("status") or "Open").strip() or "Open"
	status_values = STATUS_OPTIONS.get(status_name)
	if status_values is None:
		frappe.throw(_("Unsupported quota operation status filter."), frappe.ValidationError)
	if status_values:
		query_filters["status"] = ["in", status_values]

	or_filters = _search_filters(str(resolved.get("search") or ""))
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=query_filters,
		or_filters=or_filters or None,
		fields=[
			"name",
			"status",
			"source_doctype",
			"source_name",
			"company",
			"branch",
			"entitlement_key",
			"units",
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
		order_by="creation desc, name desc",
		limit_page_length=MAX_DATASET_ROWS + 1,
	)
	if len(rows) > MAX_DATASET_ROWS:
		frappe.throw(
			_(
				"More than {0} quota operations match this scope. "
				"Narrow Company, Branch, status, source type, or search before continuing."
			).format(MAX_DATASET_ROWS),
			frappe.ValidationError,
		)

	page_number = _bounded_int(page, 1, 1, 100000)
	resolved_page_size = _bounded_int(page_size, DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
	total_rows = len(rows)
	total_pages = max(1, ceil(total_rows / resolved_page_size))
	page_number = min(page_number, total_pages)
	start = (page_number - 1) * resolved_page_size
	page_rows = rows[start : start + resolved_page_size]
	can_retry = _user_can_retry()

	return {
		"title": _("Quota Operations"),
		"columns": _columns(),
		"rows": [_serialize_row(row, can_retry=can_retry) for row in page_rows],
		"summary": _summary(rows),
		"pagination": {
			"page": page_number,
			"page_size": resolved_page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": page_number > 1,
			"has_next": page_number < total_pages,
		},
		"filters": {
			"company": str(resolved.get("company") or ""),
			"branch": str(resolved.get("branch") or ""),
			"status": status_name,
			"source_doctype": str(resolved.get("source_doctype") or ""),
			"search": str(resolved.get("search") or ""),
		},
		"metadata": {
			"dataset_limit": MAX_DATASET_ROWS,
			"permission_aware": True,
			"branch_scope_enforced": True,
			"needs_review_is_read_only": True,
			"retry_action": "Pending Finalize only",
		},
	}


@frappe.whitelist()
def retry_quota_operation(operation_name: str) -> dict[str, Any]:
	_require_post()
	_require_retry_access()
	operation_name = str(operation_name or "").strip()
	if not operation_name:
		frappe.throw(_("Quota operation is required."), frappe.ValidationError)

	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters={"name": operation_name},
		fields=["name", "status", "company", "branch", "source_doctype", "source_name"],
		limit_page_length=1,
	)
	if not rows:
		frappe.throw(_("Quota operation was not found or is not permitted."), frappe.DoesNotExistError)
	row = rows[0]
	_assert_row_scope(row)

	if row.status != "Pending Finalize":
		frappe.throw(
			_("Only Pending Finalize quota operations can be retried from this page."),
			frappe.ValidationError,
		)

	if not queue_sales_quota_finalization(row.name):
		frappe.throw(
			_("The quota finalization job could not be queued. Try again after the worker service is available."),
			frappe.ValidationError,
		)

	return {
		"queued": True,
		"operation_name": row.name,
		"status": row.status,
		"message": _("Quota finalization retry queued."),
	}


def _build_query_filters(filters: frappe._dict) -> dict[str, Any]:
	company = str(
		filters.get("company")
		or get_operating_context().get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	if not company:
		frappe.throw(_("Company is required."), frappe.ValidationError)

	# This fails closed if the user cannot access the requested Company.
	get_allowed_operating_contexts(company=company)
	query_filters: dict[str, Any] = {"company": company}

	branch = str(filters.get("branch") or "").strip()
	scope = get_operational_branch_scope(company=company)
	if branch:
		validate_operating_branch(company=company, branch=branch, throw=True)
		query_filters["branch"] = branch
	elif scope.get("restricted"):
		allowed = list(scope.get("allowed_branches") or [])
		if not allowed:
			frappe.throw(
				_("Your Branch operating access is not active for Company {0}.").format(company),
				frappe.PermissionError,
			)
		query_filters["branch"] = ["in", allowed]

	source_doctype = str(filters.get("source_doctype") or "").strip()
	if source_doctype:
		if source_doctype not in SOURCE_DOCTYPES:
			frappe.throw(_("Unsupported quota operation source type."), frappe.ValidationError)
		query_filters["source_doctype"] = source_doctype

	return query_filters


def _assert_row_scope(row: frappe._dict) -> None:
	company = str(row.get("company") or "").strip()
	branch = str(row.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Quota operation has no Company attribution."), frappe.PermissionError)
	get_allowed_operating_contexts(company=company)
	scope = get_operational_branch_scope(company=company)
	if scope.get("restricted"):
		allowed = set(scope.get("allowed_branches") or [])
		if not branch or branch not in allowed:
			frappe.throw(_("You do not have access to this quota operation."), frappe.PermissionError)
	elif branch:
		validate_operating_branch(company=company, branch=branch, throw=True)


def _search_filters(value: str) -> dict[str, Any]:
	value = str(value or "").strip()
	if not value:
		return {}
	like = f"%{value}%"
	return {
		"source_name": ["like", like],
		"reason_code": ["like", like],
		"last_error": ["like", like],
		"remote_message": ["like", like],
	}


def _serialize_row(row: frappe._dict, *, can_retry: bool) -> dict[str, Any]:
	status = str(row.get("status") or "")
	source_doctype = str(row.get("source_doctype") or "")
	source_name = str(row.get("source_name") or "")
	issue = (
		str(row.get("last_error") or "").strip()
		or str(row.get("remote_message") or "").strip()
		or str(row.get("reason_code") or "").strip()
	)
	return {
		"name": row.get("name"),
		"status": status,
		"source": f"{source_doctype} {source_name}".strip(),
		"source_doctype": source_doctype,
		"source_name": source_name,
		"source_openable": _can_read_source(source_doctype, source_name),
		"company": row.get("company") or "",
		"branch": row.get("branch") or "",
		"entitlement_key": row.get("entitlement_key") or "",
		"units": int(row.get("units") or 0),
		"has_reservation": bool(row.get("reservation_reference")),
		"reservation_expires_on": row.get("reservation_expires_on"),
		"warning": int(row.get("warning") or 0),
		"reason_code": row.get("reason_code") or "",
		"issue": issue[:500],
		"reserved_on": row.get("reserved_on"),
		"finalized_on": row.get("finalized_on"),
		"last_attempt_on": row.get("last_attempt_on"),
		"attempt_count": int(row.get("attempt_count") or 0),
		"action": "Retry Finalization" if status == "Pending Finalize" and can_retry else "",
		"can_retry": bool(status == "Pending Finalize" and can_retry),
	}


def _summary(rows: list[frappe._dict]) -> list[dict[str, Any]]:
	return [
		{
			"label": _("Needs Review"),
			"value": sum(1 for row in rows if row.get("status") == "Needs Review"),
			"datatype": "Int",
		},
		{
			"label": _("Pending Finalize"),
			"value": sum(1 for row in rows if row.get("status") == "Pending Finalize"),
			"datatype": "Int",
		},
		{
			"label": _("Finalized"),
			"value": sum(1 for row in rows if row.get("status") == "Finalized"),
			"datatype": "Int",
		},
		{
			"label": _("Matching Operations"),
			"value": len(rows),
			"datatype": "Int",
		},
	]


def _columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 145},
		{"fieldname": "source", "label": _("Source Transaction"), "fieldtype": "Data", "width": 250},
		{"fieldname": "company", "label": _("Company"), "fieldtype": "Data", "width": 180},
		{"fieldname": "branch", "label": _("Branch"), "fieldtype": "Data", "width": 150},
		{"fieldname": "entitlement_key", "label": _("Entitlement"), "fieldtype": "Data", "width": 170},
		{"fieldname": "reason_code", "label": _("Reason"), "fieldtype": "Data", "width": 190},
		{"fieldname": "issue", "label": _("Issue / Message"), "fieldtype": "Data", "width": 300},
		{"fieldname": "reserved_on", "label": _("Reserved On"), "fieldtype": "Datetime", "width": 170},
		{"fieldname": "last_attempt_on", "label": _("Last Attempt"), "fieldtype": "Datetime", "width": 170},
		{"fieldname": "attempt_count", "label": _("Attempts"), "fieldtype": "Int", "width": 90},
		{"fieldname": "action", "label": _("Action"), "fieldtype": "Data", "width": 150},
	]


def _can_read_source(doctype: str, name: str) -> bool:
	if not doctype or not name:
		return False
	try:
		return bool(frappe.has_permission(doctype, "read", doc=name))
	except Exception:
		return False


def _require_read_access() -> None:
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(READ_ROLES):
		frappe.throw(_("You do not have access to Quota Operations."), frappe.PermissionError)
	if not frappe.has_permission(OPERATION_DOCTYPE, "read"):
		frappe.throw(_("You do not have access to quota operation records."), frappe.PermissionError)


def _require_retry_access() -> None:
	_require_read_access()
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(RETRY_ROLES):
		frappe.throw(_("You have read-only access to Quota Operations."), frappe.PermissionError)


def _user_can_retry() -> bool:
	return bool(set(frappe.get_roles(frappe.session.user)).intersection(RETRY_ROLES))


def _require_post() -> None:
	request = getattr(frappe.local, "request", None)
	method = str(getattr(request, "method", "") or "").upper()
	if method != "POST":
		frappe.throw(_("Quota operation retry requires POST."), frappe.PermissionError)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		parsed = default
	return max(minimum, min(parsed, maximum))
