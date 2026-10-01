from __future__ import annotations

import hashlib
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	finalize_sales_quota_operation,
	get_sales_transaction_quota_readiness,
)
from retailedge.integrations.coreedge_remote_usage import (
	CoreEdgeRemoteUsageError,
	get_remote_usage_client,
	get_remote_usage_readiness,
)
from retailedge.operating_context import get_allowed_operating_branches


_MUTATION_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
}
_STATUS_OPTIONS = {"Open", "Pending Finalize", "Needs Review", "Finalized", "All"}
_PAGE_SIZE_DEFAULT = 25
_PAGE_SIZE_MAX = 100


@frappe.whitelist()
def get_quota_review_context() -> dict:
	_assert_read_access()
	return {
		"title": "Quota Operations Review",
		"eyebrow": "Operations Review",
		"subtitle": (
			"Review pending CoreEdge quota finalizations and committed sales that "
			"need explicit commercial reconciliation."
		),
		"can_reconcile": _can_mutate(),
		"default_filters": {
			"status": "Open",
			"company": str(frappe.defaults.get_user_default("Company") or "").strip(),
			"branch": "",
			"source_doctype": "",
			"from_date": "",
			"to_date": "",
			"search": "",
		},
		"status_options": [
			{"label": "Open", "value": "Open"},
			{"label": "Needs Review", "value": "Needs Review"},
			{"label": "Pending Finalize", "value": "Pending Finalize"},
			{"label": "Finalized", "value": "Finalized"},
			{"label": "All", "value": "All"},
		],
		"source_doctype_options": [
			{"label": "All sales documents", "value": ""},
			{"label": "Sales Invoice", "value": "Sales Invoice"},
			{"label": "POS Invoice", "value": "POS Invoice"},
		],
		"sales_quota": get_sales_transaction_quota_readiness(),
		"remote_usage": get_remote_usage_readiness(),
	}


@frappe.whitelist()
def list_quota_operations(
	filters: dict[str, Any] | str | None = None,
	page: int = 1,
	page_size: int = _PAGE_SIZE_DEFAULT,
) -> dict:
	_assert_read_access()
	filters = _parse_filters(filters)
	page = max(1, int(page or 1))
	page_size = max(1, min(int(page_size or _PAGE_SIZE_DEFAULT), _PAGE_SIZE_MAX))
	list_filters, scope_filters, or_filters = _build_filters(filters)

	fields = [
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
		"review_action",
		"review_reason",
		"reviewed_by",
		"reviewed_on",
		"creation",
		"modified",
	]
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=list_filters,
		or_filters=or_filters,
		fields=fields,
		order_by="modified desc, creation desc",
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	total_rows = _count_rows(list_filters, or_filters)
	status_counts = _status_counts(scope_filters, or_filters)
	return {
		"rows": [dict(row) for row in rows],
		"summary": {
			"pending_finalize": status_counts.get("Pending Finalize", 0),
			"needs_review": status_counts.get("Needs Review", 0),
			"finalized": status_counts.get("Finalized", 0),
			"total": sum(status_counts.values()),
		},
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_rows": total_rows,
			"total_pages": max(1, (total_rows + page_size - 1) // page_size),
		},
		"can_reconcile": _can_mutate(),
	}


@frappe.whitelist()
def search_quota_review_options(
	doctype: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
	_assert_read_access()
	doctype = str(doctype or "").strip()
	txt = str(txt or "").strip()
	company = str(company or "").strip()
	if doctype not in {"Company", "Branch"}:
		frappe.throw(_("Unsupported quota review filter search."), frappe.PermissionError)

	if doctype == "Branch":
		branches = get_allowed_operating_branches(company=company) if company else []
		return [
			{"value": branch, "label": branch}
			for branch in branches
			if not txt or txt.lower() in branch.lower()
		][:20]

	filters: dict[str, Any] = {}
	if txt:
		filters["name"] = ["like", f"%{txt}%"]
	rows = frappe.get_list(
		"Company",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=20,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


@frappe.whitelist()
def retry_quota_operation(operation_name: str, reason: str | None = None) -> dict:
	_require_post()
	_assert_mutation_access()
	operation = frappe.get_doc(OPERATION_DOCTYPE, _operation_name(operation_name))
	if operation.status == "Finalized":
		return {"ok": True, "status": "Finalized", "operation": _operation_result(operation)}
	if operation.status == "Pending Finalize":
		result = finalize_sales_quota_operation(operation.name)
		return {
			"ok": result.get("status") == "Finalized",
			"status": result.get("status"),
			"operation": result,
		}
	if operation.status != "Needs Review":
		frappe.throw(_("This quota operation is not eligible for retry."), frappe.ValidationError)
	if not operation.reservation_reference:
		return {
			"ok": False,
			"status": "Needs Review",
			"reason_code": "RECONCILIATION_RESERVATION_REQUIRED",
			"message": _(
				"This committed sale has no quota reservation. Use Attempt Reconciliation."
			),
			"operation": _operation_result(operation),
		}

	resolved_reason = _review_reason(reason)
	result = finalize_sales_quota_operation(
		operation.name,
		allow_needs_review=True,
		review_action="Retry CoreEdge Finalization",
		review_reason=resolved_reason,
	)
	return {
		"ok": result.get("status") == "Finalized",
		"status": result.get("status"),
		"operation": result,
	}


@frappe.whitelist()
def reconcile_unreserved_quota_operation(
	operation_name: str,
	reason: str,
) -> dict:
	_require_post()
	_assert_mutation_access()
	resolved_reason = _review_reason(reason)
	name = _operation_name(operation_name)
	operation = frappe.get_doc(OPERATION_DOCTYPE, name)
	if operation.status == "Finalized":
		return {"ok": True, "status": "Finalized", "operation": _operation_result(operation)}
	if operation.status != "Needs Review":
		frappe.throw(
			_("Only a Needs Review quota operation can be reconciled."),
			frappe.ValidationError,
		)
	if operation.reservation_reference:
		return retry_quota_operation(operation.name, resolved_reason)
	if operation.reason_code != "FAIL_OPEN_UNRESERVED":
		frappe.throw(
			_(
				"This review item does not qualify for automatic unreserved-sale "
				"reconciliation."
			),
			frappe.ValidationError,
		)

	docstatus = _source_docstatus(operation)
	if int(docstatus or 0) not in {1, 2}:
		_record_review_failure(
			operation,
			action="Attempt Reconciliation",
			reason=resolved_reason,
			reason_code="SOURCE_NOT_SUBMITTED",
			message=_(
				"The source document has not reached a submitted transaction state."
			),
		)
		return {
			"ok": False,
			"status": "Needs Review",
			"reason_code": "SOURCE_NOT_SUBMITTED",
			"operation": _operation_result(operation),
		}

	attempt_key = _review_reserve_key(operation)
	try:
		response = get_remote_usage_client().reserve_usage(
			operation.entitlement_key,
			int(operation.units or 1),
			attempt_key,
			expires_in_seconds=3600,
			reference_doctype=operation.source_doctype,
			reference_name=operation.source_name,
			request_id=attempt_key,
			correlation_id=f"{operation.source_doctype}:{operation.source_name}",
			source_path="RetailEdge Quota Review",
		)
	except CoreEdgeRemoteUsageError as exc:
		_record_review_failure(
			operation,
			action="Attempt Reconciliation",
			reason=resolved_reason,
			reason_code="RECONCILIATION_SERVICE_UNAVAILABLE",
			message=str(exc)[:500],
		)
		return {
			"ok": False,
			"status": "Needs Review",
			"reason_code": "RECONCILIATION_SERVICE_UNAVAILABLE",
			"operation": _operation_result(operation),
		}

	data = response.get("data") or {}
	quota = data.get("quota") or {}
	if not data.get("ok"):
		reason_code = str(data.get("reason_code") or "RECONCILIATION_BLOCKED")[:140]
		message = str(data.get("message") or quota.get("message") or reason_code)[:1000]
		_record_review_failure(
			operation,
			action="Attempt Reconciliation",
			reason=resolved_reason,
			reason_code=reason_code,
			message=message,
		)
		return {
			"ok": False,
			"status": "Needs Review",
			"reason_code": reason_code,
			"message": message,
			"operation": _operation_result(operation),
		}

	reservation_reference = str(quota.get("reservation_reference") or "").strip()
	if quota.get("status") != "Active" or not reservation_reference:
		_record_review_failure(
			operation,
			action="Attempt Reconciliation",
			reason=resolved_reason,
			reason_code="RECONCILIATION_RESERVATION_INVALID",
			message=_("CoreEdge did not return an active reconciliation reservation."),
		)
		return {
			"ok": False,
			"status": "Needs Review",
			"reason_code": "RECONCILIATION_RESERVATION_INVALID",
			"operation": _operation_result(operation),
		}

	_lock_operation(name)
	operation = frappe.get_doc(OPERATION_DOCTYPE, name)
	if operation.status == "Finalized":
		return {"ok": True, "status": "Finalized", "operation": _operation_result(operation)}
	if operation.reservation_reference:
		return retry_quota_operation(operation.name, resolved_reason)

	operation.reservation_reference = reservation_reference
	operation.reservation_expires_on = quota.get("expires_on")
	operation.warning = 1 if quota.get("warning") else 0
	operation.reason_code = str(quota.get("reason_code") or "RECONCILIATION_RESERVED")[:140]
	operation.remote_message = str(quota.get("message") or "")[:1000]
	operation.last_error = None
	_apply_review_metadata(operation, "Attempt Reconciliation", resolved_reason)
	_save_review_operation(operation, reconciliation=True)

	result = finalize_sales_quota_operation(
		operation.name,
		allow_needs_review=True,
		review_action="Attempt Reconciliation",
		review_reason=resolved_reason,
	)
	return {
		"ok": result.get("status") == "Finalized",
		"status": result.get("status"),
		"operation": result,
	}


def _parse_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})


def _build_filters(filters: frappe._dict):
	status = str(filters.get("status") or "Open").strip()
	if status not in _STATUS_OPTIONS:
		frappe.throw(_("Invalid quota review status filter."), frappe.ValidationError)

	scope_filters: list[list[Any]] = []
	company = str(filters.get("company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if company:
		scope_filters.append([OPERATION_DOCTYPE, "company", "=", company])
	if branch:
		allowed = set(get_allowed_operating_branches(company=company) or [])
		if allowed and branch not in allowed:
			frappe.throw(_("You are not allowed to review that Branch."), frappe.PermissionError)
		scope_filters.append([OPERATION_DOCTYPE, "branch", "=", branch])

	source_doctype = str(filters.get("source_doctype") or "").strip()
	if source_doctype:
		if source_doctype not in {"Sales Invoice", "POS Invoice"}:
			frappe.throw(_("Invalid source document filter."), frappe.ValidationError)
		scope_filters.append([OPERATION_DOCTYPE, "source_doctype", "=", source_doctype])

	from_date = str(filters.get("from_date") or "").strip()
	to_date = str(filters.get("to_date") or "").strip()
	if from_date:
		scope_filters.append([OPERATION_DOCTYPE, "creation", ">=", f"{from_date} 00:00:00"])
	if to_date:
		scope_filters.append([OPERATION_DOCTYPE, "creation", "<=", f"{to_date} 23:59:59"])

	list_filters = list(scope_filters)
	if status == "Open":
		list_filters.append(
			[OPERATION_DOCTYPE, "status", "in", ["Pending Finalize", "Needs Review"]]
		)
	elif status != "All":
		list_filters.append([OPERATION_DOCTYPE, "status", "=", status])

	search = str(filters.get("search") or "").strip()
	or_filters = []
	if search:
		pattern = f"%{search}%"
		or_filters = [
			[OPERATION_DOCTYPE, "source_name", "like", pattern],
			[OPERATION_DOCTYPE, "reservation_reference", "like", pattern],
			[OPERATION_DOCTYPE, "reason_code", "like", pattern],
			[OPERATION_DOCTYPE, "last_error", "like", pattern],
		]
	return list_filters, scope_filters, or_filters


def _count_rows(filters, or_filters) -> int:
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=["count(name) as count"],
		limit_page_length=1,
	)
	return int(rows[0].get("count") or 0) if rows else 0


def _status_counts(filters, or_filters) -> dict[str, int]:
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=["status", "count(name) as count"],
		group_by="status",
		limit_page_length=10,
	)
	return {str(row.status): int(row.get("count") or 0) for row in rows}


def _record_review_failure(
	operation,
	*,
	action: str,
	reason: str,
	reason_code: str,
	message: str,
) -> None:
	operation.reason_code = str(reason_code or "")[:140]
	operation.remote_message = str(message or "")[:1000]
	operation.last_error = str(message or reason_code or "")[:1000]
	_apply_review_metadata(operation, action, reason)
	_save_review_operation(operation)


def _apply_review_metadata(operation, action: str, reason: str) -> None:
	operation.review_action = str(action or "")[:140]
	operation.review_reason = str(reason or "")[:1000]
	operation.reviewed_by = getattr(frappe.session, "user", None) or "Administrator"
	operation.reviewed_on = now_datetime()


def _save_review_operation(operation, *, reconciliation: bool = False) -> None:
	operation.flags.allow_retailedge_quota_operation_update = True
	if reconciliation:
		operation.flags.allow_retailedge_quota_operation_reconcile = True
	operation.save(ignore_permissions=True)


def _lock_operation(name: str) -> None:
	quote = chr(96)
	table = f"{quote}tab{OPERATION_DOCTYPE}{quote}"
	rows = frappe.db.sql(
		f"select name from {table} where name = %s for update",
		(name,),
		as_dict=True,
	)
	if not rows:
		frappe.throw(_("Quota review item was not found."), frappe.DoesNotExistError)


def _source_docstatus(operation) -> int:
	return int(
		frappe.db.get_value(
			operation.source_doctype,
			operation.source_name,
			"docstatus",
		)
		or 0
	)


def _review_reserve_key(operation) -> str:
	nonce = frappe.generate_hash(length=12)
	raw = f"retail:quota-review:{operation.operation_key}:reserve:{nonce}"
	if len(raw) <= 140:
		return raw
	return "retail:quota-review:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _review_reason(value: str | None) -> str:
	resolved = str(value or "").strip()
	if len(resolved) < 5:
		frappe.throw(_("Provide a review reason of at least 5 characters."), frappe.ValidationError)
	if len(resolved) > 1000:
		frappe.throw(_("Review reason cannot exceed 1000 characters."), frappe.ValidationError)
	return resolved


def _operation_name(value: str) -> str:
	resolved = str(value or "").strip()
	if not resolved:
		frappe.throw(_("Quota operation is required."), frappe.ValidationError)
	return resolved


def _operation_result(operation) -> dict:
	return {
		"name": operation.name,
		"status": operation.status,
		"source_doctype": operation.source_doctype,
		"source_name": operation.source_name,
		"reservation_reference": operation.reservation_reference,
		"reason_code": operation.reason_code or "",
		"last_error": operation.last_error or "",
		"review_action": operation.review_action or "",
		"review_reason": operation.review_reason or "",
		"reviewed_by": operation.reviewed_by or "",
		"reviewed_on": operation.reviewed_on,
	}


def _assert_read_access() -> None:
	if getattr(frappe.session, "user", None) == "Administrator":
		return
	if not frappe.has_permission(OPERATION_DOCTYPE, ptype="read"):
		frappe.throw(_("You are not allowed to review quota operations."), frappe.PermissionError)


def _can_mutate() -> bool:
	if getattr(frappe.session, "user", None) == "Administrator":
		return True
	return bool(_MUTATION_ROLES.intersection(set(frappe.get_roles(frappe.session.user))))


def _assert_mutation_access() -> None:
	if not _can_mutate():
		frappe.throw(
			_("You are not allowed to reconcile quota operations."),
			frappe.PermissionError,
		)


def _require_post() -> None:
	request = getattr(frappe.local, "request", None)
	if request and str(getattr(request, "method", "") or "").upper() != "POST":
		frappe.throw(_("This action requires HTTP POST."), frappe.PermissionError)
