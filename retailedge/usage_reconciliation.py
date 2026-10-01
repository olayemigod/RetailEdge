from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	finalize_sales_quota_operation,
)
from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_allowed_operating_contexts,
	get_operational_branch_scope,
)


_REVIEW_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
_RETRY_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
}
_ALLOWED_STATUSES = {"Needs Review", "Pending Finalize", "Finalized"}
_DEFAULT_PAGE_LENGTH = 50
_MAX_PAGE_LENGTH = 100


@frappe.whitelist()
def get_usage_reconciliation(
	filters: dict[str, Any] | str | None = None,
	limit_start: int = 0,
	page_length: int = _DEFAULT_PAGE_LENGTH,
) -> dict[str, Any]:
	_assert_review_access()
	resolved = _coerce_filters(filters)
	scope = _resolve_scope(resolved)
	can_retry = _can_retry()

	if scope["requires_company"] or scope["no_branch_access"]:
		return _empty_payload(scope=scope, filters=resolved, can_retry=can_retry)

	query_filters = _scope_filters(scope)
	status = str(resolved.get("status") or "Needs Review").strip()
	if status and status != "All":
		if status not in _ALLOWED_STATUSES:
			frappe.throw(_("Invalid usage reconciliation status."), frappe.ValidationError)
		query_filters["status"] = status

	source_doctype = str(resolved.get("source_doctype") or "").strip()
	if source_doctype:
		if source_doctype not in {"Sales Invoice", "POS Invoice"}:
			frappe.throw(_("Invalid source document type."), frappe.ValidationError)
		query_filters["source_doctype"] = source_doctype

	search = str(resolved.get("search") or "").strip()[:140]
	or_filters = []
	if search:
		pattern = f"%{search}%"
		or_filters = [
			["source_name", "like", pattern],
			["reservation_reference", "like", pattern],
			["reason_code", "like", pattern],
		]

	start = _bounded_non_negative_int(limit_start, default=0, maximum=100000)
	length = _bounded_positive_int(
		page_length,
		default=_DEFAULT_PAGE_LENGTH,
		maximum=_MAX_PAGE_LENGTH,
	)
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
			"modified",
		],
		order_by="creation desc",
		limit_start=start,
		limit_page_length=length + 1,
	)
	has_more = len(rows) > length
	rows = rows[:length]

	return {
		"title": _("Usage Reconciliation"),
		"rows": [_decorate_row(dict(row), can_retry=can_retry) for row in rows],
		"summary": _get_summary(scope),
		"filters": {
			"company": scope["company"],
			"branch": scope["branch"],
			"status": status or "Needs Review",
			"source_doctype": source_doctype,
			"search": search,
		},
		"options": {
			"companies": scope["companies"],
			"branches": scope["branches"],
			"statuses": ["Needs Review", "Pending Finalize", "Finalized", "All"],
			"source_doctypes": ["Sales Invoice", "POS Invoice"],
		},
		"access": {
			"can_retry": can_retry,
			"read_only": not can_retry,
		},
		"pagination": {
			"limit_start": start,
			"page_length": length,
			"has_more": has_more,
		},
		"metadata": {
			"requires_company": False,
			"no_branch_access": False,
			"scope_source": scope["scope_source"],
			"no_new_reservation": True,
			"accounting_mutation": False,
			"platform_escalation_required_for_unreserved": True,
		},
	}


@frappe.whitelist()
def retry_usage_finalization(operation_name: str) -> dict[str, Any]:
	_assert_post()
	_assert_retry_access()
	name = str(operation_name or "").strip()
	if not name or len(name) > 140:
		frappe.throw(_("A valid usage reconciliation operation is required."), frappe.ValidationError)

	operation = frappe.get_doc(OPERATION_DOCTYPE, name)
	operation.check_permission("read")
	_assert_operation_scope(operation)

	if operation.status == "Finalized":
		return {
			"ok": True,
			"status": "Finalized",
			"operation": _decorate_row(operation.as_dict(), can_retry=True),
		}
	if operation.status not in {"Pending Finalize", "Needs Review"}:
		frappe.throw(_("This usage operation cannot be retried."), frappe.ValidationError)
	if not operation.reservation_reference:
		frappe.throw(
			_(
				"This usage exception has no existing platform reservation. "
				"Escalate it for platform reconciliation; a new reservation will not "
				"be created from this review page."
			),
			frappe.ValidationError,
		)

	result = finalize_sales_quota_operation(
		operation.name,
		allow_needs_review_retry=True,
	)
	refreshed = frappe.get_doc(OPERATION_DOCTYPE, operation.name)
	return {
		"ok": refreshed.status == "Finalized",
		"status": refreshed.status,
		"operation": _decorate_row(refreshed.as_dict(), can_retry=True),
		"engine_result": result,
	}


def _resolve_scope(filters: frappe._dict) -> dict[str, Any]:
	user = frappe.session.user
	requested_company = str(filters.get("company") or "").strip()
	base_context = get_allowed_operating_contexts(company=requested_company)
	companies = list(base_context.get("companies") or [])
	current = dict(base_context.get("current") or {})

	company = (
		requested_company
		or str(current.get("company") or "").strip()
		or (companies[0] if len(companies) == 1 else "")
	)
	if company and company not in companies:
		frappe.throw(
			_("You do not have access to Company {0}.").format(company),
			frappe.PermissionError,
		)
	if not company:
		return {
			"company": "",
			"branch": "",
			"companies": companies,
			"branches": [],
			"restricted": False,
			"allowed_branches": [],
			"requires_company": True,
			"no_branch_access": False,
			"scope_source": "company_required",
		}

	branches = list(get_allowed_operating_branches(company=company, user=user))
	branch_scope = get_operational_branch_scope(company=company, user=user)
	allowed_branches = list(branch_scope.get("allowed_branches") or [])
	requested_branch = str(filters.get("branch") or "").strip()

	if requested_branch and requested_branch not in branches:
		frappe.throw(
			_("You do not have access to Branch {0}.").format(requested_branch),
			frappe.PermissionError,
		)

	restricted = bool(branch_scope.get("restricted"))
	no_branch_access = restricted and not allowed_branches
	return {
		"company": company,
		"branch": requested_branch,
		"companies": companies,
		"branches": branches,
		"restricted": restricted,
		"allowed_branches": allowed_branches,
		"requires_company": False,
		"no_branch_access": no_branch_access,
		"scope_source": branch_scope.get("source") or "operating_context",
	}


def _scope_filters(scope: dict[str, Any]) -> dict[str, Any]:
	filters: dict[str, Any] = {"company": scope["company"]}
	if scope["branch"]:
		filters["branch"] = scope["branch"]
	elif scope["restricted"]:
		filters["branch"] = ["in", scope["allowed_branches"]]
	return filters


def _get_summary(scope: dict[str, Any]) -> dict[str, int]:
	filters = _scope_filters(scope)
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=filters,
		fields=["status", "count(name) as count"],
		group_by="status",
		limit_page_length=10,
	)
	counts = {status: 0 for status in _ALLOWED_STATUSES}
	for row in rows:
		status = str(row.get("status") or "")
		if status in counts:
			counts[status] = int(row.get("count") or 0)
	return {
		"needs_review": counts["Needs Review"],
		"pending_finalize": counts["Pending Finalize"],
		"finalized": counts["Finalized"],
		"open": counts["Needs Review"] + counts["Pending Finalize"],
	}


def _decorate_row(row: dict[str, Any], *, can_retry: bool) -> dict[str, Any]:
	status = str(row.get("status") or "")
	reservation_reference = str(row.get("reservation_reference") or "").strip()
	reason_code = str(row.get("reason_code") or "").strip()
	row["retry_allowed"] = bool(
		can_retry
		and reservation_reference
		and status in {"Needs Review", "Pending Finalize"}
	)
	row["requires_platform_reconciliation"] = bool(
		status == "Needs Review" and not reservation_reference
	)
	row["severity"] = (
		"danger"
		if status == "Needs Review"
		else ("warning" if status == "Pending Finalize" else "success")
	)
	row["guidance"] = _guidance(
		status=status,
		reason_code=reason_code,
		has_reservation=bool(reservation_reference),
	)
	return row


def _guidance(*, status: str, reason_code: str, has_reservation: bool) -> str:
	if status == "Finalized":
		return _("Usage finalization is confirmed.")
	if not has_reservation:
		return _(
			"No platform reservation exists for this committed sale. Escalate for "
			"platform reconciliation; do not create a replacement business document."
		)
	if reason_code in {
		"RESERVATION_EXPIRED",
		"RESERVATION_ALREADY_RELEASED",
		"RESERVATION_NOT_FOUND",
		"USAGE_RESERVATION_ACCESS_DENIED",
	}:
		return _(
			"Retry once to verify the platform's authoritative reservation state. "
			"If it remains unresolved, escalate for platform reconciliation."
		)
	return _(
		"Retry finalization against the existing reservation. No new quota "
		"reservation will be created."
	)


def _empty_payload(
	*,
	scope: dict[str, Any],
	filters: frappe._dict,
	can_retry: bool,
) -> dict[str, Any]:
	return {
		"title": _("Usage Reconciliation"),
		"rows": [],
		"summary": {
			"needs_review": 0,
			"pending_finalize": 0,
			"finalized": 0,
			"open": 0,
		},
		"filters": {
			"company": scope["company"],
			"branch": "",
			"status": str(filters.get("status") or "Needs Review"),
			"source_doctype": str(filters.get("source_doctype") or ""),
			"search": str(filters.get("search") or "")[:140],
		},
		"options": {
			"companies": scope["companies"],
			"branches": scope["branches"],
			"statuses": ["Needs Review", "Pending Finalize", "Finalized", "All"],
			"source_doctypes": ["Sales Invoice", "POS Invoice"],
		},
		"access": {
			"can_retry": can_retry,
			"read_only": not can_retry,
		},
		"pagination": {
			"limit_start": 0,
			"page_length": _DEFAULT_PAGE_LENGTH,
			"has_more": False,
		},
		"metadata": {
			"requires_company": scope["requires_company"],
			"no_branch_access": scope["no_branch_access"],
			"scope_source": scope["scope_source"],
			"no_new_reservation": True,
			"accounting_mutation": False,
			"platform_escalation_required_for_unreserved": True,
		},
	}


def _assert_operation_scope(operation) -> None:
	company = str(operation.company or "").strip()
	branch = str(operation.branch or "").strip()
	if not company:
		frappe.throw(
			_("Usage reconciliation operation has no Company attribution."),
			frappe.PermissionError,
		)
	scope = _resolve_scope(frappe._dict(company=company, branch=branch))
	if (
		scope["requires_company"]
		or scope["no_branch_access"]
		or (scope["restricted"] and not branch)
	):
		frappe.throw(_("You do not have access to this usage operation."), frappe.PermissionError)


def _assert_review_access() -> None:
	if frappe.session.user == "Administrator":
		return
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(_REVIEW_ROLES):
		frappe.throw(_("You do not have access to Usage Reconciliation."), frappe.PermissionError)
	if not frappe.has_permission(OPERATION_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to read usage reconciliation records."), frappe.PermissionError)


def _assert_retry_access() -> None:
	if frappe.session.user == "Administrator":
		return
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(_RETRY_ROLES):
		frappe.throw(_("You do not have permission to retry usage finalization."), frappe.PermissionError)
	if not frappe.has_permission(OPERATION_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to read usage reconciliation records."), frappe.PermissionError)


def _can_retry() -> bool:
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles(frappe.session.user))
	return bool(roles.intersection(_RETRY_ROLES))


def _assert_post() -> None:
	request = getattr(frappe.local, "request", None)
	if request is not None and str(getattr(request, "method", "")).upper() != "POST":
		frappe.throw(_("Usage reconciliation changes require HTTP POST."), frappe.PermissionError)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})


def _bounded_non_negative_int(value: Any, *, default: int, maximum: int) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		return default
	return min(max(parsed, 0), maximum)


def _bounded_positive_int(value: Any, *, default: int, maximum: int) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		return default
	return min(max(parsed, 1), maximum)
