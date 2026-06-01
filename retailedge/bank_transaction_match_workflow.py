from __future__ import annotations

import json

import frappe
from frappe.utils import cint, cstr, flt, fmt_money, now_datetime

from retailedge.bank_transaction_matching import (
	_build_matching_row,
	_derive_action_status,
	_select_candidate_for_queue,
	amount_scenario_requires_manual_review,
	assert_can_access_bank_transaction_matching,
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	get_candidate_category_label,
	get_auto_match_status_for_row,
	get_amount_scenario_label,
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
):
	assert_can_manage_bank_transaction_match()
	assert_can_access_bank_transaction_matching()
	normalized = normalize_bank_transaction(bank_transaction_name)
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
	)
	if existing_name:
		doc = frappe.get_doc("RetailEdge Bank Transaction Match", existing_name)
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
		doc.save(ignore_permissions=True)
	elif force_refresh:
		doc.save(ignore_permissions=True)

	return {
		"name": doc.name,
		"created": created,
		"decision_status": doc.decision_status,
		"bank_transaction": doc.bank_transaction,
		"suggested_document": doc.suggested_document,
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

	revalidation_filters = _coerce_json_payload(filters)
	suggestion_rows = [_revalidate_suggestion_row(row, filters=revalidation_filters) for row in suggestion_rows]
	suggestion_rows, duplicate_candidate_rows = split_duplicate_candidate_suggestions(suggestion_rows)
	filters_payload = _coerce_json_payload(filters)
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

	revalidation_filters = _coerce_json_payload(filters)
	suggestion_rows = [_revalidate_suggestion_row(row, filters=revalidation_filters) for row in suggestion_rows]
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
	return "|".join(
		(
			cstr(row.get("bank_transaction")).strip(),
			cstr(row.get("suggested_document_type")).strip(),
			cstr(row.get("suggested_document")).strip(),
		)
	)


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
	)
	if existing_match:
		return {
			"status": "duplicates",
			"row": _preparation_summary_row(row, reason=f"Review record already exists: {existing_match}.", match_record=existing_match),
		}
	active_candidate_match = _find_active_candidate_review_match(
		suggested_document_type=suggested_document_type,
		suggested_document=suggested_document,
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


def _find_active_candidate_review_match(suggested_document_type, suggested_document):
	if not suggested_document_type or not suggested_document:
		return None
	status_filter = ["not in", ["Rejected", "Cancelled", "Reopened"]]
	name = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"suggested_document_type": suggested_document_type,
			"suggested_document": suggested_document,
			"decision_status": status_filter,
		},
		"name",
	)
	if name:
		return name
	if suggested_document_type == "Sales Invoice":
		return frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{"sales_invoice": suggested_document, "decision_status": status_filter},
			"name",
		)
	if suggested_document_type == "Payment Entry":
		return frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{"payment_entry": suggested_document, "decision_status": status_filter},
			"name",
		)
	return None

def _find_rejected_exact_pair_match(bank_transaction, suggested_document_type, suggested_document):
	if not bank_transaction or not suggested_document_type or not suggested_document:
		return None
	return frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"bank_transaction": bank_transaction,
			"suggested_document_type": suggested_document_type,
			"suggested_document": suggested_document,
			"decision_status": "Rejected",
		},
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
	doc.save(ignore_permissions=True)


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
	doc.save(ignore_permissions=True)


def _auto_confirm_bank_transaction_match(match_name, row, auto_status, settings):
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
	settings = _get_bulk_confirm_settings()
	warnings = []
	if doc.decision_status not in {"Suggested", "Needs Review", "Reopened"}:
		category = "already_confirmed" if doc.decision_status == "Confirmed" else "skipped"
		return {"eligible": False, "reason": f"Decision Status is {doc.decision_status}.", "warnings": warnings, "category": category}
	if doc.match_confidence == "Weak Match":
		return {
			"eligible": False,
			"reason": "Weak Match records are not eligible for bulk confirmation.",
			"warnings": warnings,
			"category": "weak_needs_review",
		}
	if amount_scenario_requires_manual_review(getattr(doc, "amount_scenario", None)):
		return {
			"eligible": False,
			"reason": f"{get_amount_scenario_label(getattr(doc, 'amount_scenario', None))} requires manual review and is blocked from bulk confirm.",
			"warnings": warnings,
			"category": "weak_needs_review",
		}
	candidate_category = get_candidate_category_label(getattr(doc, "candidate_category", None))
	if candidate_category in {"Invoice Context Only", "Weak Invoice Total Similarity"}:
		return {
			"eligible": False,
			"reason": f"{candidate_category} is blocked from bulk confirm until payment-event evidence is available.",
			"warnings": warnings,
			"category": "weak_needs_review",
		}
	if _match_reason_mentions_manual_review_scenario(getattr(doc, "match_reason", None)):
		return {
			"eligible": False,
			"reason": "This match contains a manual-review payment scenario and is blocked from bulk confirm.",
			"warnings": warnings,
			"category": "weak_needs_review",
		}
	if doc.match_confidence == "Possible Match" and not settings["allow_possible"]:
		return {"eligible": False, "reason": "Possible Match records require manual confirmation.", "warnings": warnings, "category": "weak_needs_review"}
	if cint(doc.match_score or 0) < settings["min_score"] and doc.match_confidence != "Strong Match":
		return {"eligible": False, "reason": "Match score is below the bulk confirmation threshold.", "warnings": warnings, "category": "weak_needs_review"}
	if not doc.bank_transaction or not frappe.db.exists("Bank Transaction", doc.bank_transaction):
		return {"eligible": False, "reason": "Bank Transaction does not exist.", "warnings": warnings, "category": "unsafe"}
	if not doc.suggested_document_type or not doc.suggested_document:
		return {"eligible": False, "reason": NO_MATCH_CANDIDATE_MESSAGE, "warnings": warnings, "category": "unsafe"}
	if not frappe.db.exists(doc.suggested_document_type, doc.suggested_document):
		return {
			"eligible": False,
			"reason": f"{doc.suggested_document_type} {doc.suggested_document} does not exist.",
			"warnings": warnings,
			"category": "unsafe",
		}
	if cint(doc.synced_to_sales_invoice or 0):
		return {"eligible": False, "reason": "This match is already synced to Sales Invoice.", "warnings": warnings, "category": "already_confirmed"}
	if abs(flt(doc.amount_difference)) > settings["amount_tolerance"] and doc.match_confidence != "Strong Match":
		return {"eligible": False, "reason": "Amount difference is outside the configured tolerance.", "warnings": warnings, "category": "weak_needs_review"}
	conflict = _get_first_active_confirmed_conflict(doc)
	if conflict:
		return {"eligible": False, "reason": conflict, "warnings": warnings, "category": "duplicate_blocked"}
	if doc.match_confidence == "Possible Match":
		warnings.append("Possible Match selected for bulk confirmation.")
	return {"eligible": True, "reason": "Eligible for bulk confirmation.", "warnings": warnings, "category": "eligible"}


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
	old_status = cstr(doc.decision_status or "Draft")
	allowed_current_statuses = allowed_current_statuses or set()
	if old_status not in allowed_current_statuses:
		frappe.throw(f"{action} is not allowed while Decision Status is {old_status}.")

	if new_status == "Confirmed":
		if get_amount_scenario_label(getattr(doc, "amount_scenario", None)) in {
			"Date Mismatch",
			"Period Mismatch",
			"Account Mismatch",
			"Date + Account Mismatch",
			"Exception Only",
		}:
			frappe.throw(
				"Date/account exception matches cannot be confirmed in this phase. Review the source dates/accounts and use a future authorized exception workflow."
			)
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
			**(details or {}),
		},
	)
	doc.save(ignore_permissions=True)
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


def _find_existing_match_name(bank_transaction, suggested_document_type=None, suggested_document=None):
	filters = {"bank_transaction": bank_transaction}
	if suggested_document_type:
		filters["suggested_document_type"] = suggested_document_type
	if suggested_document:
		filters["suggested_document"] = suggested_document
	name = frappe.db.get_value("RetailEdge Bank Transaction Match", filters, "name")
	if name:
		return name
	if suggested_document:
		return frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{"bank_transaction": bank_transaction, "sales_invoice": suggested_document},
			"name",
		) or frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{"bank_transaction": bank_transaction, "payment_entry": suggested_document},
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
	doc.candidate_amount = flt(candidate.get("candidate_amount"))
	doc.amount_difference = flt(doc.bank_amount) - flt(doc.candidate_amount)
	doc.match_confidence = candidate.get("confidence") or "No Match"
	doc.match_score = cint(candidate.get("score") or 0)
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
				"match_score": candidate.get("score"),
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
