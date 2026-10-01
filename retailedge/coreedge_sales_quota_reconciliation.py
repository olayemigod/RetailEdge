from __future__ import annotations

import hashlib
from typing import Any

import frappe
from frappe import _
from frappe.desk.search import validate_and_sanitize_search_inputs
from frappe.utils import cint, get_datetime, getdate, now_datetime

from retailedge.coreedge_sales_quota import (
	OPERATION_DOCTYPE,
	finalize_sales_quota_operation,
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
@validate_and_sanitize_search_inputs
def search_quota_reconciliation_branches(
	doctype,
	txt,
	searchfield,
	start,
	page_len,
	filters,
):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	company = str(filters.get("company") or "").strip()
	if not company:
		return []
	if not frappe.has_permission("Company", "read", doc=company):
		return []

	try:
		scope = get_report_branch_scope(company, user=frappe.session.user)
	except (frappe.PermissionError, frappe.ValidationError):
		return []

	profile_filters: list[list[Any]] = [
		["RetailEdge Branch Profile", "company", "=", company],
		["RetailEdge Branch Profile", "enabled", "=", 1],
	]
	if txt:
		profile_filters.append(
			["RetailEdge Branch Profile", "branch", "like", f"%{txt}%"]
		)
	if scope.get("restricted"):
		allowed = [
			str(value).strip()
			for value in dict.fromkeys(scope.get("allowed_branches") or [])
			if str(value or "").strip()
		]
		if not allowed:
			return []
		profile_filters.append(
			["RetailEdge Branch Profile", "branch", "in", allowed]
		)

	start = max(cint(start), 0)
	page_len = min(cint(page_len) or 20, 20)
	rows = frappe.get_list(
		"RetailEdge Branch Profile",
		filters=profile_filters,
		fields=["branch"],
		order_by="branch asc",
		limit_start=start,
		limit_page_length=page_len,
	)
	branches = [row.get("branch") for row in rows if row.get("branch")]
	return [(branch,) for branch in dict.fromkeys(branches)]


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
		"reconciliation_case_reference": operation.reconciliation_case_reference or "",
		"reconciliation_case_status": operation.reconciliation_case_status or "",
		"reconciliation_submitted_on": operation.reconciliation_submitted_on,
		"reason_code": operation.reason_code or "",
		"message": operation.last_error or operation.remote_message or "",
	}


@frappe.whitelist()
def submit_unreserved_quota_reconciliation_case(operation_name: str, reason: str) -> dict:
	_require_post()
	_assert_reconciliation_operator()
	reason = _required_reason(reason)
	operation = _get_scoped_operation(operation_name)

	if operation.status != "Needs Review":
		frappe.throw(
			_("Only Needs Review quota operations can be submitted for CoreEdge review."),
			frappe.ValidationError,
		)
	if operation.reservation_reference:
		frappe.throw(
			_("This quota operation already has a reservation; retry finalization instead."),
			frappe.ValidationError,
		)
	if operation.reason_code != "FAIL_OPEN_UNRESERVED":
		frappe.throw(
			_("Only audited fail-open sales can use unreserved CoreEdge review."),
			frappe.ValidationError,
		)

	if operation.reconciliation_case_reference:
		return _reconciliation_response(operation, ok=True)

	previous_status = operation.status
	source = _get_source_state(operation)
	attempt = _next_review_attempt(operation.name)
	request_key = _review_idempotency_key(operation.name, "case-submit", attempt)
	client = get_remote_usage_client()

	try:
		response = client.submit_reconciliation_case(
			operation.entitlement_key,
			operation.operation_key,
			"FAIL_OPEN_UNRESERVED",
			int(operation.units or 1),
			operation.source_doctype,
			operation.source_name,
			str(source["occurred_on"]),
			request_key,
			local_status=operation.status,
			local_reason_code=operation.reason_code,
			error_summary=_reconciliation_evidence_summary(operation, source),
			request_id=request_key,
			correlation_id=f"{operation.source_doctype}:{operation.source_name}",
			source_path="RetailEdge Sales Quota Reconciliation",
		)
	except CoreEdgeRemoteUsageError as exc:
		message = _safe_message(exc)
		_update_case_submission_failure(operation, message)
		_write_review_event(
			operation=operation,
			action="Submit CoreEdge Review",
			result="Failed",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code="COREDGE_RECONCILIATION_SUBMISSION_UNAVAILABLE",
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	data = response.get("data") or {}
	case = data.get("case") or {}
	if not data.get("ok"):
		reason_code = data.get("reason_code") or "COREDGE_RECONCILIATION_SUBMISSION_REJECTED"
		message = data.get("message") or _("CoreEdge rejected the reconciliation evidence.")
		_update_case_submission_failure(operation, message)
		_write_review_event(
			operation=operation,
			action="Submit CoreEdge Review",
			result="Blocked",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code=reason_code,
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	case_reference = str(case.get("case_reference") or "").strip()
	if not case_reference:
		message = _("CoreEdge accepted the request without returning a reconciliation Case Reference.")
		_update_case_submission_failure(operation, message)
		_write_review_event(
			operation=operation,
			action="Submit CoreEdge Review",
			result="Failed",
			previous_status=previous_status,
			new_status=operation.status,
			reason=reason,
			reason_code="COREDGE_RECONCILIATION_CASE_REFERENCE_MISSING",
			message=message,
		)
		return _reconciliation_response(operation, ok=False)

	operation.reconciliation_case_reference = case_reference
	operation.reconciliation_case_status = str(case.get("case_status") or "Open")[:140]
	operation.reconciliation_case_evidence_hash = str(case.get("evidence_hash") or "")[:140] or None
	operation.reconciliation_submitted_on = case.get("submitted_on") or now_datetime()
	operation.reconciliation_last_idempotency_key = request_key
	operation.last_error = None
	operation.flags.allow_retailedge_quota_operation_update = True
	operation.flags.allow_retailedge_quota_case_submission = True
	operation.save(ignore_permissions=True)

	_write_review_event(
		operation=operation,
		action="Submit CoreEdge Review",
		result="Submitted",
		previous_status=previous_status,
		new_status=operation.status,
		reason=reason,
		reason_code=str(data.get("reason_code") or case.get("case_status") or "RECONCILIATION_CASE_SUBMITTED"),
		message=str(data.get("message") or _("CoreEdge reconciliation case submitted for platform review.")),
	)
	return _reconciliation_response(operation, ok=True)


@frappe.whitelist()
def reconcile_unreserved_quota_operation(operation_name: str, reason: str) -> dict:
	"""Backward-compatible alias for the governed CoreEdge case-submission workflow."""
	return submit_unreserved_quota_reconciliation_case(operation_name, reason)


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
			"reconciliation_case_reference",
			"reconciliation_case_status",
			"reconciliation_submitted_on",
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
	meta = frappe.get_meta(operation.source_doctype)
	fields = ["docstatus", "creation"]
	for fieldname in ("posting_date", "posting_time", "transaction_date"):
		if meta.has_field(fieldname):
			fields.append(fieldname)
	row = frappe.db.get_value(
		operation.source_doctype,
		operation.source_name,
		fields,
		as_dict=True,
	)
	if not row:
		frappe.throw(_("The source sales document no longer exists."), frappe.DoesNotExistError)
	if int(row.docstatus or 0) != 1:
		frappe.throw(
			_("Only currently submitted sales can be submitted as committed usage evidence."),
			frappe.ValidationError,
		)

	if row.get("posting_date"):
		posting_time = str(row.get("posting_time") or "00:00:00")
		occurred_on = get_datetime(f"{row.get('posting_date')} {posting_time}")
	elif row.get("transaction_date"):
		occurred_on = get_datetime(row.get("transaction_date"))
	elif row.get("creation"):
		occurred_on = get_datetime(row.get("creation"))
	else:
		frappe.throw(
			_("The source sale has no reliable transaction timestamp for quota reconciliation."),
			frappe.ValidationError,
		)

	return {
		"docstatus": int(row.docstatus or 0),
		"event_date": getdate(occurred_on),
		"occurred_on": occurred_on,
	}


def _reconciliation_evidence_summary(operation, source: dict) -> str:
	message = str(operation.remote_message or "").strip()
	parts = [
		"RetailEdge recorded FAIL_OPEN_UNRESERVED after the original CoreEdge quota reservation was unavailable.",
		f"Source document status: {int(source.get('docstatus') or 0)}.",
	]
	if message:
		parts.append(f"Original CoreEdge error: {message}")
	return " ".join(parts)[:1000]


def _update_case_submission_failure(operation, message: str) -> None:
	operation.last_error = str(message or "")[:1000] or None
	operation.flags.allow_retailedge_quota_operation_update = True
	operation.save(ignore_permissions=True)


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
			"reconciliation_case_reference": operation.reconciliation_case_reference,
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
		if row.get("reconciliation_case_reference"):
			return _("CoreEdge review submitted")
		return _("Submit to CoreEdge review")
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
		"reconciliation_case_reference": operation.reconciliation_case_reference or "",
		"reconciliation_case_status": operation.reconciliation_case_status or "",
		"reconciliation_submitted_on": operation.reconciliation_submitted_on,
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
