from __future__ import annotations

import hashlib
from functools import partial

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from retailedge.integrations.coreedge_remote import (
	CoreEdgeRemoteAuthenticationFailed,
	CoreEdgeRemoteError,
	CoreEdgeRemoteNotConfigured,
	CoreEdgeRemoteUnavailable,
)
from retailedge.integrations.quota import (
	finalize_usage,
	release_usage,
	reserve_usage,
)


_DOCTYPE = "RetailEdge CoreEdge Quota Operation"
_FINALIZE_RETRY_STATUSES = {"Reserved", "Finalize Pending"}
_RELEASE_RETRY_STATUSES = {"Release Pending"}
_RETRYABLE_STATUSES = _FINALIZE_RETRY_STATUSES | _RELEASE_RETRY_STATUSES
_TERMINAL_STATUSES = {
	"Finalized",
	"Released",
	"Expired",
	"Reconciliation Required",
	"Failed",
}
_RECONCILIATION_REASON_CODES = {
	"RESERVATION_EXPIRED",
	"RESERVATION_ALREADY_RELEASED",
	"RESERVATION_NOT_FOUND",
	"USAGE_RESERVATION_ACCESS_DENIED",
}
_DEFAULT_RESERVATION_SECONDS = 900
_RETRY_DELAY_MINUTES = 2
_MAX_SCHEDULER_BATCH = 200


def prepare_transaction_quota(
	doc,
	*,
	entitlement_key: str,
	units: int = 1,
	transaction_event: str = "Submit",
	expires_in_seconds: int = _DEFAULT_RESERVATION_SECONDS,
) -> dict:
	"""
	Reserve quota inside the local business transaction and register commit/rollback callbacks.

	This is intentionally not called by any RetailEdge DocType hook in this foundation slice.
	"""
	_assert_transaction_identity(doc)
	entitlement_key = _required_text(entitlement_key, "Entitlement Key", 140)
	transaction_event = _required_text(transaction_event, "Transaction Event", 80)
	units = _positive_int(units, "Units")
	operation_key = build_operation_key(
		entitlement_key=entitlement_key,
		transaction_doctype=doc.doctype,
		transaction_name=doc.name,
		transaction_event=transaction_event,
	)

	existing = frappe.db.get_value(
		_DOCTYPE,
		operation_key,
		[
			"name",
			"status",
			"reservation_reference",
			"release_idempotency_key",
		],
		as_dict=True,
	)
	if existing:
		if existing.status == "Finalized":
			return _serialize_operation(frappe.get_doc(_DOCTYPE, existing.name))
		if existing.status in _FINALIZE_RETRY_STATUSES:
			_register_transaction_callbacks(
				operation_key=existing.name,
				reservation_reference=existing.reservation_reference,
				release_idempotency_key=existing.release_idempotency_key,
				transaction_doctype=doc.doctype,
				transaction_name=doc.name,
			)
			return _serialize_operation(frappe.get_doc(_DOCTYPE, existing.name))
		frappe.throw(
			_(
				"CoreEdge quota history already exists for this transaction event "
				"in status {0}. Review the quota operation before retrying."
			).format(existing.status),
			frappe.ValidationError,
		)

	reserve_key = f"reserve:{operation_key}"
	finalize_key = f"finalize:{operation_key}"
	release_key = f"release:{operation_key}"

	response = reserve_usage(
		entitlement_key,
		units,
		idempotency_key=reserve_key,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		expires_in_seconds=expires_in_seconds,
		request_id=f"{operation_key}:reserve",
		correlation_id=operation_key,
	)
	data = _response_data(response)
	if not data.get("ok"):
		frappe.throw(
			data.get("message") or _("CoreEdge quota reservation was not approved."),
			frappe.ValidationError,
		)

	quota = data.get("quota") or {}
	reservation_reference = _required_text(
		quota.get("reservation_reference"),
		"Reservation Reference",
		140,
	)

	operation = frappe.get_doc(
		{
			"doctype": _DOCTYPE,
			"operation_key": operation_key,
			"status": "Reserved",
			"entitlement_key": entitlement_key,
			"units": units,
			"transaction_doctype": doc.doctype,
			"transaction_name": doc.name,
			"transaction_event": transaction_event,
			"company": getattr(doc, "company", None),
			"branch": getattr(doc, "branch", None),
			"reservation_reference": reservation_reference,
			"reservation_status": quota.get("status") or "Active",
			"reserved_on": quota.get("reserved_on") or now_datetime(),
			"expires_on": quota.get("expires_on"),
			"reserve_idempotency_key": reserve_key,
			"finalize_idempotency_key": finalize_key,
			"release_idempotency_key": release_key,
			"actor": frappe.session.user,
		}
	)
	operation.flags.allow_quota_operation_create = True
	try:
		operation.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# A concurrent attempt with the same operation identity shares the same
		# remote reservation idempotency. Never release that shared hold here.
		existing_doc = frappe.get_doc(_DOCTYPE, operation_key)
		_register_transaction_callbacks(
			operation_key=existing_doc.name,
			reservation_reference=existing_doc.reservation_reference,
			release_idempotency_key=existing_doc.release_idempotency_key,
			transaction_doctype=doc.doctype,
			transaction_name=doc.name,
		)
		return _serialize_operation(existing_doc)
	except Exception:
		_attempt_untracked_release(
			reservation_reference=reservation_reference,
			release_idempotency_key=release_key,
			reason=(
				"RetailEdge could not persist its quota-operation outbox after "
				"CoreEdge reservation."
			),
		)
		raise

	_register_transaction_callbacks(
		operation_key=operation.name,
		reservation_reference=reservation_reference,
		release_idempotency_key=release_key,
		transaction_doctype=doc.doctype,
		transaction_name=doc.name,
	)
	return _serialize_operation(operation)


def build_operation_key(
	*,
	entitlement_key: str,
	transaction_doctype: str,
	transaction_name: str,
	transaction_event: str,
) -> str:
	value = "\x1f".join(
		[
			str(entitlement_key or "").strip(),
			str(transaction_doctype or "").strip(),
			str(transaction_name or "").strip(),
			str(transaction_event or "").strip(),
		]
	)
	return f"re-qop-{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def enqueue_finalize_quota_operation(operation_key: str) -> None:
	try:
		frappe.enqueue(
			"retailedge.integrations.quota_operations.finalize_quota_operation",
			queue="short",
			enqueue_after_commit=False,
			operation_key=operation_key,
		)
	except Exception:
		frappe.log_error(
			title="RetailEdge CoreEdge Quota Finalize Enqueue Error",
			message=frappe.get_traceback(),
		)


def finalize_quota_operation(operation_key: str) -> dict:
	row = frappe.db.get_value(
		_DOCTYPE,
		operation_key,
		["name", "status"],
		as_dict=True,
		for_update=True,
	)
	if not row:
		return {
			"ok": False,
			"status": "Missing",
			"reason_code": "LOCAL_QUOTA_OPERATION_NOT_FOUND",
		}
	operation = frappe.get_doc(_DOCTYPE, row.name)

	if operation.status == "Finalized":
		return _serialize_operation(operation)
	if operation.status in _TERMINAL_STATUSES:
		return _serialize_operation(operation)

	transaction_state = _transaction_state(operation)
	if transaction_state != "Submitted":
		reason = (
			"Transaction is cancelled before quota finalization; cancellation "
			"policy requires operator reconciliation."
			if transaction_state == "Cancelled"
			else "Transaction is not submitted after the local quota reservation committed."
		)
		return _mark_reconciliation_required(
			operation,
			reason_code=f"LOCAL_TRANSACTION_{transaction_state.upper()}",
			reason=reason,
		)

	if operation.expires_on and get_datetime(operation.expires_on) <= now_datetime():
		return _mark_reconciliation_required(
			operation,
			reason_code="RESERVATION_EXPIRED_BEFORE_FINALIZE",
			reason=(
				"CoreEdge reservation expired before RetailEdge confirmed finalization. "
				"The submitted transaction must be reconciled; do not mutate it."
			),
		)

	_attempt_started(operation)
	try:
		response = finalize_usage(
			operation.reservation_reference,
			idempotency_key=operation.finalize_idempotency_key,
			request_id=f"{operation.operation_key}:finalize",
			correlation_id=operation.operation_key,
		)
	except (
		CoreEdgeRemoteUnavailable,
		CoreEdgeRemoteAuthenticationFailed,
		CoreEdgeRemoteNotConfigured,
		CoreEdgeRemoteError,
	) as exc:
		return _mark_finalize_pending(
			operation,
			reason_code=exc.__class__.__name__,
			message=str(exc) or "CoreEdge quota finalization is temporarily unavailable.",
		)
	except Exception as exc:
		return _mark_finalize_pending(
			operation,
			reason_code="UNEXPECTED_FINALIZE_ERROR",
			message=str(exc) or "Unexpected CoreEdge quota finalization error.",
		)

	data = _response_data(response)
	if data.get("ok"):
		operation.status = "Finalized"
		operation.reservation_status = (
			(data.get("quota") or {}).get("status") or "Finalized"
		)
		operation.finalized_on = (
			(data.get("quota") or {}).get("finalized_on") or now_datetime()
		)
		operation.next_retry_on = None
		operation.last_error_code = None
		operation.last_error_message = None
		_save_operation(operation)
		return _serialize_operation(operation)

	reason_code = str(data.get("reason_code") or "USAGE_FINALIZE_FAILED")
	message = str(data.get("message") or "CoreEdge quota finalization failed.")
	if reason_code in _RECONCILIATION_REASON_CODES:
		return _mark_reconciliation_required(
			operation,
			reason_code=reason_code,
			reason=message,
		)
	return _mark_finalize_pending(
		operation,
		reason_code=reason_code,
		message=message,
	)


def retry_pending_quota_operations(limit: int = 100) -> dict:
	try:
		resolved_limit = max(1, min(int(limit or 100), _MAX_SCHEDULER_BATCH))
	except (TypeError, ValueError):
		resolved_limit = 100

	rows = frappe.get_all(
		_DOCTYPE,
		filters={"status": ["in", sorted(_RETRYABLE_STATUSES)]},
		fields=["name", "next_retry_on"],
		order_by="modified asc",
		limit_page_length=resolved_limit * 2,
	)
	now = now_datetime()
	processed = 0
	finalized = 0
	reconciliation_required = 0
	pending = 0
	for row in rows:
		if processed >= resolved_limit:
			break
		if row.next_retry_on and get_datetime(row.next_retry_on) > now:
			continue
		processed += 1
		current_status = frappe.db.get_value(_DOCTYPE, row.name, "status")
		if current_status in _RELEASE_RETRY_STATUSES:
			operation = frappe.get_doc(_DOCTYPE, row.name)
			result = release_quota_operation(
				row.name,
				reason=(
					operation.notes
					or "Retrying previously requested CoreEdge quota release."
				),
			)
		else:
			result = finalize_quota_operation(row.name)
		status = result.get("status")
		if status == "Finalized":
			finalized += 1
		elif status == "Reconciliation Required":
			reconciliation_required += 1
		elif status in _RETRYABLE_STATUSES:
			pending += 1
	return {
		"processed": processed,
		"finalized": finalized,
		"reconciliation_required": reconciliation_required,
		"pending": pending,
	}


def release_quota_operation(operation_key: str, *, reason: str) -> dict:
	operation = frappe.get_doc(_DOCTYPE, operation_key)
	if operation.status == "Released":
		return _serialize_operation(operation)
	if operation.status == "Finalized":
		frappe.throw(
			_("Finalized quota operations cannot be released."),
			frappe.ValidationError,
		)
	if operation.status in _TERMINAL_STATUSES:
		return _serialize_operation(operation)

	reason = _required_text(reason, "Release Reason", 500)
	operation.status = "Release Pending"
	operation.notes = reason
	operation.last_attempt_on = now_datetime()
	operation.attempt_count = int(operation.attempt_count or 0) + 1
	_save_operation(operation)

	try:
		response = release_usage(
			operation.reservation_reference,
			idempotency_key=operation.release_idempotency_key,
			reason=reason,
			request_id=f"{operation.operation_key}:release",
			correlation_id=operation.operation_key,
		)
	except (
		CoreEdgeRemoteUnavailable,
		CoreEdgeRemoteAuthenticationFailed,
		CoreEdgeRemoteNotConfigured,
		CoreEdgeRemoteError,
	) as exc:
		operation.status = "Release Pending"
		operation.last_error_code = exc.__class__.__name__[:140]
		operation.last_error_message = str(exc)[:1000]
		operation.next_retry_on = add_to_date(
			now_datetime(),
			minutes=_RETRY_DELAY_MINUTES,
		)
		_save_operation(operation)
		return _serialize_operation(operation)
	except Exception as exc:
		operation.status = "Release Pending"
		operation.last_error_code = "UNEXPECTED_RELEASE_ERROR"
		operation.last_error_message = str(exc)[:1000]
		operation.next_retry_on = add_to_date(
			now_datetime(),
			minutes=_RETRY_DELAY_MINUTES,
		)
		_save_operation(operation)
		return _serialize_operation(operation)

	data = _response_data(response)
	if data.get("ok"):
		operation.status = "Released"
		operation.reservation_status = (
			(data.get("quota") or {}).get("status") or "Released"
		)
		operation.released_on = (
			(data.get("quota") or {}).get("released_on") or now_datetime()
		)
		operation.last_error_code = None
		operation.last_error_message = None
		operation.next_retry_on = None
		_save_operation(operation)
		return _serialize_operation(operation)

	reason_code = str(data.get("reason_code") or "USAGE_RELEASE_FAILED")
	message = str(data.get("message") or "CoreEdge quota release failed.")
	if reason_code == "RESERVATION_EXPIRED":
		operation.status = "Expired"
		operation.reservation_status = "Expired"
		operation.last_error_code = reason_code
		operation.last_error_message = message[:1000]
		operation.next_retry_on = None
		_save_operation(operation)
		return _serialize_operation(operation)
	if reason_code in {
		"RESERVATION_ALREADY_FINALIZED",
		"RESERVATION_NOT_FOUND",
	}:
		return _mark_reconciliation_required(
			operation,
			reason_code=reason_code,
			reason=message,
		)

	operation.status = "Release Pending"
	operation.last_error_code = reason_code[:140]
	operation.last_error_message = message[:1000]
	operation.next_retry_on = add_to_date(
		now_datetime(),
		minutes=_RETRY_DELAY_MINUTES,
	)
	_save_operation(operation)
	return _serialize_operation(operation)



def _register_transaction_callbacks(
	*,
	operation_key: str,
	reservation_reference: str,
	release_idempotency_key: str,
	transaction_doctype: str,
	transaction_name: str,
) -> None:
	callback_key = f"{operation_key}:{id(frappe.db)}"
	registered = getattr(frappe.local, "_retailedge_quota_callbacks", set())
	if callback_key in registered:
		return
	registered.add(callback_key)
	frappe.local._retailedge_quota_callbacks = registered

	frappe.db.after_commit.add(
		partial(enqueue_finalize_quota_operation, operation_key)
	)
	frappe.db.after_rollback.add(
		partial(
			_release_after_rollback,
			reservation_reference=reservation_reference,
			release_idempotency_key=release_idempotency_key,
			transaction_doctype=transaction_doctype,
			transaction_name=transaction_name,
		)
	)


def _release_after_rollback(
	*,
	reservation_reference: str,
	release_idempotency_key: str,
	transaction_doctype: str,
	transaction_name: str,
) -> None:
	try:
		release_usage(
			reservation_reference,
			idempotency_key=release_idempotency_key,
			reason=(
				f"{transaction_doctype} {transaction_name} rolled back before commit."
			),
			request_id=f"{release_idempotency_key}:rollback",
			correlation_id=release_idempotency_key,
		)
	except Exception:
		frappe.log_error(
			title="RetailEdge CoreEdge Quota Rollback Release Error",
			message=frappe.get_traceback(),
		)


def _attempt_untracked_release(
	*,
	reservation_reference: str,
	release_idempotency_key: str,
	reason: str,
) -> None:
	try:
		release_usage(
			reservation_reference,
			idempotency_key=release_idempotency_key,
			reason=reason,
			request_id=f"{release_idempotency_key}:untracked",
			correlation_id=release_idempotency_key,
		)
	except Exception:
		frappe.log_error(
			title="RetailEdge Untracked CoreEdge Quota Reservation",
			message=(
				f"Reservation {reservation_reference} could not be released after "
				"local outbox persistence failed. CoreEdge TTL must recover capacity.\n"
				f"{frappe.get_traceback()}"
			),
		)


def _attempt_started(operation) -> None:
	operation.attempt_count = int(operation.attempt_count or 0) + 1
	operation.last_attempt_on = now_datetime()
	operation.status = "Finalize Pending"
	_save_operation(operation)


def _mark_finalize_pending(operation, *, reason_code: str, message: str) -> dict:
	operation.status = "Finalize Pending"
	operation.last_error_code = str(reason_code or "USAGE_FINALIZE_FAILED")[:140]
	operation.last_error_message = str(message or "")[:1000]
	operation.next_retry_on = add_to_date(
		now_datetime(),
		minutes=_RETRY_DELAY_MINUTES,
	)
	_save_operation(operation)
	return _serialize_operation(operation)


def _mark_reconciliation_required(
	operation,
	*,
	reason_code: str,
	reason: str,
) -> dict:
	operation.status = "Reconciliation Required"
	operation.last_error_code = str(reason_code or "RECONCILIATION_REQUIRED")[:140]
	operation.last_error_message = str(reason or "")[:1000]
	operation.reconciliation_reason = str(reason or "")[:1000]
	operation.next_retry_on = None
	_save_operation(operation)
	return _serialize_operation(operation)


def _transaction_state(operation) -> str:
	if not frappe.db.exists(
		operation.transaction_doctype,
		operation.transaction_name,
	):
		return "Missing"
	docstatus = int(
		frappe.db.get_value(
			operation.transaction_doctype,
			operation.transaction_name,
			"docstatus",
		)
		or 0
	)
	if docstatus == 1:
		return "Submitted"
	if docstatus == 2:
		return "Cancelled"
	return "Draft"


def _save_operation(operation) -> None:
	operation.flags.allow_quota_operation_update = True
	operation.save(ignore_permissions=True)


def _response_data(response: dict) -> dict:
	if not isinstance(response, dict):
		return {
			"ok": False,
			"reason_code": "INVALID_REMOTE_RESPONSE",
			"message": "CoreEdge quota response is invalid.",
		}
	data = response.get("data")
	return data if isinstance(data, dict) else {}


def _serialize_operation(operation) -> dict:
	return {
		"operation_key": operation.operation_key,
		"status": operation.status,
		"entitlement_key": operation.entitlement_key,
		"units": int(operation.units or 0),
		"transaction_doctype": operation.transaction_doctype,
		"transaction_name": operation.transaction_name,
		"transaction_event": operation.transaction_event,
		"reservation_reference": operation.reservation_reference,
		"reservation_status": operation.reservation_status,
		"reserved_on": operation.reserved_on,
		"expires_on": operation.expires_on,
		"finalized_on": operation.finalized_on,
		"released_on": operation.released_on,
		"attempt_count": int(operation.attempt_count or 0),
		"last_attempt_on": operation.last_attempt_on,
		"next_retry_on": operation.next_retry_on,
		"last_error_code": operation.last_error_code,
		"last_error_message": operation.last_error_message,
		"reconciliation_reason": operation.reconciliation_reason,
	}


def _assert_transaction_identity(doc) -> None:
	if not getattr(doc, "doctype", None) or not getattr(doc, "name", None):
		frappe.throw(
			_("A saved local transaction identity is required before reserving quota."),
			frappe.ValidationError,
		)


def _required_text(value, label: str, max_length: int) -> str:
	resolved = str(value or "").strip()
	if not resolved:
		frappe.throw(_("{0} is required.").format(label), frappe.ValidationError)
	if len(resolved) > max_length:
		frappe.throw(
			_("{0} cannot exceed {1} characters.").format(label, max_length),
			frappe.ValidationError,
		)
	return resolved


def _positive_int(value, label: str) -> int:
	try:
		resolved = int(value)
	except (TypeError, ValueError):
		frappe.throw(_("{0} must be a whole number.").format(label), frappe.ValidationError)
	if resolved <= 0:
		frappe.throw(_("{0} must be greater than zero.").format(label), frappe.ValidationError)
	return resolved
