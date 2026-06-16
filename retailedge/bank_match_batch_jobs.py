from __future__ import annotations

import json
import hashlib
import traceback

import frappe
from frappe.utils import cint, cstr, flt, now_datetime

from retailedge.bank_transaction_match_workflow import (
	assert_can_manage_bank_transaction_match,
	bulk_confirm_bank_transaction_matches,
	create_bank_match_reviews_from_suggestions,
	run_bank_transaction_auto_match,
)

MAX_SYNC_ROWS = 200
DEFAULT_CHUNK_SIZE = 100
ALLOWED_ACTIONS = {"Create Review Records", "Run Auto-Match", "Bulk Confirm Selected"}
ACTIVE_JOB_STATUSES = {"Queued", "Running"}
TERMINAL_JOB_STATUSES = {"Completed", "Completed With Errors", "Failed", "Cancelled"}
RETRYABLE_ROW_STATUSES = {"Failed"}


def _load_batch_job_for_action(batch_job_name, permission_type="read"):
	job = frappe.get_doc("RetailEdge Bank Match Batch Job", batch_job_name)
	if not job.has_permission(permission_type):
		frappe.throw(
			"You do not have permission to access this Bank Match Batch Job.",
			frappe.PermissionError,
		)
	return job


def _assert_can_create_batch_job():
	assert_can_manage_bank_transaction_match()


def coerce_json(value, default=None):
	if default is None:
		default = []
	if value in (None, ""):
		return default
	if isinstance(value, str):
		try:
			return json.loads(value)
		except Exception:
			return default
	return value


def row_count_for_payload(rows=None, match_names=None):
	if match_names is not None:
		return len(coerce_json(match_names, []))
	return len(coerce_json(rows, []))


def should_run_background(rows=None, match_names=None, max_sync_rows=MAX_SYNC_ROWS):
	return row_count_for_payload(rows=rows, match_names=match_names) > cint(max_sync_rows or MAX_SYNC_ROWS)


def background_required_response(action_type, total_rows, max_sync_rows=MAX_SYNC_ROWS):
	return {
		"status": "requires_background",
		"requires_background": True,
		"action_type": action_type,
		"total_rows": total_rows,
		"max_sync_rows": cint(max_sync_rows or MAX_SYNC_ROWS),
		"message": f"This selection has {total_rows} rows and may take time. Run as a background job?",
	}


def _safe_json_dumps(value):
	return json.dumps(value, default=str, sort_keys=True)


def _sanitize_error(message):
	return cstr(message).replace("\n", " ")[:1000]


def _payload_identity(action_type, payload):
	if action_type == "Bulk Confirm Selected":
		return cstr(payload.get("name") if isinstance(payload, dict) else payload).strip()
	payload = payload if isinstance(payload, dict) else {}
	return "|".join(
		(
			cstr(payload.get("candidate_key")).strip(),
			cstr(payload.get("bank_transaction")).strip(),
			cstr(payload.get("suggested_document_type")).strip(),
			cstr(payload.get("suggested_document")).strip(),
			cstr(payload.get("candidate_category")).strip(),
			cstr(payload.get("payment_event_source")).strip(),
			cstr(payload.get("payment_row_reference") or payload.get("payment_row_index")).strip(),
		)
	)


def build_selection_fingerprint(action_type, filters_payload=None, payload_rows=None, selected_keys_payload=None):
	row_identities = []
	for payload in payload_rows or []:
		row_payload = payload if isinstance(payload, dict) else {"name": payload}
		identity = _payload_identity(action_type, row_payload)
		if identity:
			row_identities.append(identity)
	scope = {
		"action_type": action_type,
		"filters": filters_payload or {},
		"rows": sorted(row_identities),
		"selected_keys": sorted(cstr(key).strip() for key in (selected_keys_payload or []) if cstr(key).strip()),
	}
	return hashlib.sha256(_safe_json_dumps(scope).encode()).hexdigest()


def get_active_duplicate_job(action_type, selection_fingerprint):
	if not selection_fingerprint:
		return None
	return frappe.db.get_value(
		"RetailEdge Bank Match Batch Job",
		{
			"action_type": action_type,
			"selection_fingerprint": selection_fingerprint,
			"status": ["in", list(ACTIVE_JOB_STATUSES)],
		},
		"name",
	)


@frappe.whitelist()
def create_bank_match_batch_job(
	action_type,
	filters=None,
	rows=None,
	selected_keys=None,
	match_names=None,
	dry_run=0,
	chunk_size=None,
	enqueue=1,
	retry_of=None,
	retry_reason=None,
):
	_assert_can_create_batch_job()
	if action_type not in ALLOWED_ACTIONS:
		frappe.throw(f"Unsupported bank match batch action: {action_type}")

	payload_rows = coerce_json(match_names, []) if action_type == "Bulk Confirm Selected" else coerce_json(rows, [])
	filters_payload = coerce_json(filters, {})
	selected_keys_payload = coerce_json(selected_keys, [])
	chunk_size = cint(chunk_size or DEFAULT_CHUNK_SIZE) or DEFAULT_CHUNK_SIZE
	selection_fingerprint = build_selection_fingerprint(
		action_type,
		filters_payload=filters_payload,
		payload_rows=payload_rows,
		selected_keys_payload=selected_keys_payload,
	)
	active_duplicate = get_active_duplicate_job(action_type, selection_fingerprint)
	if active_duplicate:
		return {
			"status": "duplicate_active_job",
			"batch_job": active_duplicate,
			"total_rows": len(payload_rows),
			"message": f"An active Bank Match Batch Job already exists for this selection: {active_duplicate}.",
		}

	job = frappe.new_doc("RetailEdge Bank Match Batch Job")
	job.action_type = action_type
	job.source_report = "Bank Transaction Matching" if action_type != "Bulk Confirm Selected" else "Bank Match Review"
	job.filters_json = json.dumps(filters_payload, default=str)
	job.selected_keys_json = json.dumps(selected_keys_payload, default=str)
	job.selected_rows_json = json.dumps(payload_rows, default=str)
	job.selection_fingerprint = selection_fingerprint
	job.total_rows = len(payload_rows)
	job.pending_rows = len(payload_rows)
	job.processed_rows = 0
	job.progress_percent = 0
	job.status = "Queued"
	job.started_by = frappe.session.user
	job.dry_run = cint(dry_run)
	job.chunk_size = chunk_size
	job.company = filters_payload.get("company")
	job.branch = filters_payload.get("branch")
	job.bank_account = filters_payload.get("bank_account")
	if retry_of:
		job.retry_of = retry_of
		job.retry_reason = retry_reason
		job.retry_source_row_count = len(payload_rows)

	for idx, payload in enumerate(payload_rows, start=1):
		row_payload = payload if isinstance(payload, dict) else {"name": payload}
		job.append("rows", _build_job_row(idx, row_payload, action_type))

	# Queue storage should survive stale selected rows; row-level processing revalidates safely.
	job.insert(ignore_permissions=True, ignore_links=True)
	frappe.db.commit()

	if cint(enqueue):
		frappe.enqueue(
			"retailedge.bank_match_batch_jobs.process_bank_match_batch_job",
			queue="long",
			job_name=f"RetailEdge Bank Match Batch Job {job.name}",
			batch_job_name=job.name,
		)

	return {
		"status": "queued",
		"batch_job": job.name,
		"total_rows": job.total_rows,
		"message": f"Bank Match Batch Job {job.name} has been queued. You can continue working while it runs.",
	}


@frappe.whitelist()
def refresh_bank_match_batch_job_progress(batch_job_name):
	job = _load_batch_job_for_action(batch_job_name, "read")
	_recount_job(job)
	job.summary_json = json.dumps(_job_summary(job), default=str)
	_save_job(job)
	frappe.db.commit()
	return _job_summary(job)


@frappe.whitelist()
def retry_bank_match_batch_job_rows(batch_job_name, retry_statuses=None, retry_reason=None, enqueue=1):
	job = _load_batch_job_for_action(batch_job_name, "write")
	statuses = set(coerce_json(retry_statuses, list(RETRYABLE_ROW_STATUSES)) or [])
	statuses = statuses.intersection(RETRYABLE_ROW_STATUSES)
	if not statuses:
		frappe.throw("Only failed rows are retryable in this phase.")
	if job.status not in TERMINAL_JOB_STATUSES:
		frappe.throw(f"Only completed, failed, or cancelled batch jobs can be retried. Current status: {job.status}.")
	rows = []
	for row in job.rows:
		if row.result_status in statuses:
			rows.append(coerce_json(row.input_payload_json, {}))
	if not rows:
		frappe.throw("No retryable failed rows were found for this batch job.")
	return create_bank_match_batch_job(
		action_type=job.action_type,
		filters=job.filters_json,
		rows=json.dumps(rows) if job.action_type != "Bulk Confirm Selected" else None,
		match_names=json.dumps(rows) if job.action_type == "Bulk Confirm Selected" else None,
		selected_keys=job.selected_keys_json,
		dry_run=job.dry_run,
		chunk_size=job.chunk_size,
		enqueue=enqueue,
		retry_of=job.name,
		retry_reason=retry_reason or "Retry failed rows",
	)


@frappe.whitelist()
def cancel_bank_match_batch_job(batch_job_name, reason=None):
	job = _load_batch_job_for_action(batch_job_name, "write")
	if job.status not in ACTIVE_JOB_STATUSES:
		frappe.throw(f"Only queued or running batch jobs can be cancelled. Current status: {job.status}.")
	job.cancel_requested = 1
	job.status = "Cancelled"
	job.cancelled_by = frappe.session.user
	job.cancelled_on = now_datetime()
	job.cancel_reason = reason
	job.completed_on = job.completed_on or now_datetime()
	_mark_pending_rows_cancelled(job)
	_recount_job(job)
	job.summary_json = json.dumps(_job_summary(job), default=str)
	_save_job(job)
	frappe.db.commit()
	return _job_summary(job)


def get_recent_bank_match_batch_jobs(action_type=None, limit=20):
	filters = {}
	if action_type:
		filters["action_type"] = action_type
	return frappe.get_all(
		"RetailEdge Bank Match Batch Job",
		filters=filters,
		fields=["name", "status", "action_type", "progress_percent", "total_rows", "processed_rows", "failed_count", "started_by", "started_on", "completed_on"],
		order_by="modified desc",
		limit_page_length=cint(limit or 20),
	)


def _build_job_row(idx, payload, action_type):
	row = {
		"row_index": idx,
		"candidate_key": payload.get("candidate_key") or payload.get("name") or payload.get("bank_transaction"),
		"bank_transaction": payload.get("bank_transaction"),
		"suggested_document_type": payload.get("suggested_document_type"),
		"suggested_document": payload.get("suggested_document"),
		"candidate_category": payload.get("candidate_category"),
		"payment_event_source": payload.get("payment_event_source"),
		"payment_row_reference": payload.get("payment_row_reference"),
		"payment_row_index": payload.get("payment_row_index"),
		"payment_account": payload.get("payment_account"),
		"resolved_payment_account": payload.get("resolved_payment_account"),
		"amount_scenario": payload.get("amount_scenario"),
		"match_score": payload.get("match_score"),
		"match_confidence": payload.get("match_confidence"),
		"input_payload_json": json.dumps(payload, default=str),
		"result_status": "Pending",
	}
	if action_type == "Bulk Confirm Selected":
		row["review_record"] = payload.get("name")
		row["candidate_key"] = payload.get("name")
	return row


def process_bank_match_batch_job(batch_job_name):
	job = frappe.get_doc("RetailEdge Bank Match Batch Job", batch_job_name)
	if job.status == "Cancelled" or cint(getattr(job, "cancel_requested", 0)):
		_mark_pending_rows_cancelled(job)
		job.status = "Cancelled"
		job.completed_on = job.completed_on or now_datetime()
		_recount_job(job)
		job.summary_json = json.dumps(_job_summary(job), default=str)
		_save_job(job)
		frappe.db.commit()
		return _job_summary(job)
	job.status = "Running"
	job.started_on = job.started_on or now_datetime()
	_recount_job(job)
	_save_job(job)
	frappe.db.commit()

	try:
		chunk_size = cint(job.chunk_size or DEFAULT_CHUNK_SIZE) or DEFAULT_CHUNK_SIZE
		pending = [row for row in job.rows if row.result_status == "Pending"]
		for start in range(0, len(pending), chunk_size):
			if _is_cancel_requested(job.name):
				job = frappe.get_doc("RetailEdge Bank Match Batch Job", job.name)
				_mark_pending_rows_cancelled(job)
				job.status = "Cancelled"
				job.completed_on = now_datetime()
				_recount_job(job)
				job.summary_json = json.dumps(_job_summary(job), default=str)
				_save_job(job)
				frappe.db.commit()
				return _job_summary(job)
			for row in pending[start : start + chunk_size]:
				if _is_cancel_requested(job.name):
					break
				_process_job_row(job, row)
			_recount_job(job)
			_save_job(job)
			frappe.db.commit()
		_recount_job(job)
		job.completed_on = now_datetime()
		job.status = _final_job_status(job)
		job.summary_json = json.dumps(_job_summary(job), default=str)
		_save_job(job)
		frappe.db.commit()
		return _job_summary(job)
	except Exception as exc:
		job.status = "Failed"
		job.last_error = _sanitize_error(exc)
		job.completed_on = now_datetime()
		_recount_job(job)
		_save_job(job)
		frappe.db.commit()
		raise


def _save_job(job):
	job.flags.ignore_links = True
	job.save(ignore_permissions=True)


def _is_cancel_requested(job_name):
	status, cancel_requested = frappe.db.get_value(
		"RetailEdge Bank Match Batch Job",
		job_name,
		["status", "cancel_requested"],
	) or (None, 0)
	return status == "Cancelled" or cint(cancel_requested)


def _mark_pending_rows_cancelled(job):
	for row in job.rows:
		if row.result_status == "Pending":
			row.result_status = "Skipped"
			row.result_message = "Job cancelled before processing."
			row.processed_on = now_datetime()


def _final_job_status(job):
	if job.status == "Cancelled" or cint(getattr(job, "cancel_requested", 0)):
		return "Cancelled"
	if cint(job.failed_count or 0):
		return "Completed With Errors"
	return "Completed"


def _process_job_row(job, row):
	payload = coerce_json(row.input_payload_json, {})
	try:
		if job.action_type == "Create Review Records":
			result = create_bank_match_reviews_from_suggestions(filters=job.filters_json, rows=json.dumps([payload]))
			_apply_create_result(row, result)
		elif job.action_type == "Run Auto-Match":
			result = run_bank_transaction_auto_match(filters=job.filters_json, rows=json.dumps([payload]))
			_apply_auto_match_result(row, result)
		elif job.action_type == "Bulk Confirm Selected":
			name = payload.get("name") or row.review_record
			result = bulk_confirm_bank_transaction_matches(match_names=json.dumps([name]))
			_apply_bulk_confirm_result(row, result)
		else:
			row.result_status = "Failed"
			row.result_message = f"Unsupported action {job.action_type}"
	except Exception as exc:
		row.result_status = "Failed"
		row.result_message = cstr(exc)[:1000]
		row.error_traceback = traceback.format_exc()
	row.processed_on = now_datetime()


def _apply_create_result(row, result):
	if result.get("created_count"):
		created = (result.get("created") or [{}])[0]
		row.result_status = "Created"
		row.review_record = created.get("match_record")
		row.result_message = created.get("reason") or result.get("message")
	elif result.get("duplicate_count"):
		dup = (result.get("duplicates") or [{}])[0]
		row.result_status = "Already Exists"
		row.review_record = dup.get("match_record")
		row.result_message = dup.get("reason")
	elif result.get("already_matched_count"):
		row.result_status = "Blocked"
		row.result_message = _first_reason(result, "already_matched")
	elif result.get("unsafe_count") or result.get("duplicate_candidate_skipped_count"):
		reason = _first_reason(result, "unsafe") or _first_reason(result, "duplicate_candidates")
		if _is_locked_candidate_validation_failure(reason):
			row.result_status = "Failed"
		else:
			row.result_status = "Skipped"
		row.result_message = reason
	elif result.get("error_count"):
		row.result_status = "Failed"
		row.result_message = _first_reason(result, "errors")
	else:
		row.result_status = "Skipped"
		row.result_message = result.get("message")


def _apply_auto_match_result(row, result):
	if result.get("auto_confirmed_count"):
		row.result_status = "Confirmed"
		row.review_record = (result.get("auto_confirmed") or [{}])[0].get("match_record")
		row.result_message = _first_reason(result, "auto_confirmed")
	elif result.get("auto_prepared_count"):
		row.result_status = "Created"
		row.review_record = (result.get("auto_prepared") or [{}])[0].get("match_record")
		row.result_message = _first_reason(result, "auto_prepared")
	elif result.get("review_record_exists_count"):
		row.result_status = "Already Exists"
		row.review_record = (result.get("review_record_exists") or [{}])[0].get("match_record")
		row.result_message = _first_reason(result, "review_record_exists")
	elif result.get("already_confirmed_count") or result.get("manual_review_count") or result.get("duplicate_candidate_skipped_count"):
		row.result_status = "Blocked"
		row.result_message = _first_reason(result, "already_confirmed") or _first_reason(result, "manual_review") or _first_reason(result, "duplicate_candidates")
	elif result.get("error_count"):
		row.result_status = "Failed"
		row.result_message = _first_reason(result, "errors")
	else:
		row.result_status = "Skipped"
		row.result_message = result.get("message")


def _apply_bulk_confirm_result(row, result):
	if result.get("confirmed_count"):
		row.result_status = "Confirmed"
		row.result_message = (result.get("confirmed") or [{}])[0].get("message")
	else:
		row.result_status = "Blocked"
		row.result_message = (result.get("blocked") or [{}])[0].get("reason") or "Not eligible for bulk confirmation."


def _is_locked_candidate_validation_failure(reason):
	reason = cstr(reason).strip()
	return reason.startswith("Locked candidate") or "Locked Payment Entry candidate" in reason or "Locked Sales Invoice" in reason


def _first_reason(result, bucket):
	rows = result.get(bucket) or []
	if not rows:
		return None
	return rows[0].get("reason") or rows[0].get("message") or result.get("message")


def _recount_job(job):
	job.total_rows = len(job.rows)
	job.pending_rows = sum(1 for row in job.rows if row.result_status == "Pending")
	job.processed_rows = sum(1 for row in job.rows if row.result_status != "Pending")
	job.created_count = sum(1 for row in job.rows if row.result_status == "Created")
	job.confirmed_count = sum(1 for row in job.rows if row.result_status == "Confirmed")
	job.skipped_count = sum(1 for row in job.rows if row.result_status == "Skipped")
	job.blocked_count = sum(1 for row in job.rows if row.result_status == "Blocked")
	job.failed_count = sum(1 for row in job.rows if row.result_status == "Failed")
	job.already_exists_count = sum(1 for row in job.rows if row.result_status == "Already Exists")
	job.progress_percent = round((flt(job.processed_rows) / flt(job.total_rows)) * 100, 2) if cint(job.total_rows or 0) else 100


def _job_summary(job):
	status = job.status or "Queued"
	progress_percent = getattr(job, "progress_percent", 0)
	processed_rows = getattr(job, "processed_rows", 0)
	total_rows = getattr(job, "total_rows", 0)
	row_status_counts = {}
	for row in getattr(job, "rows", []) or []:
		row_status = row.result_status or "Pending"
		row_status_counts[row_status] = row_status_counts.get(row_status, 0) + 1
	can_read = bool(job.has_permission("read")) if getattr(job, "name", None) else False
	can_write = bool(job.has_permission("write")) if getattr(job, "name", None) else False
	can_cancel = can_write and status in ACTIVE_JOB_STATUSES
	can_retry_failed = can_write and status in TERMINAL_JOB_STATUSES and cint(getattr(job, "failed_count", 0)) > 0
	message = f"{status}: {processed_rows} of {total_rows} rows processed."
	if can_retry_failed:
		message += " Failed rows can be retried as a new batch job."
	elif cint(getattr(job, "failed_count", 0)) > 0:
		message += " Failed rows exist, but you do not have permission to retry them."
	if can_cancel:
		message += " This job can be cancelled."
	return {
		"batch_job": job.name,
		"status": status,
		"status_label": status,
		"action_type": job.action_type,
		"message": message,
		"total_rows": total_rows,
		"pending_rows": getattr(job, "pending_rows", 0),
		"processed_rows": processed_rows,
		"progress_percent": progress_percent,
		"progress_label": f"{status}: {progress_percent}% complete ({processed_rows} of {total_rows} rows processed)",
		"created_count": job.created_count,
		"confirmed_count": job.confirmed_count,
		"skipped_count": job.skipped_count,
		"blocked_count": job.blocked_count,
		"failed_count": job.failed_count,
		"already_exists_count": getattr(job, "already_exists_count", 0),
		"row_status_counts": row_status_counts,
		"is_active": status in ACTIVE_JOB_STATUSES,
		"is_terminal": status in TERMINAL_JOB_STATUSES,
		"can_read": can_read,
		"can_write": can_write,
		"can_cancel": can_cancel,
		"can_retry": can_retry_failed,
		"can_retry_failed": can_retry_failed,
		"can_retry_blocked": False,
		"started_on": getattr(job, "started_on", None),
		"completed_on": getattr(job, "completed_on", None),
		"last_error": getattr(job, "last_error", None),
	}
