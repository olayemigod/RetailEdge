from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from retailedge.integrations.coreedge_remote_usage import (
	CoreEdgeRemoteUsageError,
	CoreEdgeRemoteUsageUnavailable,
	get_remote_usage_client,
)


OPERATION_DOCTYPE = "RetailEdge CoreEdge Quota Operation"
DEFAULT_ENTITLEMENT_KEY = "SALES_TRANSACTIONS"
FINALIZE_JOB = "retailedge.coreedge_sales_quota.finalize_sales_quota_operation"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}
_RECONCILABLE_REASONS = {
	"FAIL_OPEN_UNRESERVED",
	"RESERVATION_EXPIRED",
	"RESERVATION_ALREADY_RELEASED",
}


@dataclass(frozen=True, slots=True)
class SalesTransactionQuotaConfig:
	enabled: bool = False
	entitlement_key: str = DEFAULT_ENTITLEMENT_KEY
	fail_closed: bool = True
	reservation_seconds: int = 3600

	@classmethod
	def from_mapping(cls, values: dict[str, Any] | None = None):
		values = values or {}
		return cls(
			enabled=_parse_bool(values.get("retailedge_sales_quota_enabled"), default=False),
			entitlement_key=(
				str(
					values.get("retailedge_sales_quota_entitlement_key")
					or DEFAULT_ENTITLEMENT_KEY
				).strip()
				or DEFAULT_ENTITLEMENT_KEY
			),
			fail_closed=_parse_bool(
				values.get("retailedge_sales_quota_fail_closed"),
				default=True,
			),
			reservation_seconds=_parse_reservation_seconds(
				values.get("retailedge_sales_quota_reservation_seconds")
			),
		)

	def sanitized(self) -> dict:
		return {
			"enabled": self.enabled,
			"entitlement_key": self.entitlement_key,
			"fail_closed": self.fail_closed,
			"reservation_seconds": self.reservation_seconds,
		}


def get_sales_transaction_quota_config() -> SalesTransactionQuotaConfig:
	return SalesTransactionQuotaConfig.from_mapping(frappe.conf)


def get_sales_transaction_quota_readiness() -> dict:
	config = get_sales_transaction_quota_config()
	return config.sanitized()


def before_submit_sales_transaction_quota(doc, method=None):
	config = get_sales_transaction_quota_config()
	if not config.enabled:
		return

	eligible, _count_reason = is_counted_sales_transaction(doc)
	if not eligible:
		return

	operation_key = make_sales_quota_operation_key(doc.doctype, doc.name)
	existing = frappe.db.get_value(
		OPERATION_DOCTYPE,
		{"operation_key": operation_key},
		["name", "status"],
		as_dict=True,
	)
	if existing:
		if existing.status in {"Pending Finalize", "Finalized"}:
			return
		frappe.throw(
			_("The existing quota operation for this document requires administrator review."),
			title=_("Sales Transaction Quota"),
		)

	attempt = frappe.generate_hash(length=12)
	reserve_key = _idempotency_key(doc.doctype, doc.name, "reserve", attempt)
	finalize_key = _idempotency_key(doc.doctype, doc.name, "finalize", attempt)
	release_key = _idempotency_key(doc.doctype, doc.name, "release", attempt)

	try:
		response = get_remote_usage_client().reserve_usage(
			config.entitlement_key,
			1,
			reserve_key,
			expires_in_seconds=config.reservation_seconds,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			request_id=reserve_key,
			correlation_id=f"{doc.doctype}:{doc.name}",
			source_path="RetailEdge Sales Submit",
		)
	except CoreEdgeRemoteUsageError as exc:
		_handle_remote_unavailable(config, doc, exc)
		_insert_quota_operation(
			doc=doc,
			operation_key=operation_key,
			entitlement_key=config.entitlement_key,
			reservation_reference=None,
			reservation_expires_on=None,
			reserve_idempotency_key=reserve_key,
			finalize_idempotency_key=finalize_key,
			release_idempotency_key=release_key,
			warning=False,
			reason_code="FAIL_OPEN_UNRESERVED",
			remote_message=_safe_error(exc),
			status="Needs Review",
		)
		return

	data = response.get("data") or {}
	quota = data.get("quota") or {}
	if not data.get("ok"):
		_log_quota_failure(
			doc,
			"CoreEdge blocked the sales transaction quota reservation.",
			data.get("reason_code"),
		)
		frappe.throw(
			_("This sale cannot be submitted because the configured transaction limit is unavailable."),
			title=_("Sales Transaction Limit"),
		)

	reservation_reference = str(quota.get("reservation_reference") or "").strip()
	if quota.get("status") != "Active" or not reservation_reference:
		_log_quota_failure(
			doc,
			"CoreEdge returned a non-active sales quota reservation.",
			quota.get("reason_code"),
		)
		frappe.throw(
			_("This sale cannot be submitted because a valid quota reservation was not obtained."),
			title=_("Sales Transaction Limit"),
		)

	_register_after_rollback(
		lambda: _release_rolled_back_reservation(
			reservation_reference=reservation_reference,
			release_idempotency_key=release_key,
			doc_doctype=doc.doctype,
			doc_name=doc.name,
		)
	)

	operation = _insert_quota_operation(
		doc=doc,
		operation_key=operation_key,
		entitlement_key=config.entitlement_key,
		reservation_reference=reservation_reference,
		reservation_expires_on=quota.get("expires_on"),
		reserve_idempotency_key=reserve_key,
		finalize_idempotency_key=finalize_key,
		release_idempotency_key=release_key,
		warning=bool(quota.get("warning")),
		reason_code=quota.get("reason_code"),
		remote_message=quota.get("message"),
	)

	_register_after_commit(
		lambda: _enqueue_finalize_operation(operation.name)
	)


def is_counted_sales_transaction(doc) -> tuple[bool, str]:
	if not doc or doc.doctype not in {"Sales Invoice", "POS Invoice"}:
		return False, "unsupported_doctype"
	if int(getattr(doc, "is_return", 0) or 0):
		return False, "return_or_credit_note"
	if doc.doctype == "Sales Invoice" and int(getattr(doc, "is_consolidated", 0) or 0):
		return False, "pos_consolidated_sales_invoice"
	return True, "counted_sale"


def make_sales_quota_operation_key(doctype: str, name: str) -> str:
	value = f"{doctype}\x1f{name}"
	return f"resq-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:40]}"


def finalize_sales_quota_operation(operation_name: str) -> dict:
	_lock_operation(operation_name)
	operation = frappe.get_doc(OPERATION_DOCTYPE, operation_name)
	if operation.status == "Finalized":
		return _serialize_operation(operation)
	if operation.status == "Needs Review":
		return _serialize_operation(operation)

	operation.attempt_count = int(operation.attempt_count or 0) + 1
	operation.last_attempt_on = now_datetime()

	docstatus = frappe.db.get_value(
		operation.source_doctype,
		operation.source_name,
		"docstatus",
	)
	if int(docstatus or 0) not in {1, 2}:
		_mark_needs_review(
			operation,
			"Source document has not reached a submitted transaction state; "
			"quota finalization was not attempted.",
		)
		return _serialize_operation(operation)

	finalize_attempt_key = _retry_idempotency_key(
		operation.finalize_idempotency_key,
		int(operation.attempt_count or 0),
	)
	try:
		response = get_remote_usage_client().finalize_usage(
			operation.reservation_reference,
			finalize_attempt_key,
			request_id=finalize_attempt_key,
			correlation_id=f"{operation.source_doctype}:{operation.source_name}",
			source_path="RetailEdge Sales Commit",
		)
	except CoreEdgeRemoteUsageError as exc:
		operation.last_error = _safe_error(exc)
		_save_operation(operation)
		return _serialize_operation(operation)

	data = response.get("data") or {}
	quota = data.get("quota") or {}
	if data.get("ok"):
		operation.status = "Finalized"
		operation.finalized_on = now_datetime()
		operation.reason_code = quota.get("reason_code") or "RESERVATION_FINALIZED"
		operation.remote_message = quota.get("message") or ""
		operation.last_error = None
		_save_operation(operation)
		return _serialize_operation(operation)

	operation.reason_code = data.get("reason_code") or quota.get("reason_code") or ""
	operation.remote_message = data.get("message") or quota.get("message") or ""
	operation.last_error = operation.remote_message or operation.reason_code
	if operation.reason_code in {
		"RESERVATION_EXPIRED",
		"RESERVATION_ALREADY_RELEASED",
		"RESERVATION_NOT_FOUND",
		"USAGE_RESERVATION_ACCESS_DENIED",
	}:
		operation.status = "Needs Review"
	_save_operation(operation)
	return _serialize_operation(operation)


@frappe.whitelist()
def retry_sales_quota_finalize(operation_name: str) -> dict:
	"""Operator-triggered retry for a still-pending quota finalization."""
	_require_post()
	_assert_quota_review_operator()

	operation_name = str(operation_name or "").strip()
	if not operation_name:
		frappe.throw(_("Quota operation is required."), frappe.ValidationError)

	operation = frappe.get_doc(OPERATION_DOCTYPE, operation_name)
	operation.check_permission("read")
	if operation.status != "Pending Finalize":
		frappe.throw(
			_("Only Pending Finalize quota operations can be retried."),
			frappe.ValidationError,
		)
	return finalize_sales_quota_operation(operation.name)


@frappe.whitelist()
def reconcile_sales_quota_operation(operation_name: str, reason: str) -> dict:
	"""Reconcile one committed sale through the governed CoreEdge V2.6E contract."""
	_require_post()
	_assert_quota_review_operator()
	reason = _required_reconciliation_reason(reason)

	operation_name = str(operation_name or "").strip()
	if not operation_name:
		frappe.throw(_("Quota operation is required."), frappe.ValidationError)

	_lock_operation(operation_name)
	operation = frappe.get_doc(OPERATION_DOCTYPE, operation_name)
	operation.check_permission("read")
	if operation.status != "Needs Review":
		frappe.throw(
			_("Only Needs Review quota operations can be reconciled."),
			frappe.ValidationError,
		)
	if str(operation.reason_code or "") not in _RECONCILABLE_REASONS:
		frappe.throw(
			_("This quota operation requires platform review and is not eligible for product-side reconciliation."),
			frappe.ValidationError,
		)

	source = _get_reconciliation_source_document(operation)
	occurred_on = _source_business_occurred_on(source)
	units = int(operation.units or 0)
	if units != 1:
		frappe.throw(
			_("RetailEdge Sales Transaction reconciliation requires exactly one quota unit."),
			frappe.ValidationError,
		)

	operation.reconciliation_attempt_count = int(operation.reconciliation_attempt_count or 0) + 1
	operation.last_reconciliation_attempt_on = now_datetime()
	attempt_key = _idempotency_key(
		operation.source_doctype,
		operation.source_name,
		"reconcile",
		frappe.generate_hash(length=12),
	)

	try:
		response = get_remote_usage_client().reconcile_usage(
			operation.entitlement_key,
			units,
			occurred_on,
			reason,
			attempt_key,
			operation.source_doctype,
			operation.source_name,
			source_reason_code=operation.reason_code,
			request_id=attempt_key,
			correlation_id=f"{operation.source_doctype}:{operation.source_name}",
			source_path="RetailEdge Quota Review",
		)
	except CoreEdgeRemoteUsageError as exc:
		operation.reconciliation_last_error = _safe_error(exc)
		_save_operation(operation)
		return _serialize_operation(operation)

	data = response.get("data") or {}
	result = data.get("reconciliation") or {}
	if data.get("ok") and (
		result.get("reconciled")
		or result.get("already_counted")
		or data.get("status") in {"Applied Current Period", "Recorded Historical", "Already Counted"}
	):
		operation.status = "Reconciled"
		operation.reconciliation_reference = result.get("reconciliation_reference") or None
		operation.reconciliation_status = data.get("status") or result.get("status") or "Reconciled"
		operation.reconciliation_result_code = result.get("reason_code") or ""
		operation.reconciliation_reason = reason
		operation.reconciled_on = now_datetime()
		operation.reconciled_by = frappe.session.user
		operation.reconciliation_last_error = None
		_save_operation(operation)
		return _serialize_operation(operation)

	operation.reconciliation_status = data.get("status") or result.get("status") or "Failed"
	operation.reconciliation_result_code = (
		data.get("reason_code") or result.get("reason_code") or ""
	)
	operation.reconciliation_last_error = (
		data.get("message")
		or result.get("message")
		or operation.reconciliation_result_code
		or _("CoreEdge reconciliation did not complete.")
	)
	_save_operation(operation)
	return _serialize_operation(operation)


def retry_pending_sales_quota_operations(limit: int = 50) -> int:
	try:
		resolved_limit = max(1, min(int(limit or 50), 200))
	except (TypeError, ValueError):
		resolved_limit = 50

	rows = frappe.get_all(
		OPERATION_DOCTYPE,
		filters={"status": "Pending Finalize"},
		fields=["name"],
		order_by="creation asc",
		limit_page_length=resolved_limit,
	)
	queued = 0
	for row in rows:
		if _enqueue_finalize_operation(row.name):
			queued += 1
	return queued


def _enqueue_finalize_operation(operation_name: str) -> bool:
	try:
		frappe.enqueue(
			FINALIZE_JOB,
			queue="short",
			timeout=120,
			job_id=f"retailedge-sales-quota-finalize::{operation_name}",
			deduplicate=True,
			operation_name=operation_name,
		)
		return True
	except Exception:
		frappe.log_error(
			title="RetailEdge CoreEdge Quota Finalize Queue Failed",
			message=frappe.get_traceback(),
		)
		return False


def _register_after_commit(callback) -> None:
	frappe.db.after_commit.add(callback)


def _register_after_rollback(callback) -> None:
	frappe.db.after_rollback.add(callback)


def _assert_quota_review_operator() -> None:
	if frappe.session.user == "Administrator":
		return
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection({"System Manager", "RetailEdge Manager", "RetailEdgeManager"}):
		frappe.throw(
			_("You are not allowed to retry CoreEdge quota finalization."),
			frappe.PermissionError,
		)


def _require_post() -> None:
	request = getattr(frappe.local, "request", None)
	if request is not None and str(getattr(request, "method", "")).upper() != "POST":
		frappe.throw(_("This operation requires an HTTP POST request."), frappe.PermissionError)


def _get_reconciliation_source_document(operation):
	if operation.source_doctype not in {"Sales Invoice", "POS Invoice"}:
		frappe.throw(_("Unsupported quota source document type."), frappe.ValidationError)
	if not frappe.db.exists(operation.source_doctype, operation.source_name):
		frappe.throw(_("The source sales document no longer exists."), frappe.DoesNotExistError)

	source = frappe.get_doc(operation.source_doctype, operation.source_name)
	source.check_permission("read")
	if int(source.docstatus or 0) not in {1, 2}:
		frappe.throw(
			_("The source sales document has not reached a submitted transaction state."),
			frappe.ValidationError,
		)
	eligible, _count_reason = is_counted_sales_transaction(source)
	if not eligible:
		frappe.throw(
			_("The source document is not an eligible counted Sales Transaction."),
			frappe.ValidationError,
		)
	return source


def _source_business_occurred_on(source):
	if not getattr(source, "posting_date", None):
		frappe.throw(
			_("The source sales document does not have a Posting Date."),
			frappe.ValidationError,
		)
	posting_time = getattr(source, "posting_time", None) or "00:00:00"
	try:
		return get_datetime(f"{source.posting_date} {posting_time}")
	except (TypeError, ValueError):
		frappe.throw(
			_("The source sales document Posting Date/Time is invalid."),
			frappe.ValidationError,
		)


def _required_reconciliation_reason(value: str | None) -> str:
	resolved = str(value or "").strip()
	if len(resolved) < 5:
		frappe.throw(
			_("Provide a reconciliation reason of at least 5 characters."),
			frappe.ValidationError,
		)
	if len(resolved) > 500:
		frappe.throw(_("Reconciliation reason cannot exceed 500 characters."), frappe.ValidationError)
	return resolved


def _insert_quota_operation(
	*,
	doc,
	operation_key: str,
	entitlement_key: str,
	reservation_reference: str | None,
	reservation_expires_on,
	reserve_idempotency_key: str,
	finalize_idempotency_key: str,
	release_idempotency_key: str,
	warning: bool,
	reason_code,
	remote_message,
	status: str = "Pending Finalize",
):
	operation = frappe.get_doc(
		{
			"doctype": OPERATION_DOCTYPE,
			"operation_key": operation_key,
			"status": status,
			"source_doctype": doc.doctype,
			"source_name": doc.name,
			"company": getattr(doc, "company", None),
			"branch": getattr(doc, "branch", None),
			"entitlement_key": entitlement_key,
			"units": 1,
			"reservation_reference": reservation_reference,
			"reservation_expires_on": reservation_expires_on,
			"warning": 1 if warning else 0,
			"reason_code": str(reason_code or "")[:140] or None,
			"remote_message": str(remote_message or "")[:1000] or None,
			"reserve_idempotency_key": reserve_idempotency_key,
			"finalize_idempotency_key": finalize_idempotency_key,
			"release_idempotency_key": release_idempotency_key,
			"reserved_on": now_datetime(),
		}
	)
	operation.flags.allow_retailedge_quota_operation_create = True
	operation.insert(ignore_permissions=True)
	return operation


def _release_rolled_back_reservation(
	*,
	reservation_reference: str,
	release_idempotency_key: str,
	doc_doctype: str,
	doc_name: str,
) -> None:
	try:
		response = get_remote_usage_client().release_usage(
			reservation_reference,
			release_idempotency_key,
			"RetailEdge transaction rolled back before database commit.",
			request_id=release_idempotency_key,
			correlation_id=f"{doc_doctype}:{doc_name}",
			source_path="RetailEdge Sales Rollback",
		)
		data = response.get("data") or {}
		if not data.get("ok"):
			frappe.log_error(
				title="RetailEdge CoreEdge Quota Release Rejected",
				message=(
					f"Reservation: {reservation_reference}\n"
					f"Document: {doc_doctype} {doc_name}\n"
					f"Reason: {str(data.get('reason_code') or '')[:140]}\n"
					f"Message: {str(data.get('message') or '')[:500]}"
				),
			)
	except Exception:
		frappe.log_error(
			title="RetailEdge CoreEdge Quota Release Failed",
			message=frappe.get_traceback(),
		)


def _handle_remote_unavailable(config, doc, exc: Exception) -> None:
	_log_quota_failure(
		doc,
		"CoreEdge sales transaction quota service is unavailable.",
		_safe_error(exc),
	)
	availability_failure = isinstance(exc, CoreEdgeRemoteUsageUnavailable)
	if config.fail_closed or not availability_failure:
		frappe.throw(
			_(
				"This sale cannot be submitted because transaction-limit verification "
				"is unavailable or not safely configured."
			),
			title=_("Sales Transaction Access Unavailable"),
		)


def _mark_needs_review(operation, message: str) -> None:
	operation.status = "Needs Review"
	operation.last_error = str(message)[:1000]
	_save_operation(operation)


def _save_operation(operation) -> None:
	operation.flags.allow_retailedge_quota_operation_update = True
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
		frappe.throw(_("RetailEdge quota operation was not found."), frappe.DoesNotExistError)


def _serialize_operation(operation) -> dict:
	return {
		"name": operation.name,
		"status": operation.status,
		"source_doctype": operation.source_doctype,
		"source_name": operation.source_name,
		"entitlement_key": operation.entitlement_key,
		"reservation_reference": operation.reservation_reference,
		"reservation_expires_on": operation.reservation_expires_on,
		"attempt_count": int(operation.attempt_count or 0),
		"last_error": operation.last_error or "",
		"finalized_on": operation.finalized_on,
		"reconciliation_reference": getattr(operation, "reconciliation_reference", None),
		"reconciliation_status": getattr(operation, "reconciliation_status", None),
		"reconciliation_result_code": getattr(operation, "reconciliation_result_code", None),
		"reconciliation_attempt_count": int(
			getattr(operation, "reconciliation_attempt_count", 0) or 0
		),
		"reconciliation_last_error": (
			getattr(operation, "reconciliation_last_error", None) or ""
		),
		"reconciled_on": getattr(operation, "reconciled_on", None),
	}


def _log_quota_failure(doc, message: str, reason=None) -> None:
	frappe.log_error(
		title="RetailEdge Sales Transaction Quota",
		message=(
			f"{message}\n"
			f"Document: {getattr(doc, 'doctype', '')} {getattr(doc, 'name', '')}\n"
			f"Reason: {str(reason or '')[:300]}"
		),
	)


def _idempotency_key(doctype: str, name: str, action: str, attempt: str) -> str:
	raw = f"retail:sale:{doctype}:{name}:{action}:{attempt}"
	if len(raw) <= 140:
		return raw
	digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
	return f"retail:sale:{action}:{digest}"


def _retry_idempotency_key(base_key: str, attempt_count: int) -> str:
	raw = f"{base_key}:attempt:{max(1, int(attempt_count or 1))}"
	if len(raw) <= 140:
		return raw
	digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
	return f"retail:sale:finalize-retry:{digest}"


def _safe_error(exc: Exception) -> str:
	return str(exc or exc.__class__.__name__)[:500]


def _parse_bool(value: Any, default: bool) -> bool:
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, int):
		return value != 0
	text = str(value).strip().lower()
	if text in _TRUE_VALUES:
		return True
	if text in _FALSE_VALUES:
		return False
	return default


def _parse_reservation_seconds(value: Any) -> int:
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		return 3600
	if 60 <= parsed <= 3600:
		return parsed
	return 3600
