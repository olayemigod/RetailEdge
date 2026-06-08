from __future__ import annotations

import json

import frappe
from frappe.utils import cint, cstr, flt, fmt_money, now_datetime

from retailedge.bank_transaction_matching import (
	_build_matching_row,
	_derive_action_status,
	_select_candidate_for_queue,
	_date_difference_days,
	_resolve_account_match_payload,
	amount_scenario_requires_manual_review,
	assert_can_access_bank_transaction_matching,
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	get_candidate_category_label,
	normalize_candidate_category_key,
	get_auto_match_status_for_row,
	get_amount_scenario_label,
	_normalize_auto_match_score,
	get_bank_transaction_matching_settings,
	get_bank_transaction_matching_rows,
	get_review_creation_block_reason,
	is_payment_basis_review_candidate,
	normalize_bank_transaction,
	payment_entry_has_active_confirmed_bank_match,
	sales_invoice_has_active_confirmed_bank_match,
	split_duplicate_candidate_suggestions,
)
from retailedge.cashier_expense import user_has_any_role
from retailedge.utils.settings import get_retailedge_settings


BANK_TRANSACTION_MATCH_WORKFLOW_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}

NO_MATCH_CANDIDATE_MESSAGE = "No match candidate found."


def assert_can_manage_bank_transaction_match(user: str | None = None):
	if user_has_any_role(user=user, roles=BANK_TRANSACTION_MATCH_WORKFLOW_ROLES):
		return
	frappe.throw(
		"You do not have permission to manage RetailEdge bank transaction match decisions.",
		frappe.PermissionError,
	)


def create_or_get_bank_transaction_match(
	bank_transaction_name,
	suggested_document_type=None,
	suggested_document=None,
	sales_invoice=None,
	payment_entry=None,
	source_report="Bank Transaction Matching",
	force_refresh=False,
	row_payload=None,
):
	assert_can_manage_bank_transaction_match()
	assert_can_access_bank_transaction_matching()
	selected_row = _normalize_report_row_candidate_payload(row_payload)
	if selected_row.get("bank_transaction"):
		bank_transaction_name = selected_row.get("bank_transaction")
	normalized = normalize_bank_transaction(bank_transaction_name)
	if selected_row and cint(selected_row.get("candidate_locked")):
		selected_row = _lock_report_row_candidate(selected_row)
		if cint(selected_row.get("candidate_identity_valid")) == 0:
			frappe.throw(
				cstr(selected_row.get("candidate_changed_reason")).strip()
				or "Current best candidate differs from the selected report row. Refresh the report and review again."
			)
		candidate = _build_candidate_from_report_row(selected_row)
	else:
		candidate = _resolve_matching_candidate(
			bank_transaction_name=bank_transaction_name,
			suggested_document_type=suggested_document_type,
			suggested_document=suggested_document,
			sales_invoice=sales_invoice,
			payment_entry=payment_entry,
		)
	_ensure_valid_candidate(candidate)

	existing_name = _find_existing_match_name(
		bank_transaction=bank_transaction_name,
		suggested_document_type=candidate.get("document_type") if candidate else suggested_document_type,
		suggested_document=(candidate or {}).get("document_name") or suggested_document or sales_invoice or payment_entry,
		payment_event_source=(candidate or {}).get("payment_event_source") or selected_row.get("payment_event_source"),
		payment_row_index=(candidate or {}).get("payment_row_index") or selected_row.get("payment_row_index") or selected_row.get("payment_row_reference"),
	)
	if existing_name:
		doc = frappe.get_doc("RetailEdge Bank Transaction Match", existing_name)
		if selected_row and cint(selected_row.get("candidate_locked")) and not _stored_candidate_matches_row(doc, selected_row):
			frappe.throw("Current best candidate differs from the selected report row. Refresh the report and review again.")
		created = False
	else:
		doc = frappe.get_doc({"doctype": "RetailEdge Bank Transaction Match"})
		created = True

	_populate_match_document(
		doc=doc,
		bank_transaction=normalized,
		candidate=candidate,
		source_report=source_report,
	)

	if created:
		doc.insert(ignore_permissions=True)
		append_bank_transaction_match_action_log(
			doc,
			action="Created",
			old_status=None,
			new_status=doc.decision_status,
			remarks="Created from Bank Transaction Matching report.",
			details={"bank_transaction": bank_transaction_name},
		)
		_save_match_preserving_selected_candidate(doc)
	elif force_refresh:
		_save_match_preserving_selected_candidate(doc)

	return {
		"name": doc.name,
		"created": created,
		"decision_status": doc.decision_status,
		"bank_transaction": doc.bank_transaction,
		"suggested_document": doc.suggested_document,
		"suggested_document_type": doc.suggested_document_type,
		"candidate_key": _build_report_row_candidate_key(selected_row or candidate),
	}


def confirm_bank_transaction_match(match_name, decision_note=None):
	return _apply_bank_transaction_match_decision(
		match_name=match_name,
		action="Confirmed",
		new_status="Confirmed",
		decision_note=decision_note,
		allowed_current_statuses={"Draft", "Suggested", "Needs Review", "Reopened"},
		success_message="Candidate confirmed. RetailEdge stored the decision only. No reconciliation or accounting posting was performed.",
	)


def reject_bank_transaction_match(match_name, decision_note=None):
	return _apply_bank_transaction_match_decision(
		match_name=match_name,
		action="Rejected",
		new_status="Rejected",
		decision_note=decision_note,
		allowed_current_statuses={"Draft", "Suggested", "Needs Review", "Reopened", "Confirmed"},
		success_message="Candidate rejected. RetailEdge stored the decision only. No reconciliation or accounting posting was performed.",
	)


def mark_bank_transaction_match_needs_review(match_name, decision_note=None):
	return _apply_bank_transaction_match_decision(
		match_name=match_name,
		action="Needs Review",
		new_status="Needs Review",
		decision_note=decision_note,
		allowed_current_statuses={"Draft", "Suggested", "Reopened", "Confirmed"},
		success_message="Candidate marked Needs Review. RetailEdge stored the decision only.",
	)


def reopen_bank_transaction_match(match_name, decision_note=None):
	return _apply_bank_transaction_match_decision(
		match_name=match_name,
		action="Reopened",
		new_status="Reopened",
		decision_note=decision_note,
		allowed_current_statuses={"Rejected", "Cancelled", "Confirmed", "Needs Review"},
		success_message="Candidate reopened. RetailEdge stored the decision only.",
	)


def cancel_bank_transaction_match(match_name, decision_note=None):
	return _apply_bank_transaction_match_decision(
		match_name=match_name,
		action="Cancelled",
		new_status="Cancelled",
		decision_note=decision_note,
		allowed_current_statuses={"Draft", "Suggested", "Needs Review", "Reopened", "Confirmed"},
		success_message="Candidate cancelled. RetailEdge stored the decision only.",
	)


def preview_bulk_confirm_bank_transaction_matches(match_names):
	assert_can_manage_bank_transaction_match()
	names = _coerce_match_names(match_names)
	result = {
		"total_selected": len(names),
		"eligible_count": 0,
		"blocked_count": 0,
		"warning_count": 0,
		"skipped_count": 0,
		"unsafe_count": 0,
		"already_confirmed_count": 0,
		"duplicate_blocked_count": 0,
		"weak_needs_review_count": 0,
		"eligible": [],
		"blocked": [],
		"warnings": [],
		"reasons": [],
	}
	for name in names:
		doc = frappe.get_doc("RetailEdge Bank Transaction Match", name)
		eligibility = _get_bulk_confirm_eligibility(doc)
		row = {
			"name": doc.name,
			"bank_transaction": doc.bank_transaction,
			"suggested_document_type": doc.suggested_document_type,
			"suggested_document": doc.suggested_document,
			"match_confidence": doc.match_confidence,
			"match_score": cint(doc.match_score or 0),
			"reason": eligibility["reason"],
			"category": eligibility.get("category") or "blocked",
		}
		if eligibility["eligible"]:
			result["eligible"].append(row)
		else:
			result["blocked"].append(row)
			_increment_bulk_preview_category(result, row["category"])
		for warning in eligibility.get("warnings") or []:
			result["warnings"].append({"name": doc.name, "warning": warning})

	result["eligible_count"] = len(result["eligible"])
	result["blocked_count"] = len(result["blocked"])
	result["warning_count"] = len(result["warnings"])
	result["reasons"] = _summarize_rows_by_reason(result["blocked"])
	return result


def _summarize_rows_by_reason(rows):
	counts = {}
	for row in rows or []:
		reason = cstr(row.get("reason") or "Unspecified").strip()
		counts[reason] = counts.get(reason, 0) + 1
	return [{"reason": reason, "count": count} for reason, count in sorted(counts.items())]


def get_bank_match_review_queue_summary(filters=None):
	assert_can_manage_bank_transaction_match()
	filters = _coerce_json_payload(filters)
	db_filters = {}
	for fieldname in ("company", "branch", "bank_account", "decision_status", "review_status", "match_status", "risk_level", "suggested_document_type"):
		if filters.get(fieldname):
			db_filters[fieldname] = filters.get(fieldname)
	if filters.get("from_date") and filters.get("to_date"):
		db_filters["transaction_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]

	rows = frappe.get_all(
		"RetailEdge Bank Transaction Match",
		filters=db_filters,
		fields=[
			"name",
			"decision_status",
			"review_status",
			"match_confidence",
			"risk_level",
			"transaction_date",
		],
		limit_page_length=0,
	)
	today = frappe.utils.nowdate()
	return {
		"total": len(rows),
		"draft_prepared": sum(1 for row in rows if row.get("decision_status") in {"Draft", "Suggested"}),
		"pending_review": sum(1 for row in rows if row.get("review_status") in {"Pending Review", "Needs Review", "Reopened"}),
		"ready_to_confirm": sum(1 for row in rows if row.get("review_status") == "Ready to Confirm"),
		"needs_review": sum(1 for row in rows if row.get("review_status") == "Needs Review"),
		"confirmed": sum(1 for row in rows if row.get("decision_status") == "Confirmed"),
		"high_confidence": sum(1 for row in rows if row.get("match_confidence") == "Strong Match"),
		"weak_needs_review": sum(1 for row in rows if row.get("match_confidence") == "Weak Match" or row.get("review_status") == "Needs Review"),
		"confirmed_today": sum(1 for row in rows if row.get("decision_status") == "Confirmed" and cstr(row.get("transaction_date")) == today),
		"rejected": sum(1 for row in rows if row.get("decision_status") == "Rejected"),
		"reopened": sum(1 for row in rows if row.get("decision_status") == "Reopened"),
		"cancelled": sum(1 for row in rows if row.get("decision_status") == "Cancelled"),
		"rejected_cancelled": sum(1 for row in rows if row.get("decision_status") in {"Rejected", "Cancelled"}),
		"duplicate_blocked": sum(1 for row in rows if row.get("risk_level") == "Blocked"),
	}


def bulk_confirm_bank_transaction_matches(match_names, remarks=None):
	assert_can_manage_bank_transaction_match()
	preview = preview_bulk_confirm_bank_transaction_matches(match_names)
	result = {
		"total_selected": preview["total_selected"],
		"confirmed_count": 0,
		"skipped_count": preview["blocked_count"],
		"blocked": preview["blocked"],
		"confirmed": [],
	}
	for row in preview["eligible"]:
		try:
			decision = confirm_bank_transaction_match(row["name"], decision_note=remarks)
			result["confirmed"].append(
				{
					"name": row["name"],
					"decision_status": decision.get("decision_status"),
					"message": decision.get("message"),
				}
			)
		except Exception as exc:
			result["blocked"].append({"name": row["name"], "reason": cstr(exc)})
			result["skipped_count"] += 1
	result["confirmed_count"] = len(result["confirmed"])
	return result


def bulk_mark_bank_transaction_matches_needs_review(match_names, remarks=None):
	assert_can_manage_bank_transaction_match()
	names = _coerce_match_names(match_names)
	result = {
		"total_selected": len(names),
		"updated_count": 0,
		"skipped_count": 0,
		"updated": [],
		"blocked": [],
	}
	for name in names:
		try:
			decision = mark_bank_transaction_match_needs_review(name, decision_note=remarks)
			result["updated"].append({"name": name, "decision_status": decision.get("decision_status")})
		except Exception as exc:
			result["blocked"].append({"name": name, "reason": cstr(exc)})
	result["updated_count"] = len(result["updated"])
	result["skipped_count"] = len(result["blocked"])
	return result


def create_bank_match_reviews_from_suggestions(filters=None, rows=None, selected_keys=None):
	assert_can_manage_bank_transaction_match()
	assert_can_access_bank_transaction_matching()
	suggestion_rows = _coerce_suggestion_rows(rows)
	if not suggestion_rows:
		suggestion_rows = get_bank_transaction_matching_rows(filters=_coerce_json_payload(filters), limit=500)

	selected = set(_coerce_selected_keys(selected_keys))
	if selected:
		suggestion_rows = [row for row in suggestion_rows if _suggestion_row_key(row) in selected]

	filters_payload = _coerce_json_payload(filters)
	suggestion_rows = [_lock_report_row_candidate(row, filters=filters_payload) for row in suggestion_rows]
	suggestion_rows, duplicate_candidate_rows = split_duplicate_candidate_suggestions(suggestion_rows)
	allow_rejected_pair_retry = bool(selected) and (
		cstr(filters_payload.get("review_queue_status")).strip() in {"Rejected", "All"}
		or cint(filters_payload.get("include_rejected_candidates") or 0)
	)
	result = {
		"status": "success",
		"message": "",
		"total_selected": len(suggestion_rows) + len(duplicate_candidate_rows),
		"created_count": 0,
		"duplicate_count": 0,
		"duplicate_candidate_skipped_count": len(duplicate_candidate_rows),
		"already_matched_count": 0,
		"unsafe_count": 0,
		"error_count": 0,
		"created": [],
		"duplicates": [],
		"duplicate_candidates": [
			_preparation_summary_row(
				row,
				reason=_duplicate_candidate_preparation_reason(row),
			)
			for row in duplicate_candidate_rows
		],
		"already_matched": [],
		"unsafe": [],
		"errors": [],
		"reasons": [],
	}

	for raw_row in suggestion_rows:
		row = frappe._dict(raw_row or {})
		try:
			classification = _classify_suggestion_review_preparation(
				row,
				allow_rejected_pair_retry=allow_rejected_pair_retry,
			)
			if classification["status"] != "eligible":
				_bucket = classification["status"]
				result[_bucket].append(classification["row"])
				_update_preparation_result_count(result, _bucket)
				continue

			created = create_or_get_bank_transaction_match(
				bank_transaction_name=row.get("bank_transaction"),
				suggested_document_type=row.get("suggested_document_type"),
				suggested_document=row.get("suggested_document"),
				sales_invoice=row.get("suggested_sales_invoice"),
				payment_entry=row.get("suggested_document") if row.get("suggested_document_type") == "Payment Entry" else None,
				source_report="Bank Transaction Matching",
				force_refresh=True,
				row_payload=row,
			)
			if not created.get("created"):
				result["duplicates"].append(
					_preparation_summary_row(row, reason=f"Review record already exists: {created.get('name')}.", match_record=created.get("name"))
				)
				result["duplicate_count"] = len(result["duplicates"])
				continue

			_prepare_created_match_review_record(created.get("name"), row)
			result["created"].append(
				_preparation_summary_row(
					row,
					reason="Review record created. It has not been confirmed.",
					match_record=created.get("name"),
				)
			)
			result["created_count"] = len(result["created"])
		except Exception as exc:
			result["errors"].append(_preparation_summary_row(row, reason=cstr(exc)))
			result["error_count"] = len(result["errors"])

	result["skipped_count"] = (
		result["duplicate_count"]
		+ result["duplicate_candidate_skipped_count"]
		+ result["already_matched_count"]
		+ result["unsafe_count"]
		+ result["error_count"]
	)
	result["blocked_count"] = result["already_matched_count"] + result["unsafe_count"] + result["error_count"]
	result["reasons"] = _summarize_preparation_reasons(result)
	result["message"] = (
		f"{result['total_selected']} filtered suggestions checked. "
		f"{result['created_count']} review records created, "
		f"{result['duplicate_candidate_skipped_count']} duplicate candidate suggestions skipped, "
		f"{result['duplicate_count']} skipped because review records already exist, "
		f"{result['already_matched_count']} blocked because candidates are already confirmed, "
		f"{result['unsafe_count']} unsafe rows skipped, "
		f"{result['error_count']} errors."
	)
	return result


def run_bank_transaction_auto_match(filters=None, rows=None, selected_keys=None):
	assert_can_manage_bank_transaction_match()
	assert_can_access_bank_transaction_matching()
	suggestion_rows = _coerce_suggestion_rows(rows)
	if not suggestion_rows:
		suggestion_rows = get_bank_transaction_matching_rows(filters=_coerce_json_payload(filters), limit=500)

	selected = set(_coerce_selected_keys(selected_keys))
	if selected:
		suggestion_rows = [row for row in suggestion_rows if _suggestion_row_key(row) in selected]

	filters_payload = _coerce_json_payload(filters)
	suggestion_rows = [_lock_report_row_candidate(row, filters=filters_payload) for row in suggestion_rows]
	suggestion_rows, duplicate_candidate_rows = split_duplicate_candidate_suggestions(suggestion_rows)
	settings = get_bank_transaction_matching_settings()
	result = {
		"status": "success",
		"message": "",
		"checked_count": len(suggestion_rows) + len(duplicate_candidate_rows),
		"auto_prepared_count": 0,
		"auto_confirmed_count": 0,
		"blocked_count": 0,
		"skipped_count": 0,
		"duplicate_candidate_skipped_count": len(duplicate_candidate_rows),
		"review_record_exists_count": 0,
		"already_confirmed_count": 0,
		"manual_review_count": 0,
		"error_count": 0,
		"auto_prepared": [],
		"auto_confirmed": [],
		"duplicate_candidates": [
			_preparation_summary_row(
				row,
				reason=_duplicate_candidate_preparation_reason(row),
			)
			for row in duplicate_candidate_rows
		],
		"review_record_exists": [],
		"already_confirmed": [],
		"manual_review": [],
		"errors": [],
		"reasons": [],
	}

	for raw_row in suggestion_rows:
		row = frappe._dict(raw_row or {})
		try:
			preparation = _classify_suggestion_review_preparation(
				row,
				allow_rejected_pair_retry=False,
				for_auto_match=True,
			)
			if preparation["status"] != "eligible":
				_bucket = _auto_match_bucket_for_preparation_status(preparation["status"])
				result[_bucket].append(preparation["row"])
				_update_auto_match_result_count(result, _bucket)
				continue

			auto_status = get_auto_match_status_for_row(row, settings=settings)
			if not (auto_status.get("eligible_prepare") or auto_status.get("eligible_confirm")):
				result["manual_review"].append(
					_preparation_summary_row(
						row,
						reason=auto_status.get("reason") or "This suggestion is not eligible for RetailEdge auto-match.",
					)
				)
				result["manual_review_count"] = len(result["manual_review"])
				continue

			created = create_or_get_bank_transaction_match(
				bank_transaction_name=row.get("bank_transaction"),
				suggested_document_type=row.get("suggested_document_type"),
				suggested_document=row.get("suggested_document"),
				sales_invoice=row.get("suggested_sales_invoice"),
				payment_entry=row.get("suggested_document") if row.get("suggested_document_type") == "Payment Entry" else None,
				source_report="Bank Transaction Matching",
				force_refresh=True,
				row_payload=row,
			)
			match_name = created.get("name")
			if not created.get("created"):
				result["review_record_exists"].append(
					_preparation_summary_row(
						row,
						reason=f"Review record already exists: {match_name}.",
						match_record=match_name,
					)
				)
				result["review_record_exists_count"] = len(result["review_record_exists"])
				continue

			if auto_status.get("eligible_confirm"):
				decision = _auto_confirm_bank_transaction_match(match_name, row, auto_status, settings)
				result["auto_confirmed"].append(
					_preparation_summary_row(
						row,
						reason=decision.get("message"),
						match_record=match_name,
					)
				)
				result["auto_confirmed_count"] = len(result["auto_confirmed"])
			else:
				_auto_prepare_bank_transaction_match(match_name, row, auto_status, settings)
				result["auto_prepared"].append(
					_preparation_summary_row(
						row,
						reason=auto_status.get("reason") or "Exact high-confidence match prepared automatically.",
						match_record=match_name,
					)
				)
				result["auto_prepared_count"] = len(result["auto_prepared"])
		except Exception as exc:
			result["errors"].append(_preparation_summary_row(row, reason=cstr(exc)))
			result["error_count"] = len(result["errors"])

	result["blocked_count"] = (
		result["duplicate_candidate_skipped_count"]
		+ result["review_record_exists_count"]
		+ result["already_confirmed_count"]
		+ result["manual_review_count"]
		+ result["error_count"]
	)
	result["skipped_count"] = result["blocked_count"]
	result["reasons"] = _summarize_auto_match_reasons(result)
	result["message"] = (
		f"{result['checked_count']} suggestions checked. "
		f"{result['auto_prepared_count']} RetailEdge review records auto-prepared, "
		f"{result['auto_confirmed_count']} RetailEdge review records auto-confirmed, "
		f"{result['manual_review_count']} blocked for manual review, "
		f"{result['review_record_exists_count']} skipped because review records already exist, "
		f"{result['already_confirmed_count']} skipped because candidates are already confirmed, "
		f"{result['duplicate_candidate_skipped_count']} duplicate candidates skipped, "
		f"{result['error_count']} errors."
	)
	return result


def _summarize_preparation_reasons(result):
	counts = {}
	for bucket in ("duplicate_candidates", "duplicates", "already_matched", "unsafe", "errors"):
		for row in result.get(bucket) or []:
			reason = cstr(row.get("reason") or "Unspecified").strip()
			counts[reason] = counts.get(reason, 0) + 1
	return [{"reason": reason, "count": count} for reason, count in sorted(counts.items())]


def _summarize_auto_match_reasons(result):
	counts = {}
	for bucket in ("duplicate_candidates", "review_record_exists", "already_confirmed", "manual_review", "errors"):
		for row in result.get(bucket) or []:
			reason = cstr(row.get("reason") or "Unspecified").strip()
			counts[reason] = counts.get(reason, 0) + 1
	return [{"reason": reason, "count": count} for reason, count in sorted(counts.items())]


def _auto_match_bucket_for_preparation_status(status):
	return {
		"duplicates": "review_record_exists",
		"already_matched": "already_confirmed",
		"unsafe": "manual_review",
		"errors": "errors",
	}.get(status, "manual_review")


def _update_auto_match_result_count(result, bucket):
	count_field = {
		"review_record_exists": "review_record_exists_count",
		"already_confirmed": "already_confirmed_count",
		"manual_review": "manual_review_count",
		"errors": "error_count",
	}.get(bucket, f"{bucket}_count")
	result[count_field] = len(result[bucket])


def _duplicate_candidate_preparation_reason(row):
	winner = cstr((row or {}).get("duplicate_candidate_winner_bank_transaction")).strip()
	if winner:
		return f"Candidate already suggested in this batch/current queue. Kept suggestion is {winner}."
	return "Candidate already suggested in this batch/current queue."


def _update_preparation_result_count(result, bucket):
	count_field = {
		"duplicates": "duplicate_count",
		"duplicate_candidates": "duplicate_candidate_skipped_count",
		"already_matched": "already_matched_count",
		"unsafe": "unsafe_count",
		"errors": "error_count",
	}.get(bucket, f"{bucket}_count")
	result[count_field] = len(result[bucket])


def _increment_bulk_preview_category(result, category):
	if category == "already_confirmed":
		result["already_confirmed_count"] += 1
	elif category == "duplicate_blocked":
		result["duplicate_blocked_count"] += 1
	elif category == "weak_needs_review":
		result["weak_needs_review_count"] += 1
	elif category == "unsafe":
		result["unsafe_count"] += 1
	else:
		result["skipped_count"] += 1


def append_bank_transaction_match_action_log(doc, action, old_status=None, new_status=None, remarks=None, details=None):
	doc.append(
		"action_logs",
		{
			"action": action,
			"action_by": frappe.session.user,
			"action_on": now_datetime(),
			"old_status": old_status,
			"new_status": new_status,
			"remarks": remarks,
			"details_json": json.dumps(details or {}, default=str, sort_keys=True, indent=2),
		},
	)
	doc.last_action = action
	doc.last_action_by = frappe.session.user
	doc.last_action_on = now_datetime()


def _save_match_preserving_selected_candidate(doc, ignore_permissions=True):
	if not getattr(doc, "flags", None):
		doc.flags = frappe._dict()
	doc.flags.retailedge_preserve_selected_candidate = True
	doc.save(ignore_permissions=ignore_permissions)


def _coerce_match_names(match_names):
	if isinstance(match_names, str):
		try:
			match_names = json.loads(match_names)
		except Exception:
			match_names = [match_names]
	names = []
	for name in match_names or []:
		value = cstr(name.get("name") if isinstance(name, dict) else name).strip()
		if value and value not in names:
			names.append(value)
	return names


def _coerce_json_payload(value):
	if isinstance(value, str):
		try:
			return frappe._dict(json.loads(value))
		except Exception:
			return frappe._dict()
	return frappe._dict(value or {})


def _coerce_suggestion_rows(rows):
	if isinstance(rows, str):
		try:
			rows = json.loads(rows)
		except Exception:
			rows = []
	return [frappe._dict(row or {}) for row in rows or [] if isinstance(row, dict)]


def _coerce_selected_keys(selected_keys):
	if isinstance(selected_keys, str):
		try:
			selected_keys = json.loads(selected_keys)
		except Exception:
			selected_keys = [selected_keys]
	keys = []
	for key in selected_keys or []:
		value = cstr(key).strip()
		if value and value not in keys:
			keys.append(value)
	return keys


def _suggestion_row_key(row):
	row = row or {}
	return cstr(row.get("candidate_key")).strip() or _build_report_row_candidate_key(row)


EXACT_SELECTED_ROW_DRIFT_MESSAGE = "Current best candidate differs from the selected report row. Refresh the report and review again."


def _build_report_row_candidate_key(row):
	row = frappe._dict(row or {})
	return "|".join(
		[
			cstr(row.get("bank_transaction")).strip(),
			cstr(row.get("suggested_document_type") or row.get("document_type")).strip(),
			cstr(row.get("suggested_document") or row.get("document_name")).strip(),
			cstr(row.get("candidate_category")).strip(),
			cstr(row.get("payment_event_source")).strip(),
			cstr(row.get("payment_row_index") or row.get("payment_row_reference")).strip(),
		]
	)


def _normalize_report_row_candidate_payload(row):
	row = frappe._dict(_coerce_json_payload(row))
	if not row:
		return frappe._dict()
	row.setdefault("bank_transaction", cstr(row.get("bank_transaction")).strip())
	row.setdefault("suggested_document_type", cstr(row.get("suggested_document_type") or row.get("document_type")).strip())
	row.setdefault("suggested_document", cstr(row.get("suggested_document") or row.get("document_name")).strip())
	row.setdefault("sales_invoice", cstr(row.get("sales_invoice") or row.get("suggested_sales_invoice") or (row.get("suggested_document") if row.get("suggested_document_type") == "Sales Invoice" else "")).strip())
	row.setdefault("payment_entry", cstr(row.get("payment_entry") or (row.get("suggested_document") if row.get("suggested_document_type") == "Payment Entry" else "")).strip())
	explicit_candidate_key = cstr(row.get("candidate_key")).strip()
	_extract_payment_event_candidate_from_report_row(row)
	row.setdefault("candidate_key", _build_report_row_candidate_key(row))
	row.setdefault("candidate_locked", 1 if cint(row.get("candidate_locked") or 0) or explicit_candidate_key else 0)
	return row


def _extract_payment_event_candidate_from_report_row(row):
	row = frappe._dict(row or {})
	document_type = cstr(row.get("suggested_document_type") or row.get("document_type")).strip()
	document_name = cstr(row.get("suggested_document") or row.get("document_name")).strip()
	category_key = normalize_candidate_category_key(row.get("candidate_category"))
	payment_event_source = cstr(row.get("payment_event_source")).strip()
	payment_row_identity = cstr(row.get("payment_row_index") or row.get("payment_row_reference")).strip()
	payment_mode = cstr(row.get("payment_mode") or row.get("mode_of_payment")).strip()
	payment_account = cstr(row.get("resolved_payment_account") or row.get("payment_account")).strip()
	payment_text = f"{payment_mode} {payment_account}".lower()

	if document_type == "Payment Entry" or category_key == "payment_entry_match":
		if document_name:
			row["suggested_document_type"] = "Payment Entry"
			row["suggested_document"] = document_name
			row["payment_entry"] = cstr(row.get("payment_entry") or document_name).strip()
			row["candidate_category"] = category_key or "payment_entry_match"
			row["payment_event_source"] = payment_event_source or "Payment Entry"
			row["payment_event_found"] = 1
		return row

	if category_key not in {"invoice_payment_row_match", "pos_payment_match"}:
		return row
	if document_type != "Sales Invoice" or not document_name:
		return row
	if "cash" in payment_text:
		return row
	if not payment_event_source:
		payment_event_source = "POS Payment Row" if category_key == "pos_payment_match" else "Invoice Payment Row"
	if payment_row_identity and payment_account:
		row["suggested_document_type"] = "Sales Invoice"
		row["suggested_document"] = document_name
		row["sales_invoice"] = cstr(row.get("sales_invoice") or row.get("suggested_sales_invoice") or document_name).strip()
		row["suggested_sales_invoice"] = cstr(row.get("suggested_sales_invoice") or row.get("sales_invoice") or document_name).strip()
		row["candidate_category"] = category_key
		row["payment_event_source"] = payment_event_source
		row["payment_row_index"] = row.get("payment_row_index") or payment_row_identity
		row["payment_row_reference"] = row.get("payment_row_reference") or payment_row_identity
		row["payment_account"] = row.get("payment_account") or payment_account
		row["resolved_payment_account"] = row.get("resolved_payment_account") or payment_account
		row["payment_event_found"] = 1
	return row


def _selected_row_matches_candidate(row, candidate):
	row = frappe._dict(row or {})
	candidate = frappe._dict(candidate or {})
	if not row or not candidate:
		return False
	comparisons = {
		"suggested_document_type": cstr(candidate.get("document_type") or candidate.get("suggested_document_type")).strip(),
		"suggested_document": cstr(candidate.get("document_name") or candidate.get("suggested_document")).strip(),
		"candidate_category": cstr(candidate.get("candidate_category")).strip(),
		"payment_event_source": cstr(candidate.get("payment_event_source")).strip(),
		"payment_row_index": cstr(candidate.get("payment_row_index") or candidate.get("payment_row_reference")).strip(),
	}
	for fieldname, expected in comparisons.items():
		actual = cstr(row.get(fieldname)).strip()
		if fieldname == "candidate_category":
			actual = normalize_candidate_category_key(actual)
			expected = normalize_candidate_category_key(expected)
		if expected and actual and actual != expected:
			return False
	if comparisons["suggested_document_type"] and cstr(row.get("suggested_document_type")).strip() != comparisons["suggested_document_type"]:
		return False
	if comparisons["suggested_document"] and cstr(row.get("suggested_document")).strip() != comparisons["suggested_document"]:
		return False
	return True


def _lock_report_row_candidate(row, filters=None):
	row = _normalize_report_row_candidate_payload(row)
	if not row.get("candidate_locked"):
		return row
	exact_candidate = _resolve_matching_candidate(
		bank_transaction_name=row.get("bank_transaction"),
		suggested_document_type=row.get("suggested_document_type"),
		suggested_document=row.get("suggested_document"),
		sales_invoice=row.get("sales_invoice"),
		payment_entry=row.get("payment_entry"),
	)
	if not exact_candidate or not _selected_row_matches_candidate(row, exact_candidate):
		row["candidate_identity_valid"] = 0
		row["candidate_changed_reason"] = "Selected report row candidate is no longer available. Refresh the report and review again."
		return row
	_enrich_report_row_from_resolved_candidate(row, exact_candidate)
	row["candidate_identity_valid"] = 1
	row["candidate_changed_reason"] = None
	return row


def _enrich_report_row_from_resolved_candidate(row, candidate):
	row = frappe._dict(row or {})
	candidate = frappe._dict(candidate or {})
	field_map = {
		"candidate_category": candidate.get("candidate_category"),
		"payment_event_found": candidate.get("payment_event_found"),
		"payment_event_source": candidate.get("payment_event_source"),
		"payment_row_index": candidate.get("payment_row_index"),
		"payment_row_reference": candidate.get("payment_row_reference") or candidate.get("payment_row_index"),
		"payment_mode": candidate.get("payment_mode") or candidate.get("mode_of_payment"),
		"mode_of_payment": candidate.get("mode_of_payment") or candidate.get("payment_mode"),
		"payment_account": candidate.get("payment_account"),
		"resolved_payment_account": candidate.get("resolved_payment_account") or candidate.get("candidate_canonical_account"),
		"candidate_amount": candidate.get("candidate_amount"),
		"payment_row_amount": candidate.get("payment_row_amount") or candidate.get("candidate_amount"),
		"candidate_posting_date": candidate.get("posting_date") or candidate.get("candidate_posting_date"),
		"match_score": candidate.get("score"),
		"match_confidence": candidate.get("confidence"),
		"account_resolution_status": candidate.get("account_resolution_status"),
	}
	for fieldname, value in field_map.items():
		if value not in (None, "") and row.get(fieldname) in (None, ""):
			row[fieldname] = value
	if normalize_candidate_category_key(row.get("candidate_category")) in {"payment_entry_match", "invoice_payment_row_match", "pos_payment_match"}:
		row["payment_event_found"] = cint(row.get("payment_event_found") or 1)
	return row

def _build_candidate_from_report_row(row):
	row = _normalize_report_row_candidate_payload(row)
	document_type = cstr(row.get("suggested_document_type")).strip()
	document_name = cstr(row.get("suggested_document")).strip()
	payment_account = cstr(row.get("resolved_payment_account") or row.get("payment_account")).strip()
	return frappe._dict({
		"_from_selected_row": 1,
		"document_type": document_type,
		"document_name": document_name,
		"suggested_document_type": document_type,
		"suggested_document": document_name,
		"suggested_sales_invoice": cstr(row.get("sales_invoice") or row.get("suggested_sales_invoice")).strip() or None,
		"posting_date": row.get("candidate_posting_date"),
		"company": row.get("company"),
		"branch": row.get("branch"),
		"customer": row.get("customer"),
		"party": row.get("party") or row.get("customer"),
		"party_type": row.get("party_type") or "Customer",
		"candidate_amount": flt(row.get("candidate_amount")),
		"candidate_category": row.get("candidate_category"),
		"payment_event_found": cint(row.get("payment_event_found") or (1 if row.get("payment_event_source") else 0)),
		"payment_event_source": row.get("payment_event_source"),
		"payment_row_index": row.get("payment_row_index"),
		"payment_mode": row.get("payment_mode"),
		"payment_account": row.get("payment_account"),
		"resolved_payment_account": row.get("resolved_payment_account"),
		"account": payment_account or row.get("payment_account"),
		"reference": row.get("candidate_reference") or row.get("reference"),
		"payment_entry_paid_amount": row.get("payment_entry_paid_amount"),
		"payment_entry_allocated_amount": row.get("payment_entry_allocated_amount"),
		"sales_invoice_outstanding_amount": row.get("sales_invoice_outstanding_amount"),
		"sales_invoice_grand_total": row.get("sales_invoice_grand_total"),
		"payment_row_amount": row.get("payment_row_amount") or row.get("candidate_amount"),
		"payment_entry_invoice_context": row.get("payment_entry_invoice_context"),
		"multi_invoice_references": row.get("multi_invoice_references"),
		"amount_scenario": row.get("amount_scenario"),
		"amount_scenario_label": row.get("amount_scenario_label"),
		"exception_only": row.get("exception_only"),
		"exception_type": row.get("exception_type"),
		"score": row.get("match_score"),
		"confidence": row.get("match_confidence"),
		"account_resolution_status": row.get("account_resolution_status"),
		"account_resolution_reason": row.get("account_resolution_reason"),
		"candidate_canonical_account": row.get("resolved_payment_account") or row.get("payment_account"),
		"reasons": [cstr(row.get("match_reason")).strip()] if cstr(row.get("match_reason")).strip() else [],
	})


def _revalidate_suggestion_row(row, filters=None):
	row = frappe._dict(row or {})
	bank_transaction_name = cstr(row.get("bank_transaction")).strip()
	if not bank_transaction_name:
		return row
	try:
		bank_transaction = normalize_bank_transaction(bank_transaction_name)
	except Exception:
		return row
	candidate_filters = frappe._dict(_coerce_json_payload(filters))
	candidate_filters["include_exception_candidates"] = 1
	candidate_filters["include_confirmed_matches"] = 1
	candidates = find_sales_invoice_candidates_for_bank_transaction(
		bank_transaction_name,
		filters=candidate_filters,
		limit=20,
	) + find_payment_entry_candidates_for_bank_transaction(
		bank_transaction_name,
		filters=candidate_filters,
		limit=20,
	)
	best_candidate, _selected_match = _select_candidate_for_queue(candidates, [], candidate_filters)
	if not best_candidate:
		return frappe._dict(
			_build_matching_row(
				bank_transaction,
				candidate=None,
				action_status=_derive_action_status(bank_transaction, None),
				match_reason="No candidate reached the minimum matching confidence.",
			)
		)
	resolved = frappe._dict(
		_build_matching_row(
			bank_transaction,
			candidate=best_candidate,
			action_status=_derive_action_status(bank_transaction, best_candidate),
			match_reason="; ".join((best_candidate or {}).get("reasons") or []) or best_candidate.get("reason"),
		)
	)
	original_key = _suggestion_row_key(row)
	resolved_key = _suggestion_row_key(resolved)
	if original_key and resolved_key and original_key != resolved_key:
		resolved["candidate_revalidated"] = 1
		resolved["candidate_changed_reason"] = (
			"Current best suggestion differs from the candidate sent by Desk. RetailEdge revalidated this bank transaction server-side before proceeding."
		)
		resolved["original_suggested_document_type"] = row.get("suggested_document_type")
		resolved["original_suggested_document"] = row.get("suggested_document")
	return resolved


def _classify_suggestion_review_preparation(row, allow_rejected_pair_retry=False, for_auto_match=False):
	bank_transaction = cstr(row.get("bank_transaction")).strip()
	suggested_document_type = cstr(row.get("suggested_document_type")).strip()
	suggested_document = cstr(row.get("suggested_document")).strip()
	sales_invoice = cstr(row.get("suggested_sales_invoice") or suggested_document if suggested_document_type == "Sales Invoice" else row.get("suggested_sales_invoice")).strip()
	payment_entry = cstr(suggested_document if suggested_document_type == "Payment Entry" else row.get("payment_entry")).strip()

	if cint(row.get("candidate_locked")) and cint(row.get("candidate_identity_valid")) == 0:
		return {
			"status": "unsafe",
			"row": _preparation_summary_row(
				row,
				reason=cstr(row.get("candidate_changed_reason")).strip() or EXACT_SELECTED_ROW_DRIFT_MESSAGE,
			),
		}
	if not bank_transaction:
		return {"status": "unsafe", "row": _preparation_summary_row(row, reason="Missing Bank Transaction.")}
	if not frappe.db.exists("Bank Transaction", bank_transaction):
		return {"status": "unsafe", "row": _preparation_summary_row(row, reason=f"Bank Transaction {bank_transaction} does not exist.")}
	if suggested_document_type not in {"Sales Invoice", "Payment Entry"} or not suggested_document:
		return {"status": "unsafe", "row": _preparation_summary_row(row, reason=NO_MATCH_CANDIDATE_MESSAGE)}
	if not frappe.db.exists(suggested_document_type, suggested_document):
		return {
			"status": "unsafe",
			"row": _preparation_summary_row(row, reason=f"{suggested_document_type} {suggested_document} does not exist."),
		}
	payment_basis_candidate = {
		"suggested_document_type": suggested_document_type,
		"suggested_document": suggested_document,
		"document_type": suggested_document_type,
		"document_name": suggested_document,
		"candidate_category": row.get("candidate_category"),
		"payment_event_found": row.get("payment_event_found"),
		"payment_event_source": row.get("payment_event_source"),
		"payment_row_index": row.get("payment_row_index"),
		"payment_row_reference": row.get("payment_row_reference"),
		"payment_mode": row.get("payment_mode") or row.get("mode_of_payment"),
		"mode_of_payment": row.get("mode_of_payment") or row.get("payment_mode"),
		"payment_account": row.get("payment_account"),
		"resolved_payment_account": row.get("resolved_payment_account"),
		"candidate_amount": row.get("candidate_amount"),
		"payment_row_amount": row.get("payment_row_amount") or row.get("candidate_amount"),
	}
	if not is_payment_basis_review_candidate(payment_basis_candidate):
		return {
			"status": "unsafe",
			"row": _preparation_summary_row(
				row,
				reason=get_review_creation_block_reason(payment_basis_candidate)
				or "Sales Invoice is context only; payment event evidence is required for review creation and auto-match.",
			),
		}
	if cstr(row.get("decision_status")).strip() == "Confirmed" or cstr(row.get("action_status")).strip() == "Already Confirmed":
		return {"status": "already_matched", "row": _preparation_summary_row(row, reason="Candidate is already confirmed.")}
	rejected_pair_match = _find_rejected_exact_pair_match(
		bank_transaction=bank_transaction,
		suggested_document_type=suggested_document_type,
		suggested_document=suggested_document,
		payment_event_source=row.get("payment_event_source"),
		payment_row_index=row.get("payment_row_index") or row.get("payment_row_reference"),
	)
	if rejected_pair_match and (for_auto_match or not allow_rejected_pair_retry):
		return {
			"status": "duplicates",
			"row": _preparation_summary_row(
				row,
				reason="Previously rejected match pair.",
				match_record=rejected_pair_match,
			),
		}
	if cstr(row.get("action_status")).strip() == "Duplicate Candidate" or cint(row.get("duplicate_candidate_skipped")):
		return {
			"status": "duplicate_candidates",
			"row": _preparation_summary_row(row, reason="Candidate already suggested in this batch/current queue."),
		}
	if cstr(row.get("action_status")).strip() == "Exception Only" or cint(row.get("exception_only")):
		return {
			"status": "unsafe",
			"row": _preparation_summary_row(
				row,
				reason="Date/account exception candidates are investigation-only and cannot be prepared for normal confirmation in this phase.",
			),
		}
	scenario_label = get_amount_scenario_label(row.get("amount_scenario")) or cstr(row.get("amount_scenario")).strip()
	if amount_scenario_requires_manual_review(row.get("amount_scenario")):
		return {
			"status": "unsafe",
			"row": _preparation_summary_row(
				row,
				reason=(f"{scenario_label} requires manual review. Use single-row Review for manual investigation." if scenario_label else "Manual review scenario cannot be bulk-created. Use single-row Review for manual investigation."),
			),
		}
	if cstr(row.get("match_confidence")).strip() == "Weak Match":
		return {
			"status": "unsafe",
			"row": _preparation_summary_row(
				row,
				reason="Weak Match requires manual review. Use single-row Review for manual investigation.",
			),
		}
	if sales_invoice and sales_invoice_has_active_confirmed_bank_match(sales_invoice):
		return {
			"status": "already_matched",
			"row": _preparation_summary_row(row, reason="Sales Invoice already has a confirmed bank match."),
		}
	if payment_entry and payment_entry_has_active_confirmed_bank_match(payment_entry):
		return {
			"status": "already_matched",
			"row": _preparation_summary_row(row, reason="Payment Entry already has a confirmed bank match."),
		}
	active_bank_transaction_match = _find_active_bank_transaction_review_match(bank_transaction)
	if active_bank_transaction_match:
		active_status = frappe.db.get_value("RetailEdge Bank Transaction Match", active_bank_transaction_match, "decision_status")
		reason = (
			f"Bank Transaction already has confirmed match {active_bank_transaction_match}."
			if cstr(active_status).strip() == "Confirmed"
			else f"Active review record already exists for Bank Transaction: {active_bank_transaction_match}."
		)
		return {
			"status": "already_matched" if cstr(active_status).strip() == "Confirmed" else "duplicates",
			"row": _preparation_summary_row(
				row,
				reason=reason,
				match_record=active_bank_transaction_match,
			),
		}
	existing_match = _find_existing_match_name(
		bank_transaction=bank_transaction,
		suggested_document_type=suggested_document_type,
		suggested_document=suggested_document,
		payment_event_source=row.get("payment_event_source"),
		payment_row_index=row.get("payment_row_index") or row.get("payment_row_reference"),
	)
	if existing_match:
		return {
			"status": "duplicates",
			"row": _preparation_summary_row(row, reason=f"Review record already exists: {existing_match}.", match_record=existing_match),
		}
	active_candidate_match = _find_active_candidate_review_match(
		suggested_document_type=suggested_document_type,
		suggested_document=suggested_document,
		payment_event_source=row.get("payment_event_source"),
		payment_row_index=row.get("payment_row_index") or row.get("payment_row_reference"),
	)
	if active_candidate_match:
		return {
			"status": "duplicates",
			"row": _preparation_summary_row(
				row,
				reason=f"Candidate already has active review record {active_candidate_match}.",
				match_record=active_candidate_match,
			),
		}
	return {"status": "eligible", "row": _preparation_summary_row(row, reason="Eligible for review record creation.")}


def _find_active_bank_transaction_review_match(bank_transaction):
	if not bank_transaction:
		return None
	status_filter = ["not in", ["Rejected", "Cancelled", "Reopened"]]
	return frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{"bank_transaction": bank_transaction, "decision_status": status_filter},
		"name",
	)


def _find_active_candidate_review_match(suggested_document_type, suggested_document, payment_event_source=None, payment_row_index=None):
	if not suggested_document_type or not suggested_document:
		return None
	status_filter = ["not in", ["Rejected", "Cancelled", "Reopened"]]
	filters = {
		"suggested_document_type": suggested_document_type,
		"suggested_document": suggested_document,
		"decision_status": status_filter,
	}
	if suggested_document_type == "Sales Invoice" and payment_row_index not in (None, ""):
		filters["payment_row_index"] = payment_row_index
	if suggested_document_type == "Sales Invoice" and cstr(payment_event_source).strip():
		filters["payment_event_source"] = payment_event_source
	name = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		filters,
		"name",
	)
	if name:
		return name
	if suggested_document_type == "Sales Invoice":
		invoice_filters = {"sales_invoice": suggested_document, "decision_status": status_filter}
		if payment_row_index not in (None, ""):
			invoice_filters["payment_row_index"] = payment_row_index
		if cstr(payment_event_source).strip():
			invoice_filters["payment_event_source"] = payment_event_source
		return frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			invoice_filters,
			"name",
		)
	if suggested_document_type == "Payment Entry":
		return frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{"payment_entry": suggested_document, "decision_status": status_filter},
			"name",
		)
	return None

def _find_rejected_exact_pair_match(bank_transaction, suggested_document_type, suggested_document, payment_event_source=None, payment_row_index=None):
	if not bank_transaction or not suggested_document_type or not suggested_document:
		return None
	filters = {
		"bank_transaction": bank_transaction,
		"suggested_document_type": suggested_document_type,
		"suggested_document": suggested_document,
		"decision_status": "Rejected",
	}
	if suggested_document_type == "Sales Invoice" and payment_row_index not in (None, ""):
		filters["payment_row_index"] = payment_row_index
	if suggested_document_type == "Sales Invoice" and cstr(payment_event_source).strip():
		filters["payment_event_source"] = payment_event_source
	return frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		filters,
		"name",
	)


def _prepare_created_match_review_record(match_name, row):
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	old_status = cstr(doc.decision_status or "Suggested")
	remarks = "Prepared from Bank Transaction Matching report. Review before confirming."
	if cstr(row.get("action_status")).strip() == "Exception Only" or cint(row.get("exception_only")):
		doc.decision_status = "Needs Review"
		remarks = "Prepared as an exception-only review because the date or bank account does not match normal safety rules."
	elif cstr(row.get("match_confidence")).strip() == "Weak Match":
		doc.decision_status = "Needs Review"
		remarks = "Prepared as Needs Review because the suggested match confidence is weak."
	if hasattr(doc, "amount_scenario"):
		doc.amount_scenario = get_amount_scenario_label(row.get("amount_scenario")) or row.get("amount_scenario")
	if hasattr(doc, "amount_breakdown_summary"):
		doc.amount_breakdown_summary = _build_amount_breakdown_summary(row)
	doc.decision_note = remarks
	append_bank_transaction_match_action_log(
		doc,
		action="Prepared",
		old_status=old_status,
		new_status=doc.decision_status,
		remarks=remarks,
		details={
			"bank_transaction": row.get("bank_transaction"),
			"suggested_document_type": row.get("suggested_document_type"),
			"suggested_document": row.get("suggested_document"),
			"match_confidence": row.get("match_confidence"),
			"match_score": row.get("match_score"),
			"amount_scenario": row.get("amount_scenario"),
			"amount_scenario_label": get_amount_scenario_label(row.get("amount_scenario")),
			"amount_breakdown_summary": _build_amount_breakdown_summary(row),
			"sales_invoice_outstanding_amount": row.get("sales_invoice_outstanding_amount"),
			"sales_invoice_grand_total": row.get("sales_invoice_grand_total"),
			"payment_entry_paid_amount": row.get("payment_entry_paid_amount"),
			"payment_entry_allocated_amount": row.get("payment_entry_allocated_amount"),
			"payment_row_index": row.get("payment_row_index"),
			"payment_entry_invoice_context": row.get("payment_entry_invoice_context"),
			"multi_invoice_references": row.get("multi_invoice_references"),
		},
	)
	_save_match_preserving_selected_candidate(doc)


def _auto_prepare_bank_transaction_match(match_name, row, auto_status, settings):
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	old_status = cstr(doc.decision_status or "Suggested")
	reason = (
		cstr(auto_status.get("reason")).strip()
		or "Exact high-confidence match auto-prepared as a RetailEdge Bank Match Review record only."
	)
	doc.decision_status = "Suggested"
	doc.decision_note = reason
	if hasattr(doc, "amount_scenario"):
		doc.amount_scenario = get_amount_scenario_label(row.get("amount_scenario")) or row.get("amount_scenario")
	if hasattr(doc, "amount_breakdown_summary"):
		doc.amount_breakdown_summary = _build_amount_breakdown_summary(row)
	append_bank_transaction_match_action_log(
		doc,
		action="Auto Prepared",
		old_status=old_status,
		new_status=doc.decision_status,
		remarks=reason,
		details=_build_auto_match_action_details(row, settings, auto_action="Auto Prepared"),
	)
	_save_match_preserving_selected_candidate(doc)


def _auto_confirm_bank_transaction_match(match_name, row, auto_status, settings):
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	if not _stored_candidate_matches_row(doc, row):
		frappe.throw("Current best candidate differs from the reviewed candidate. Manual review required.")
	reason = (
		cstr(auto_status.get("reason")).strip()
		or "Exact high-confidence RetailEdge Bank Match Review record auto-confirmed by RetailEdge settings only."
	)
	return _apply_bank_transaction_match_decision(
		match_name=match_name,
		action="Auto Confirmed",
		new_status="Confirmed",
		decision_note=reason,
		allowed_current_statuses={"Draft", "Suggested", "Needs Review", "Reopened"},
		success_message="Exact high-confidence RetailEdge Bank Match Review record auto-confirmed by RetailEdge settings only. No reconciliation or accounting posting was performed.",
		details=_build_auto_match_action_details(row, settings, auto_action="Auto Confirmed"),
	)


def _build_auto_match_action_details(row, settings, auto_action):
	return {
		"auto_match_action": auto_action,
		"bank_transaction": row.get("bank_transaction"),
		"suggested_document_type": row.get("suggested_document_type"),
		"suggested_document": row.get("suggested_document"),
		"suggested_sales_invoice": row.get("suggested_sales_invoice"),
		"candidate_category": row.get("candidate_category"),
		"candidate_category_label": get_candidate_category_label(row.get("candidate_category")),
		"match_confidence": row.get("match_confidence"),
		"match_score": row.get("match_score"),
		"amount_scenario": row.get("amount_scenario"),
		"amount_scenario_label": get_amount_scenario_label(row.get("amount_scenario")),
		"amount_breakdown_summary": _build_amount_breakdown_summary(row),
		"payment_event_source": row.get("payment_event_source"),
		"payment_row_index": row.get("payment_row_index"),
		"payment_mode": row.get("payment_mode"),
		"payment_account": row.get("payment_account"),
		"reference_match_exact": row.get("reference_match_exact"),
		"account_match": row.get("account_match"),
		"branch_match": row.get("branch_match"),
		"settings_snapshot": {
			"enable_bank_auto_match": settings.get("enable_bank_auto_match"),
			"auto_prepare_exact_bank_matches": settings.get("auto_prepare_exact_bank_matches"),
			"auto_confirm_exact_bank_matches": settings.get("auto_confirm_exact_bank_matches"),
			"minimum_auto_match_score": settings.get("minimum_auto_match_score"),
			"require_exact_reference_for_auto_match": settings.get("require_exact_reference_for_auto_match"),
			"require_same_bank_account_for_auto_match": settings.get("require_same_bank_account_for_auto_match"),
			"require_same_branch_for_auto_match": settings.get("require_same_branch_for_auto_match"),
			"allow_auto_match_payment_entry": settings.get("allow_auto_match_payment_entry"),
			"allow_auto_match_sales_invoice": settings.get("allow_auto_match_sales_invoice"),
		},
	}


def _preparation_summary_row(row, reason=None, match_record=None):
	return {
		"bank_transaction": row.get("bank_transaction"),
		"suggested_document_type": row.get("suggested_document_type"),
		"suggested_document": row.get("suggested_document"),
		"suggested_sales_invoice": row.get("suggested_sales_invoice"),
		"candidate_category": row.get("candidate_category"),
		"candidate_category_label": get_candidate_category_label(row.get("candidate_category")),
		"customer": row.get("customer"),
		"match_confidence": row.get("match_confidence"),
		"match_score": row.get("match_score"),
		"amount_scenario": row.get("amount_scenario"),
		"amount_scenario_label": get_amount_scenario_label(row.get("amount_scenario")),
		"payment_event_source": row.get("payment_event_source"),
		"payment_row_index": row.get("payment_row_index"),
		"match_record": match_record or row.get("match_record"),
		"reason": reason,
	}


def _build_amount_breakdown_summary(row):
	row = frappe._dict(row or {})
	lines = []
	amount_fields = (
		("Bank Amount", row.get("bank_amount") or row.get("amount")),
		("Suggested Match Amount", row.get("candidate_amount")),
		("Sales Invoice Outstanding", row.get("sales_invoice_outstanding_amount")),
		("Sales Invoice Total", row.get("sales_invoice_grand_total")),
		("Payment Entry Paid Amount", row.get("payment_entry_paid_amount")),
		("Payment Entry Allocated Amount", row.get("payment_entry_allocated_amount")),
		("Payment Row Amount", row.get("payment_row_amount")),
		("Difference / Variance", row.get("amount_difference")),
	)
	for label, value in amount_fields:
		if value not in (None, ""):
			lines.append(f"{label}: {fmt_money(flt(value))}")
	scenario = get_amount_scenario_label(row.get("amount_scenario"))
	category = get_candidate_category_label(row.get("candidate_category"))
	if category:
		lines.append(f"Candidate Category: {category}")
	if row.get("payment_event_source"):
		lines.append(f"Payment Event Source: {row.get('payment_event_source')}")
	if row.get("payment_row_index") not in (None, ""):
		lines.append(f"Payment Row Index: {row.get('payment_row_index')}")
	if row.get("payment_mode"):
		lines.append(f"Mode of Payment: {row.get('payment_mode')}")
	if row.get("payment_account"):
		lines.append(f"Payment Account: {row.get('payment_account')}")
	if scenario:
		lines.append(f"Scenario: {scenario}")
	if row.get("match_confidence"):
		lines.append(f"Match Confidence: {row.get('match_confidence')}")
	if row.get("match_score") not in (None, ""):
		lines.append(f"Match Score: {row.get('match_score')}")
	if row.get("match_reason"):
		lines.append(f"Issue / Reason: {row.get('match_reason')}")
	return "\n".join(lines)


def _get_bulk_confirm_settings():
	try:
		settings = get_retailedge_settings()
	except Exception:
		settings = None
	return {
		"allow_possible": cint(getattr(settings, "allow_bulk_confirm_possible_bank_matches", 0) or 0),
		"min_score": cint(getattr(settings, "bank_match_bulk_confirm_min_score", 80) or 80),
		"amount_tolerance": flt(getattr(settings, "bank_transaction_match_amount_tolerance", 0) or 0),
	}


def _get_bulk_confirm_eligibility(doc):
	return _get_manual_confirm_eligibility(doc)


def _get_manual_confirm_eligibility(doc):
	warnings = []
	status = cstr(getattr(doc, "decision_status", None) or "Draft")
	if status not in {"Suggested", "Needs Review", "Reopened"}:
		category = "already_confirmed" if status == "Confirmed" else "skipped"
		return {"eligible": False, "reason": f"Decision Status is {status}.", "warnings": warnings, "category": category}

	if not cstr(getattr(doc, "bank_transaction", None)).strip():
		return {"eligible": False, "reason": "Bank Transaction does not exist.", "warnings": warnings, "category": "unsafe"}
	if not cstr(getattr(doc, "suggested_document_type", None)).strip() or not cstr(getattr(doc, "suggested_document", None)).strip():
		return {"eligible": False, "reason": NO_MATCH_CANDIDATE_MESSAGE, "warnings": warnings, "category": "unsafe"}
	manual_block_reason = get_review_creation_block_reason({
		"document_type": getattr(doc, "suggested_document_type", None),
		"document_name": getattr(doc, "suggested_document", None),
		"suggested_document_type": getattr(doc, "suggested_document_type", None),
		"suggested_document": getattr(doc, "suggested_document", None),
		"candidate_category": getattr(doc, "candidate_type", None) or getattr(doc, "candidate_category", None),
		"payment_event_found": 1 if cstr(getattr(doc, "payment_event_source", None)).strip() else 0,
		"payment_event_source": getattr(doc, "payment_event_source", None),
	})
	if manual_block_reason:
		return {"eligible": False, "reason": manual_block_reason, "warnings": warnings, "category": "unsafe"}

	try:
		_validate_stored_candidate_for_confirmation(doc)
		_validate_no_other_active_confirmed_match(doc)
	except Exception as exc:
		reason = cstr(exc).strip() or "Manual confirmation blocked by safety validation."
		category = "duplicate_blocked" if "already has a confirmed" in reason or "already confirmed" in reason else "unsafe"
		return {"eligible": False, "reason": reason, "warnings": warnings, "category": category}

	if cint(getattr(doc, "synced_to_sales_invoice", 0) or 0):
		return {"eligible": False, "reason": "This match is already synced to Sales Invoice.", "warnings": warnings, "category": "already_confirmed"}

	confidence = cstr(getattr(doc, "match_confidence", None)).strip()
	if confidence and confidence != "Strong Match":
		warnings.append(f"{confidence} selected for reviewer-authorized manual confirmation.")

	scenario_label = get_amount_scenario_label(getattr(doc, "amount_scenario", None)) or cstr(getattr(doc, "amount_scenario", None)).strip()
	if amount_scenario_requires_manual_review(getattr(doc, "amount_scenario", None)):
		warnings.append((scenario_label or "Manual review scenario") + " requires reviewer judgement.")
	elif _match_reason_mentions_manual_judgement_scenario(getattr(doc, "match_reason", None)):
		warnings.append("This match contains a manual-review payment scenario; reviewer judgement is required.")

	return {"eligible": True, "reason": "Eligible for reviewer-authorized manual confirmation.", "warnings": warnings, "category": "eligible"}


def _match_reason_mentions_manual_judgement_scenario(match_reason):
	text = cstr(match_reason).lower()
	return any(
		phrase in text
		for phrase in (
			"partial payment",
			"overpayment",
			"amount variance",
			"multi-invoice",
			"multi invoice",
		)
	)


def _match_reason_mentions_manual_review_scenario(match_reason):
	text = cstr(match_reason).lower()
	return any(
		phrase in text
		for phrase in (
			"partial payment",
			"overpayment",
			"amount variance",
			"multi-invoice",
			"multi invoice",
			"duplicate candidate",
			"duplicate suspected",
			"date mismatch",
			"period mismatch",
			"account mismatch",
			"exception only",
			"invoice context only",
			"weak invoice total similarity",
			"no matching payment event",
			"paid invoice total similarity only",
		)
	)


def _get_first_active_confirmed_conflict(doc):
	other_bank_match = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"bank_transaction": doc.bank_transaction,
			"decision_status": "Confirmed",
			"name": ["!=", doc.name],
		},
		"name",
	)
	if other_bank_match:
		return f"Bank Transaction already has confirmed match {other_bank_match}."
	if getattr(doc, "sales_invoice", None):
		other_invoice_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"sales_invoice": doc.sales_invoice,
				"decision_status": "Confirmed",
				"name": ["!=", doc.name],
			},
			"name",
		)
		if other_invoice_match:
			return f"Sales Invoice already has confirmed match {other_invoice_match}."
	if getattr(doc, "payment_entry", None):
		other_payment_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"payment_entry": doc.payment_entry,
				"decision_status": "Confirmed",
				"name": ["!=", doc.name],
			},
			"name",
		)
		if other_payment_match:
			return f"Payment Entry already has confirmed match {other_payment_match}."
	return None


def _apply_bank_transaction_match_decision(
	match_name,
	action,
	new_status,
	decision_note=None,
	allowed_current_statuses=None,
	success_message=None,
	details=None,
):
	assert_can_manage_bank_transaction_match()
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to update this match record.", frappe.PermissionError)
	reviewed_candidate = _capture_reviewed_candidate_snapshot(doc)
	old_status = cstr(doc.decision_status or "Draft")
	allowed_current_statuses = allowed_current_statuses or set()
	if old_status not in allowed_current_statuses:
		frappe.throw(f"{action} is not allowed while Decision Status is {old_status}.")

	if new_status == "Confirmed":
		_validate_stored_candidate_for_confirmation(doc)
		_validate_no_other_active_confirmed_match(doc)
		other_confirmed_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": doc.bank_transaction,
				"decision_status": "Confirmed",
				"name": ["!=", doc.name],
			},
			"name",
		)
		if other_confirmed_match:
			frappe.throw(
				f"Bank Transaction {doc.bank_transaction} is already confirmed against RetailEdge match {other_confirmed_match}."
			)

	doc.decision_status = new_status
	doc.decision_note = decision_note
	if not getattr(doc, "flags", None):
		doc.flags = frappe._dict()
	doc.flags.retailedge_preserve_reviewed_candidate = True
	doc.flags.retailedge_reviewed_candidate_snapshot = dict(reviewed_candidate)

	if new_status == "Confirmed":
		doc.confirmed_by = frappe.session.user
		doc.confirmed_on = now_datetime()
	elif new_status == "Rejected":
		doc.rejected_by = frappe.session.user
		doc.rejected_on = now_datetime()
	elif new_status == "Reopened":
		doc.reopened_by = frappe.session.user
		doc.reopened_on = now_datetime()

	append_bank_transaction_match_action_log(
		doc,
		action=action,
		old_status=old_status,
		new_status=new_status,
		remarks=decision_note,
		details={
			"bank_transaction": doc.bank_transaction,
			"suggested_document": doc.suggested_document,
			"suggested_document_type": doc.suggested_document_type,
			"confirmed_payment_entry": doc.payment_entry,
			"candidate_category": getattr(doc, "candidate_type", None),
			"payment_event_source": getattr(doc, "payment_event_source", None),
			"candidate_amount": getattr(doc, "candidate_amount", None),
			**(details or {}),
		},
	)
	_save_match_preserving_selected_candidate(doc)
	_assert_candidate_unchanged_before_confirm(doc, reviewed_candidate)
	return {
		"name": doc.name,
		"decision_status": doc.decision_status,
		"message": success_message or "Decision updated.",
	}


def _validate_no_other_active_confirmed_match(doc):
	if getattr(doc, "sales_invoice", None):
		other_sales_invoice_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"sales_invoice": doc.sales_invoice,
				"decision_status": "Confirmed",
				"name": ["!=", doc.name],
			},
			"name",
		)
		if other_sales_invoice_match or sales_invoice_has_active_confirmed_bank_match(doc.sales_invoice):
			frappe.throw(
				"Sales Invoice already has a confirmed bank match. Reopen, reject, or cancel the existing match before confirming another."
			)

	if getattr(doc, "payment_entry", None):
		other_payment_entry_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"payment_entry": doc.payment_entry,
				"decision_status": "Confirmed",
				"name": ["!=", doc.name],
			},
			"name",
		)
		if other_payment_entry_match or payment_entry_has_active_confirmed_bank_match(doc.payment_entry):
			frappe.throw(
				"Payment Entry already has a confirmed bank match. Reopen, reject, or cancel the existing match before confirming another."
			)


def _capture_reviewed_candidate_snapshot(doc):
	return {
		"bank_transaction": cstr(getattr(doc, "bank_transaction", None)).strip(),
		"suggested_document_type": cstr(getattr(doc, "suggested_document_type", None)).strip(),
		"suggested_document": cstr(getattr(doc, "suggested_document", None)).strip(),
		"sales_invoice": cstr(getattr(doc, "sales_invoice", None)).strip(),
		"payment_entry": cstr(getattr(doc, "payment_entry", None)).strip(),
		"candidate_type": cstr(getattr(doc, "candidate_type", None)).strip(),
		"payment_event_source": cstr(getattr(doc, "payment_event_source", None)).strip(),
		"payment_row_index": cstr(getattr(doc, "payment_row_index", None)).strip(),
		"candidate_amount": flt(getattr(doc, "candidate_amount", None)),
		"candidate_posting_date": cstr(getattr(doc, "candidate_posting_date", None)).strip(),
		"payment_account": cstr(getattr(doc, "payment_account", None)).strip(),
		"resolved_payment_account": cstr(getattr(doc, "resolved_payment_account", None)).strip(),
		"match_confidence": cstr(getattr(doc, "match_confidence", None)).strip(),
		"match_score": cint(getattr(doc, "match_score", None) or 0),
		"match_status": cstr(getattr(doc, "match_status", None)).strip(),
		"amount_scenario": cstr(getattr(doc, "amount_scenario", None)).strip(),
		"match_reason": cstr(getattr(doc, "match_reason", None)).strip(),
		"match_summary": cstr(getattr(doc, "match_summary", None)).strip(),
		"amount_breakdown_summary": cstr(getattr(doc, "amount_breakdown_summary", None)).strip(),
		"match_reason_summary": cstr(getattr(doc, "match_reason_summary", None)).strip(),
	}


def _assert_candidate_unchanged_before_confirm(doc, before_snapshot):
	current_snapshot = _capture_reviewed_candidate_snapshot(doc)
	for fieldname, before_value in before_snapshot.items():
		if current_snapshot.get(fieldname) != before_value:
			frappe.throw(
				"Candidate changed or is no longer eligible. Confirmation was stopped to prevent confirming the wrong payment."
			)


def _stored_candidate_matches_row(doc, row):
	row = frappe._dict(row or {})
	stored = _capture_reviewed_candidate_snapshot(doc)
	expected_payment_entry = cstr(row.get("suggested_document") if row.get("suggested_document_type") == "Payment Entry" else row.get("payment_entry")).strip()
	expected_sales_invoice = cstr(row.get("suggested_document") if row.get("suggested_document_type") == "Sales Invoice" else row.get("suggested_sales_invoice")).strip()
	comparisons = {
		"bank_transaction": cstr(row.get("bank_transaction")).strip(),
		"suggested_document_type": cstr(row.get("suggested_document_type")).strip(),
		"suggested_document": cstr(row.get("suggested_document")).strip(),
		"payment_entry": expected_payment_entry,
		"sales_invoice": expected_sales_invoice,
		"payment_event_source": cstr(row.get("payment_event_source")).strip(),
		"payment_row_index": cstr(row.get("payment_row_index") or row.get("payment_row_reference")).strip(),
	}
	for fieldname, expected in comparisons.items():
		if expected and stored.get(fieldname) != expected:
			return False
	return True


def _build_stored_candidate_for_validation(doc):
	return {
		"document_type": cstr(getattr(doc, "suggested_document_type", None)).strip(),
		"document_name": cstr(getattr(doc, "suggested_document", None)).strip(),
		"posting_date": cstr(getattr(doc, "candidate_posting_date", None)).strip() or None,
		"candidate_category": cstr(getattr(doc, "candidate_type", None)).strip(),
		"payment_event_source": cstr(getattr(doc, "payment_event_source", None)).strip(),
		"candidate_amount": flt(getattr(doc, "candidate_amount", None)),
		"payment_account": cstr(getattr(doc, "resolved_payment_account", None) or getattr(doc, "payment_account", None)).strip() or None,
		"account": cstr(getattr(doc, "resolved_payment_account", None) or getattr(doc, "payment_account", None)).strip() or None,
		"expected_bank_account": cstr(getattr(doc, "resolved_payment_account", None)).strip() or None,
	}


def _build_stored_bank_transaction_for_validation(doc):
	return {
		"bank_transaction": cstr(getattr(doc, "bank_transaction", None)).strip(),
		"company": cstr(getattr(doc, "company", None)).strip() or None,
		"bank_account": cstr(getattr(doc, "bank_account", None)).strip() or None,
		"ledger_account": cstr(getattr(doc, "resolved_bank_account", None)).strip() or None,
		"transaction_date": cstr(getattr(doc, "transaction_date", None)).strip() or None,
	}


def _get_current_best_candidate(doc):
	if not cstr(getattr(doc, "bank_transaction", None)).strip():
		return None
	try:
		return _resolve_matching_candidate(bank_transaction_name=doc.bank_transaction)
	except Exception:
		return None


def _build_confirmation_exception_reason(doc):
	settings = get_bank_transaction_matching_settings()
	reasons = []
	bank_transaction = _build_stored_bank_transaction_for_validation(doc)
	candidate = _build_stored_candidate_for_validation(doc)
	account_payload = _resolve_account_match_payload(bank_transaction, candidate)
	date_window_days = cint(settings.get("date_window_days") or 3)
	bank_date = cstr(bank_transaction.get("transaction_date") or "").strip()
	candidate_date = cstr(candidate.get("posting_date") or "").strip()
	date_gap = _date_difference_days(bank_date, candidate_date)
	amount_scenario = get_amount_scenario_label(getattr(doc, "amount_scenario", None))
	bank_canonical_account = cstr(account_payload.get("bank_canonical_account") or "").strip()
	candidate_canonical_account = cstr(account_payload.get("candidate_canonical_account") or "").strip()
	if not bank_canonical_account:
		reasons.append("Account unresolved: RetailEdge could not resolve the Bank Transaction account to a ledger account.")
	elif not candidate_canonical_account:
		reasons.append("Payment account unresolved: RetailEdge could not resolve the payment account to a ledger account.")
	elif account_payload.get("status") == "mismatch":
		reasons.append(
			f"Account exception: Bank account resolves to {bank_canonical_account or 'unresolved'} but payment account resolves to {candidate_canonical_account or 'unresolved'}."
		)
	if date_gap is not None and date_gap > date_window_days:
		reasons.append(
			f"Date exception: Bank Transaction date is {bank_date} while payment date is {candidate_date}, outside the allowed window of {date_window_days} days."
		)
	elif amount_scenario in {"Date Mismatch", "Period Mismatch", "Date + Account Mismatch", "Date + Account Unresolved", "Exception Only"} and not candidate_date:
		reasons.append(
			f"Date exception: Bank Transaction date is {bank_date or 'unavailable'} while payment date is unavailable, outside the allowed window of {date_window_days} days."
		)
	if reasons:
		reasons.append("Normal confirmation is blocked for date/account exceptions in this phase.")
		return " ".join(reasons)
	return None


def _validate_stored_candidate_for_confirmation(doc):
	if not cstr(getattr(doc, "bank_transaction", None)).strip() or not frappe.db.exists("Bank Transaction", doc.bank_transaction):
		frappe.throw("The reviewed candidate is no longer valid. Please reopen the matching report and create a new review record.")
	if not cstr(getattr(doc, "suggested_document_type", None)).strip() or not cstr(getattr(doc, "suggested_document", None)).strip():
		frappe.throw("The reviewed candidate is no longer valid. Please reopen the matching report and create a new review record.")
	if doc.suggested_document_type not in {"Sales Invoice", "Payment Entry"}:
		frappe.throw("Candidate changed or is no longer eligible. Confirmation was stopped to prevent confirming the wrong payment.")
	if not frappe.db.exists(doc.suggested_document_type, doc.suggested_document):
		frappe.throw("The reviewed candidate is no longer valid. Please reopen the matching report and create a new review record.")
	if doc.suggested_document_type == "Payment Entry":
		docstatus = cint(frappe.db.get_value("Payment Entry", doc.suggested_document, "docstatus") or 0)
		if docstatus != 1:
			frappe.throw("The reviewed candidate is no longer valid. Please reopen the matching report and create a new review record.")
	elif doc.suggested_document_type == "Sales Invoice":
		docstatus = cint(frappe.db.get_value("Sales Invoice", doc.suggested_document, "docstatus") or 0)
		if docstatus != 1:
			frappe.throw("The reviewed candidate is no longer valid. Please reopen the matching report and create a new review record.")
	block_reason = get_review_creation_block_reason(
		{
			"document_type": doc.suggested_document_type,
			"document_name": doc.suggested_document,
			"suggested_document_type": doc.suggested_document_type,
			"suggested_document": doc.suggested_document,
			"candidate_category": getattr(doc, "candidate_type", None),
			"payment_event_found": 1 if cstr(getattr(doc, "payment_event_source", None)).strip() else 0,
			"payment_event_source": getattr(doc, "payment_event_source", None),
		}
	)
	if block_reason:
		frappe.throw("Candidate changed or is no longer eligible. Confirmation was stopped to prevent confirming the wrong payment.")
	exception_reason = _build_confirmation_exception_reason(doc)
	if exception_reason:
		frappe.throw(exception_reason)
	rejected_pair_match = _find_rejected_exact_pair_match(
		bank_transaction=doc.bank_transaction,
		suggested_document_type=doc.suggested_document_type,
		suggested_document=doc.suggested_document,
		payment_event_source=getattr(doc, "payment_event_source", None),
		payment_row_index=getattr(doc, "payment_row_index", None),
	)
	if rejected_pair_match and rejected_pair_match != doc.name:
		frappe.throw("Candidate changed or is no longer eligible. Confirmation was stopped to prevent confirming the wrong payment.")


def _resolve_matching_candidate(
	bank_transaction_name,
	suggested_document_type=None,
	suggested_document=None,
	sales_invoice=None,
	payment_entry=None,
):
	explicit_target = suggested_document or sales_invoice or payment_entry
	explicit_type = suggested_document_type or ("Sales Invoice" if sales_invoice else "Payment Entry" if payment_entry else None)
	search_filters = {"include_exception_candidates": 1} if explicit_target else None
	candidates = find_sales_invoice_candidates_for_bank_transaction(
		bank_transaction_name,
		filters=search_filters,
		limit=20,
	) + find_payment_entry_candidates_for_bank_transaction(
		bank_transaction_name,
		filters=search_filters,
		limit=20,
	)
	candidates.sort(
		key=lambda row: (
			-(
				3
				if get_candidate_category_label(row.get("candidate_category")) == "Payment Entry Match"
				else 2
				if get_candidate_category_label(row.get("candidate_category")) in {"Invoice Payment Row Match", "POS Payment Match"}
				else 1
			),
			-cint(row.get("score") or 0),
			abs(flt(row.get("amount_difference"))),
			cstr(row.get("document_type")),
			cstr(row.get("document_name")),
		)
	)

	if explicit_target:
		for candidate in candidates:
			if cstr(candidate.get("document_name")) == cstr(explicit_target) and (
				not explicit_type or cstr(candidate.get("document_type")) == cstr(explicit_type)
			):
				return candidate

	return candidates[0] if candidates else None


def _ensure_valid_candidate(candidate):
	candidate = frappe._dict(candidate or {})
	if (
		cstr(candidate.get("document_type")).strip() not in {"Sales Invoice", "Payment Entry"}
		or not cstr(candidate.get("document_name")).strip()
	):
		frappe.throw(
			"Cannot create review record because no Sales Invoice, Payment Entry, or payment event candidate was found."
		)
	block_reason = get_review_creation_block_reason(candidate)
	if block_reason and not is_payment_basis_review_candidate(candidate):
		frappe.throw(block_reason)


def _find_existing_match_name(bank_transaction, suggested_document_type=None, suggested_document=None, payment_event_source=None, payment_row_index=None):
	status_filter = ["not in", ["Rejected", "Cancelled", "Reopened"]]
	filters = {"bank_transaction": bank_transaction, "decision_status": status_filter}
	if suggested_document_type:
		filters["suggested_document_type"] = suggested_document_type
	if suggested_document:
		filters["suggested_document"] = suggested_document
	if suggested_document_type == "Sales Invoice" and payment_row_index not in (None, ""):
		filters["payment_row_index"] = payment_row_index
	if suggested_document_type == "Sales Invoice" and cstr(payment_event_source).strip():
		filters["payment_event_source"] = payment_event_source
	name = frappe.db.get_value("RetailEdge Bank Transaction Match", filters, "name")
	if name:
		return name
	if suggested_document:
		sales_invoice_filters = {"bank_transaction": bank_transaction, "sales_invoice": suggested_document, "decision_status": status_filter}
		if suggested_document_type == "Sales Invoice" and payment_row_index not in (None, ""):
			sales_invoice_filters["payment_row_index"] = payment_row_index
		if suggested_document_type == "Sales Invoice" and cstr(payment_event_source).strip():
			sales_invoice_filters["payment_event_source"] = payment_event_source
		return frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			sales_invoice_filters,
			"name",
		) or frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{"bank_transaction": bank_transaction, "payment_entry": suggested_document, "decision_status": status_filter},
			"name",
		)
	return None


def _populate_match_document(doc, bank_transaction, candidate=None, source_report="Bank Transaction Matching"):
	candidate = candidate or {}
	doc.bank_transaction = bank_transaction.get("bank_transaction")
	doc.company = bank_transaction.get("company")
	doc.branch = bank_transaction.get("branch") or candidate.get("branch")
	doc.bank_account = bank_transaction.get("bank_account")
	doc.transaction_date = bank_transaction.get("transaction_date")
	doc.bank_amount = flt(bank_transaction.get("amount"))
	doc.bank_reference = bank_transaction.get("reference")
	doc.bank_narration = bank_transaction.get("description")
	doc.suggested_document_type = candidate.get("document_type")
	doc.suggested_document = candidate.get("document_name")
	doc.sales_invoice = candidate.get("suggested_sales_invoice") if candidate.get("document_type") == "Sales Invoice" else candidate.get("suggested_sales_invoice")
	doc.payment_entry = candidate.get("document_name") if candidate.get("document_type") == "Payment Entry" else None
	doc.customer = candidate.get("customer")
	doc.party_type = candidate.get("party_type") or "Customer"
	doc.party = candidate.get("party") or candidate.get("customer")
	doc.candidate_type = get_candidate_category_label(candidate.get("candidate_category")) or candidate.get("document_type")
	doc.candidate_posting_date = candidate.get("posting_date")
	doc.payment_event_source = candidate.get("payment_event_source")
	doc.payment_row_index = candidate.get("payment_row_index")
	doc.payment_mode = candidate.get("payment_mode")
	doc.payment_account = candidate.get("payment_account")
	doc.resolved_payment_account = candidate.get("resolved_payment_account") or candidate.get("candidate_canonical_account") or candidate.get("account")
	doc.account_resolution_status = candidate.get("account_resolution_status")
	doc.candidate_amount = flt(candidate.get("candidate_amount"))
	doc.amount_difference = flt(doc.bank_amount) - flt(doc.candidate_amount)
	doc.match_confidence = candidate.get("confidence") or "No Match"
	doc.match_score = _normalize_auto_match_score(candidate.get("score"), default=0)
	if hasattr(doc, "amount_scenario"):
		doc.amount_scenario = get_amount_scenario_label(candidate.get("amount_scenario")) or candidate.get("amount_scenario")
	if hasattr(doc, "amount_breakdown_summary"):
		doc.amount_breakdown_summary = _build_amount_breakdown_summary(
			{
				"bank_amount": bank_transaction.get("amount"),
				"candidate_amount": candidate.get("candidate_amount"),
				"amount_difference": flt(bank_transaction.get("amount")) - flt(candidate.get("candidate_amount")),
				"amount_scenario": candidate.get("amount_scenario"),
				"match_confidence": candidate.get("confidence"),
				"match_score": _normalize_auto_match_score(candidate.get("score"), default=0),
				"sales_invoice_outstanding_amount": candidate.get("sales_invoice_outstanding_amount"),
				"sales_invoice_grand_total": candidate.get("sales_invoice_grand_total"),
				"payment_entry_paid_amount": candidate.get("payment_entry_paid_amount"),
				"payment_entry_allocated_amount": candidate.get("payment_entry_allocated_amount"),
				"payment_row_amount": candidate.get("payment_row_amount"),
				"candidate_category": candidate.get("candidate_category"),
				"payment_event_source": candidate.get("payment_event_source"),
				"payment_mode": candidate.get("payment_mode"),
				"payment_account": candidate.get("payment_account"),
				"match_reason": "; ".join(candidate.get("reasons") or []) or candidate.get("reason"),
			}
		)
	context_reasons = list(candidate.get("reasons") or [])
	for fieldname in ("amount_scenario", "payment_entry_invoice_context", "payment_event_source", "payment_row_index", "payment_mode", "payment_account"):
		if candidate.get(fieldname):
			context_reasons.append(f"{fieldname.replace('_', ' ').title()}: {candidate.get(fieldname)}")
	if candidate.get("candidate_category"):
		context_reasons.append(f"Candidate Category: {get_candidate_category_label(candidate.get('candidate_category'))}")
	if candidate.get("multi_invoice_references"):
		context_reasons.append(f"Multi Invoice References: {', '.join(candidate.get('multi_invoice_references') or [])}")
	doc.match_reason = "; ".join(context_reasons) or candidate.get("reason")
	doc.decision_status = doc.decision_status or ("Needs Review" if candidate.get("exception_only") else "Suggested")
	doc.source_report = source_report or doc.source_report or "Bank Transaction Matching"
	doc.details_json = json.dumps(
		{
			"bank_transaction": bank_transaction,
			"candidate": candidate,
		},
		default=str,
		sort_keys=True,
		indent=2,
	)
	if candidate.get("_from_selected_row"):
		if not getattr(doc, "flags", None):
			doc.flags = frappe._dict()
		doc.flags.retailedge_preserve_selected_candidate = True
		doc._retailedge_candidate_context = {
			"details": {
				"candidate_category": candidate.get("candidate_category"),
				"candidate_category_label": get_candidate_category_label(candidate.get("candidate_category")),
				"payment_event_source": candidate.get("payment_event_source"),
				"payment_row_index": candidate.get("payment_row_index"),
				"payment_mode": candidate.get("payment_mode"),
				"payment_account": candidate.get("payment_account"),
				"resolved_payment_account": candidate.get("resolved_payment_account") or candidate.get("candidate_canonical_account") or candidate.get("account"),
				"posting_date": candidate.get("posting_date"),
				"reference": candidate.get("reference"),
				"account_resolution_status": candidate.get("account_resolution_status"),
				"account_resolution_reason": candidate.get("account_resolution_reason"),
				"reasons": list(candidate.get("reasons") or []),
			},
			"candidate": candidate,
		}
