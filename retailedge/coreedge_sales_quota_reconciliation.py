from __future__ import annotations

import hashlib
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	finalize_sales_quota_operation,
	get_sales_transaction_quota_config,
)
from retailedge.integrations.coreedge_remote_usage import (
	CoreEdgeRemoteUsageError,
	get_remote_usage_client,
)
from retailedge.reporting_scope import get_report_branch_scope, validate_report_scope


REVIEW_EVENT_DOCTYPE = "RetailEdge CoreEdge Quota Review Event"
_MUTATION_ROLES = {
	"System Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
}
_MAX_REPORT_ROWS = 1000


@frappe.whitelist()
def retry_quota_finalization(operation_name: str, reason: str) -> dict:
	_require_post()
	_assert_reconciliation_operator()
	reason = _required_reason(reason)
	operation = _get_scoped_operation(operation_name)

	if operation.status not in {"Pending Finalize", "Needs Review"}:
		frappe.throw(
			_("Only Pending Finalize or Needs Review quota operations can be retried."),
			frappe.ValidationError,
		)
	if not operation.reservation_reference:
		frappe.throw(
			_("This quota operation has no reservation to finalize."),
			frappe.ValidationError,
		)

	previous_status = operation.status
	try:
		result = finalize_sales_quota_operation(
			operation.name,
			allow_needs_review=True,
		)
	except Exception as exc:
		_write_review_event(
			operation=operation,
			action="Retry Finalization",
			result="Failed",
			previous_status=previous_status,
			new_status=previous_status,
			reason=reason,
			reason_code="FINALIZE_RETRY_EXCEPTION",
			message=_safe_message(exc),
		)
		raise

	operation.reload()
	_write_review_event(
		operation=operation,
		action="Retry Finalization",
		result=_event_result_for_status(operation.status),
		previous_status=previous_status,
		new_status=operation.status,
		reason=reason,
		reason_code=operation.reason_code or result.get("reason_code"),
		message=operation.last_error or operation.remote_message or "",
	)
	return {
		"ok": operation.status == "Finalized",
		"status": operation.status,
		"operation": operation.name,
		"source_doctype": operation.source_doctype,
		"source_name": operation.source_name,
		"reservation_reference": operation.reservation_reference,
		"reason_code": operation.reason_code or "",
		"message": operation.last_error or operation.remote_message or "",
	}


@frappe.whitelist()
def reconcile_unreserved_quota_operation(operation_name: str, reason: str) -> dict:
	_require_post()
	_assert_reconciliation_operator()
	reason = _required_reason(reason)
	operation = _get_scoped_operation(operation_name)

	if operation.status != "Needs Review":
		frappe.throw(
			_("Only Needs Review quota operations can use unreserved reconciliation."),
			frappe.ValidationError,
		)
	if operation.reservation_reference:
		frappe.throw(
			_("This quota operation already has a reservation; retry finalization instead."),
			frappe.ValidationError,
		)
	if operation.reason_code != "FAIL_OPEN_UNRESERVED":
		frappe.throw(
			_("Only audited fail-open sales can use unreserved reconciliation."),
			frappe.ValidationError,
		)

	previous_status = operation.status
	source = _get_source_state(operation)
	client = get_remote_usage_client()
	status_key = _review_idempotency_key(operation.name, "status")
	try:
		status_response = client.get_usage_status(
			operation.entitlement_key,
			requested_units=int(operation.units or 1),
			request_id=status_key,
			correlation_id=f"{operation.source_doctype}:{operation.source_name}",
			source_path="RetailEdge Sales Quota Reconciliation",
		)
	except CoreEdgeRemoteUsageError as exc:
		message = _safe_message(exc)
		_update_review_failure(operation, "QUOTA_STATUS_UNAVAILABLE", message)
		_write_review_event(
			operation=operation,
			action="Reconcile Unreserved",
			result="Failed",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code="QUOTA_STATUS_UNAVAILABLE",
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	status_data = status_response.get("data") or {}
	quota_status = status_data.get("quota") or {}
	if not status_data.get("ok"):
		reason_code = status_data.get("reason_code") or "QUOTA_STATUS_REJECTED"
		message = status_data.get("message") or _("CoreEdge quota status could not be evaluated.")
		_update_review_failure(operation, reason_code, message)
		_write_review_event(
			operation=operation,
			action="Reconcile Unreserved",
			result="Blocked",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code=reason_code,
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	period_check = _check_source_in_current_quota_period(
		source_date=source["event_date"],
		quota=quota_status,
	)
	if not period_check["allowed"]:
		_update_review_failure(
			operation,
			period_check["reason_code"],
			period_check["message"],
		)
		_write_review_event(
			operation=operation,
			action="Reconcile Unreserved",
			result="Blocked",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code=period_check["reason_code"],
			message=period_check["message"],
		)
		return _reconciliation_response(operation, ok=False)

	attempt = _next_review_attempt(operation.name)
	reserve_key = _review_idempotency_key(operation.name, "reserve", attempt)
	finalize_key = _review_idempotency_key(operation.name, "finalize", attempt)
	release_key = _review_idempotency_key(operation.name, "release", attempt)
	config = get_sales_transaction_quota_config()

	try:
		reserve_response = client.reserve_usage(
			operation.entitlement_key,
			int(operation.units or 1),
			reserve_key,
			expires_in_seconds=config.reservation_seconds,
			reference_doctype=operation.source_doctype,
			reference_name=operation.source_name,
			request_id=reserve_key,
			correlation_id=f"{operation.source_doctype}:{operation.source_name}",
			source_path="RetailEdge Sales Quota Reconciliation",
		)
	except CoreEdgeRemoteUsageError as exc:
		message = _safe_message(exc)
		_update_review_failure(operation, "QUOTA_RESERVE_UNAVAILABLE", message)
		_write_review_event(
			operation=operation,
			action="Reconcile Unreserved",
			result="Failed",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code="QUOTA_RESERVE_UNAVAILABLE",
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	reserve_data = reserve_response.get("data") or {}
	quota = reserve_data.get("quota") or {}
	if not reserve_data.get("ok"):
		reason_code = reserve_data.get("reason_code") or quota.get("reason_code") or "QUOTA_RESERVE_BLOCKED"
		message = reserve_data.get("message") or quota.get("message") or _("CoreEdge quota reservation was blocked.")
		_update_review_failure(operation, reason_code, message)
		_write_review_event(
			operation=operation,
			action="Reconcile Unreserved",
			result="Blocked",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code=reason_code,
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	reservation_reference = str(quota.get("reservation_reference") or "").strip()
	if quota.get("status") != "Active" or not reservation_reference:
		message = _("CoreEdge did not return an active quota reservation.")
		_update_review_failure(operation, "QUOTA_RESERVATION_NOT_ACTIVE", message)
		_write_review_event(
			operation=operation,
			action="Reconcile Unreserved",
			result="Failed",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code="QUOTA_RESERVATION_NOT_ACTIVE",
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	operation.status = "Pending Finalize"
	operation.reservation_reference = reservation_reference
	operation.reservation_expires_on = quota.get("expires_on")
	operation.reserve_idempotency_key = reserve_key
	operation.finalize_idempotency_key = finalize_key
	operation.release_idempotency_key = release_key
	operation.reserved_on = now_datetime()
	operation.warning = 1 if quota.get("warning") else 0
	operation.reason_code = quota.get("reason_code") or "RECONCILIATION_RESERVED"
	operation.remote_message = quota.get("message") or ""
	operation.last_error = None
	operation.flags.allow_retailedge_quota_operation_update = True
	operation.flags.allow_retailedge_quota_reconciliation = True
	operation.save(ignore_permissions=True)

	result = finalize_sales_quota_operation(operation.name)
	operation.reload()
	_write_review_event(
		operation=operation,
		action="Reconcile Unreserved",
		result=_event_result_for_status(operation.status),
		previous_status=previous_status,
		new_status=operation.status,
		reason=reason,
		reason_code=operation.reason_code or result.get("reason_code"),
		message=operation.last_error or operation.remote_message or "",
	)
	return _reconciliation_response(operation, ok=operation.status == "Finalized")


def get_quota_reconciliation_rows(
	filters: dict[str, Any] | frappe._dict | None = None,
	*,
	user: str | None = None,
	limit: int = 500,
) -> dict:
	filters = dict(filters or {})
	reader = user or frappe.session.user
	if not frappe.has_permission(OPERATION_DOCTYPE, "read", user=reader):
		frappe.throw(_("You do not have permission to view quota reconciliation."), frappe.PermissionError)

	company = _clean_scalar(filters.get("company"), "Company")
	if not company:
		company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required for quota reconciliation."), frappe.ValidationError)
	if not frappe.has_permission("Company", "read", doc=company, user=reader):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)

	branch = _clean_scalar(filters.get("branch"), "Branch")
	scope = validate_report_scope(
		company=company,
		branch=branch,
		user=reader,
		require_branch_when_restricted=False,
	)
	query_filters: dict[str, Any] = {"company": company}
	if branch:
		query_filters["branch"] = branch
	elif scope.get("restricted"):
		allowed_branches = list(scope.get("allowed_branches") or [])
		query_filters["branch"] = ["in", allowed_branches] if allowed_branches else "__never__"

	status = _clean_scalar(filters.get("status"), "Status")
	if status:
		query_filters["status"] = status
	elif not filters.get("include_finalized"):
		query_filters["status"] = ["in", ["Needs Review", "Pending Finalize"]]

	for fieldname in ("source_doctype", "reason_code"):
		value = _clean_scalar(filters.get(fieldname), fieldname.replace("_", " ").title())
		if value:
			query_filters[fieldname] = value

	from_date = _clean_scalar(filters.get("from_date"), "From Date")
	to_date = _clean_scalar(filters.get("to_date"), "To Date")
	if from_date and to_date:
		query_filters["creation"] = ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]
	elif from_date:
		query_filters["creation"] = [">=", f"{from_date} 00:00:00"]
	elif to_date:
		query_filters["creation"] = ["<=", f"{to_date} 23:59:59"]

	resolved_limit = max(1, min(int(limit or 500), _MAX_REPORT_ROWS))
	rows = frappe.get_list(
		OPERATION_DOCTYPE,
		filters=query_filters,
		fields=[
			"name",
			"creation",
			"status",
			"company",
			"branch",
			"source_doctype",
			"source_name",
			"entitlement_key",
			"units",
			"reservation_reference",
			"reservation_expires_on",
			"reason_code",
			"remote_message",
			"attempt_count",
			"last_attempt_on",
			"last_error",
			"finalized_on",
		],
		order_by="creation desc",
		limit_page_length=resolved_limit + 1,
	)
	truncated = len(rows) > resolved_limit
	rows = rows[:resolved_limit]
	for row in rows:
		row["recommended_action"] = _recommended_action(row)
		row["can_reconcile"] = int(_can_mutate_quota_review(user=reader))
	return {
		"rows": rows,
		"summary": _build_summary(rows, truncated=truncated),
		"truncated": truncated,
		"scope": {
			"company": company,
			"branch": branch,
			"restricted": bool(scope.get("restricted")),
			"allowed_branches": list(scope.get("allowed_branches") or []),
		},
	}


def _get_scoped_operation(operation_name: str):
	operation_name = str(operation_name or "").strip()
	if not operation_name:
		frappe.throw(_("Quota Operation is required."), frappe.ValidationError)
	operation = frappe.get_doc(OPERATION_DOCTYPE, operation_name)
	operation.check_permission("read")
	company = str(operation.company or "").strip()
	if not company:
		frappe.throw(_("Quota Operation has no Company scope."), frappe.PermissionError)
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)

	scope = get_report_branch_scope(company, user=frappe.session.user)
	branch = str(operation.branch or "").strip()
	if scope.get("restricted"):
		allowed = set(scope.get("allowed_branches") or [])
		if not branch or branch not in allowed:
			frappe.throw(
				_("You do not have access to this quota operation's Branch."),
				frappe.PermissionError,
			)

	if not frappe.has_permission(
		operation.source_doctype,
		"read",
		doc=operation.source_name,
	):
		frappe.throw(
			_("You do not have permission to view the source sales document."),
			frappe.PermissionError,
		)
	return operation


def _get_source_state(operation) -> dict:
	row = frappe.db.get_value(
		operation.source_doctype,
		operation.source_name,
		["docstatus", "posting_date", "transaction_date", "creation"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("The source sales document no longer exists."), frappe.DoesNotExistError)
	if int(row.docstatus or 0) not in {1, 2}:
		frappe.throw(
			_("Only submitted or subsequently cancelled sales can be reconciled."),
			frappe.ValidationError,
		)
	candidate = row.posting_date or row.transaction_date or row.creation
	if not candidate:
		frappe.throw(
			_("The source sale has no reliable transaction date for quota reconciliation."),
			frappe.ValidationError,
		)
	return {"docstatus": int(row.docstatus or 0), "event_date": getdate(candidate)}


def _check_source_in_current_quota_period(*, source_date, quota: dict) -> dict:
	period_start = getdate(quota.get("period_start")) if quota.get("period_start") else None
	period_end = getdate(quota.get("period_end")) if quota.get("period_end") else None
	if period_start and source_date < period_start:
		return {
			"allowed": False,
			"reason_code": "OUTSIDE_CURRENT_QUOTA_PERIOD",
			"message": _("The original sale belongs to an earlier CoreEdge quota period."),
		}
	if period_end and source_date > period_end:
		return {
			"allowed": False,
			"reason_code": "OUTSIDE_CURRENT_QUOTA_PERIOD",
			"message": _("The original sale does not belong to the current CoreEdge quota period."),
		}
	return {"allowed": True, "reason_code": "CURRENT_QUOTA_PERIOD", "message": ""}


def _update_review_failure(operation, reason_code: str, message: str) -> None:
	operation.reason_code = str(reason_code or "")[:140] or None
	operation.remote_message = str(message or "")[:1000] or None
	operation.last_error = str(message or "")[:1000] or None
	operation.flags.allow_retailedge_quota_operation_update = True
	operation.save(ignore_permissions=True)


def _write_review_event(
	*,
	operation,
	action: str,
	result: str,
	previous_status: str,
	new_status: str,
	reason: str,
	reason_code,
	message,
) -> None:
	event = frappe.get_doc(
		{
			"doctype": REVIEW_EVENT_DOCTYPE,
			"quota_operation": operation.name,
			"action": action,
			"result": result,
			"previous_status": previous_status,
			"new_status": new_status,
			"company": operation.company,
			"branch": operation.branch,
			"source_doctype": operation.source_doctype,
			"source_name": operation.source_name,
			"entitlement_key": operation.entitlement_key,
			"reservation_reference": operation.reservation_reference,
			"reason": reason,
			"reason_code": str(reason_code or "")[:140] or None,
			"message": str(message or "")[:1000] or None,
			"reviewed_on": now_datetime(),
			"reviewed_by": frappe.session.user,
		}
	)
	event.flags.allow_retailedge_quota_review_event = True
	event.insert(ignore_permissions=True)


def _assert_reconciliation_operator() -> None:
	if not _can_mutate_quota_review(user=frappe.session.user):
		frappe.throw(
			_("You are not allowed to reconcile CoreEdge sales quota operations."),
			frappe.PermissionError,
		)


def _can_mutate_quota_review(*, user: str) -> bool:
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)).intersection(_MUTATION_ROLES))


def _required_reason(value: str) -> str:
	resolved = str(value or "").strip()
	if len(resolved) < 5:
		frappe.throw(_("Provide a reconciliation reason of at least 5 characters."), frappe.ValidationError)
	if len(resolved) > 500:
		frappe.throw(_("Reconciliation reason cannot exceed 500 characters."), frappe.ValidationError)
	return resolved


def _next_review_attempt(operation_name: str) -> int:
	return int(
		frappe.db.count(REVIEW_EVENT_DOCTYPE, {"quota_operation": operation_name}) or 0
	) + 1


def _review_idempotency_key(operation_name: str, action: str, attempt: int | None = None) -> str:
	raw = f"retail:quota-review:{operation_name}:{action}"
	if attempt is not None:
		raw = f"{raw}:{max(1, int(attempt))}"
	if len(raw) <= 140:
		return raw
	digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
	return f"retail:quota-review:{action}:{digest}"


def _event_result_for_status(status: str) -> str:
	if status == "Finalized":
		return "Finalized"
	if status == "Pending Finalize":
		return "Pending Finalize"
	return "Needs Review"


def _recommended_action(row: dict) -> str:
	status = str(row.get("status") or "")
	reservation = str(row.get("reservation_reference") or "")
	reason_code = str(row.get("reason_code") or "")
	if status == "Finalized":
		return _("No action required")
	if reservation:
		return _("Retry CoreEdge finalization")
	if status == "Needs Review" and reason_code == "FAIL_OPEN_UNRESERVED":
		return _("Reconcile current CoreEdge quota period")
	if status == "Pending Finalize":
		return _("Retry finalization")
	return _("Manual CoreEdge review required")


def _build_summary(rows: list[dict], *, truncated: bool) -> dict:
	return {
		"needs_review": sum(1 for row in rows if row.get("status") == "Needs Review"),
		"pending_finalize": sum(1 for row in rows if row.get("status") == "Pending Finalize"),
		"finalized": sum(1 for row in rows if row.get("status") == "Finalized"),
		"visible_rows": len(rows),
		"truncated": int(truncated),
	}


def _reconciliation_response(operation, *, ok: bool) -> dict:
	return {
		"ok": ok,
		"status": operation.status,
		"operation": operation.name,
		"source_doctype": operation.source_doctype,
		"source_name": operation.source_name,
		"reservation_reference": operation.reservation_reference,
		"reason_code": operation.reason_code or "",
		"message": operation.last_error or operation.remote_message or "",
	}


def _clean_scalar(value: Any, label: str) -> str:
	if value in (None, ""):
		return ""
	if isinstance(value, (list, tuple, dict, set)):
		frappe.throw(_("{0} must be a single value.").format(label), frappe.ValidationError)
	return str(value).strip()


def _safe_message(exc: Exception) -> str:
	return str(exc or exc.__class__.__name__)[:1000]


def _require_post() -> None:
	request = getattr(getattr(frappe, "local", None), "request", None)
	if request is not None and str(getattr(request, "method", "")).upper() != "POST":
		frappe.throw(_("This action requires HTTP POST."), frappe.PermissionError)
