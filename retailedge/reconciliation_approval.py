from __future__ import annotations

import json

import frappe
from frappe.utils import cstr, flt, get_datetime, now_datetime

from retailedge.bank_transaction_matching import assert_can_access_bank_transaction_matching
from retailedge.utils.settings import get_retailedge_settings

APPROVAL_NOT_REQUIRED = "Not Required"
APPROVAL_PENDING = "Pending"
APPROVAL_APPROVED = "Approved"
APPROVAL_DECLINED = "Declined"
APPROVAL_INVALIDATED = "Invalidated"

DEFAULT_APPROVAL_ROLES = (
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
)


def _bool(value, default=False):
	if value in (None, ""):
		return bool(default)
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y"}
	return bool(value)


def _setting(settings, fieldname, default=None):
	if isinstance(settings, dict):
		return settings.get(fieldname, default)
	return getattr(settings, fieldname, default)


def _roles(value):
	if not value:
		return list(DEFAULT_APPROVAL_ROLES)
	if isinstance(value, str):
		items = [cstr(item).strip() for item in value.replace(",", "\n").splitlines()]
		return [item for item in items if item] or list(DEFAULT_APPROVAL_ROLES)
	if isinstance(value, (list, tuple, set)):
		return [cstr(item).strip() for item in value if cstr(item).strip()] or list(DEFAULT_APPROVAL_ROLES)
	return list(DEFAULT_APPROVAL_ROLES)


def _settings_snapshot(settings=None):
	settings = get_retailedge_settings() if settings is None else settings
	return {
		"required": _bool(
			_setting(settings, "require_second_approval_for_reconciliation_execution", None),
			default=True,
		),
		"allowed_roles": _roles(_setting(settings, "allowed_reconciliation_execution_roles", None)),
	}


def _as_match_dict(match_doc):
	if not match_doc:
		return frappe._dict()
	if isinstance(match_doc, dict):
		return frappe._dict(match_doc)
	as_dict = getattr(match_doc, "as_dict", None)
	if callable(as_dict):
		return frappe._dict(as_dict())
	return frappe._dict(match_doc)


def _candidate_identity(match_doc):
	match_doc = _as_match_dict(match_doc)
	identity = {
		"bank_transaction": cstr(match_doc.get("bank_transaction")).strip(),
		"candidate_doctype": cstr(
			match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")
		).strip(),
		"candidate_name": cstr(
			match_doc.get("suggested_document") or match_doc.get("candidate_name")
		).strip(),
		"payment_row_index": cstr(
			match_doc.get("payment_row_index") or match_doc.get("payment_row_reference")
		).strip(),
		"bank_amount": round(flt(match_doc.get("bank_amount") or match_doc.get("bank_transaction_amount")), 6),
		"candidate_amount": round(flt(match_doc.get("candidate_amount")), 6),
		"payment_account": cstr(
			match_doc.get("resolved_payment_account") or match_doc.get("payment_account")
		).strip(),
	}
	return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def _after_confirmation(approved_on, confirmed_on):
	if not approved_on or not confirmed_on:
		return False
	try:
		return get_datetime(approved_on) >= get_datetime(confirmed_on)
	except Exception:
		return False


def _has_allowed_role(user, allowed_roles):
	return bool(set(frappe.get_roles(user) or []).intersection(set(allowed_roles or [])))


def _is_execution_preflight_snapshot(match_doc):
	return bool(
		isinstance(match_doc, dict)
		and cstr(match_doc.get("name")).strip()
		and any(
			fieldname in match_doc
			for fieldname in (
				"execution_bank_transaction",
				"dry_run_status_at_execution",
				"gate_status_at_execution",
			)
		)
	)


def build_reconciliation_approval_state(match_doc, user=None, settings=None):
	# Reconciliation execution passes a rich preflight snapshot here. That snapshot
	# is intentionally rebuilt through a separate safety path and must not become
	# the source of the second-approval fingerprint. Rehydrate the live review
	# DocType so approval creation and approval validation compare like-for-like.
	if _is_execution_preflight_snapshot(match_doc):
		live_doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_doc.get("name"))
		_refresh_match_candidate_context(live_doc)
		match_doc = live_doc

	match_doc = _as_match_dict(match_doc)
	user = user or frappe.session.user
	snapshot = _settings_snapshot(settings)
	current_identity = _candidate_identity(match_doc)
	stored_status = cstr(match_doc.get("approval_status")).strip()
	approved_by = cstr(match_doc.get("approved_by")).strip()
	approved_on = match_doc.get("approved_on")
	confirmed_by = cstr(match_doc.get("confirmed_by")).strip()
	confirmed_on = match_doc.get("confirmed_on")
	stored_identity = cstr(match_doc.get("approval_candidate_identity")).strip()
	decision_status = cstr(match_doc.get("decision_status") or match_doc.get("review_status")).strip()

	if not snapshot["required"]:
		status = APPROVAL_NOT_REQUIRED
		valid = True
		reason = "Second approval is disabled in RetailEdge Settings."
	elif decision_status != "Confirmed":
		status = APPROVAL_INVALIDATED if stored_status == APPROVAL_APPROVED else APPROVAL_PENDING
		valid = False
		reason = "The Bank Match Review must be confirmed before reconciliation approval."
	elif stored_status == APPROVAL_DECLINED:
		status = APPROVAL_DECLINED
		valid = False
		reason = "Reconciliation approval was declined. Review the match before requesting approval again."
	elif (
		stored_status == APPROVAL_APPROVED
		and approved_by
		and approved_by != confirmed_by
		and stored_identity == current_identity
		and _after_confirmation(approved_on, confirmed_on)
	):
		status = APPROVAL_APPROVED
		valid = True
		reason = "Second approval is valid for the current confirmed candidate."
	elif stored_status == APPROVAL_APPROVED:
		status = APPROVAL_INVALIDATED
		valid = False
		reason = "The stored approval no longer matches the latest confirmation or candidate identity."
	else:
		status = APPROVAL_PENDING
		valid = False
		reason = "Second approval is required before reconciliation execution."

	can_approve = bool(
		snapshot["required"]
		and decision_status == "Confirmed"
		and status != APPROVAL_APPROVED
		and user
		and user != confirmed_by
		and _has_allowed_role(user, snapshot["allowed_roles"])
	)
	return {
		"required": snapshot["required"],
		"status": status,
		"stored_status": stored_status or APPROVAL_PENDING,
		"is_satisfied": bool(valid),
		"reason": reason,
		"confirmed_by": confirmed_by,
		"confirmed_on": confirmed_on,
		"requested_by": match_doc.get("approval_requested_by"),
		"requested_on": match_doc.get("approval_requested_on"),
		"approved_by": approved_by,
		"approved_on": approved_on,
		"approval_note": match_doc.get("approval_note"),
		"candidate_identity": current_identity,
		"can_approve": can_approve,
		"same_user_blocked": bool(snapshot["required"] and user and user == confirmed_by),
		"allowed_roles": snapshot["allowed_roles"],
	}


def _load_match(match_name):
	fields = [
		"name",
		"bank_transaction",
		"suggested_document_type",
		"suggested_document",
		"payment_row_index",
		"bank_amount",
		"candidate_amount",
		"payment_account",
		"resolved_payment_account",
		"decision_status",
		"review_status",
		"confirmed_by",
		"confirmed_on",
		"approval_status",
		"approval_requested_by",
		"approval_requested_on",
		"approved_by",
		"approved_on",
		"approval_note",
		"approval_candidate_identity",
		"execution_status",
	]
	return frappe._dict(
		frappe.db.get_value("RetailEdge Bank Transaction Match", match_name, fields, as_dict=True) or {}
	)


def _append_action(doc, action, remarks=None, details=None):
	now = now_datetime()
	if hasattr(doc, "append") and hasattr(doc, "action_logs"):
		doc.append(
			"action_logs",
			{
				"action": action,
				"action_by": frappe.session.user,
				"action_on": now,
				"old_status": getattr(doc, "decision_status", None),
				"new_status": getattr(doc, "decision_status", None),
				"remarks": remarks,
				"details_json": json.dumps(details or {}, default=str, sort_keys=True, indent=2),
			},
		)
	if hasattr(doc, "last_action"):
		doc.last_action = action
	if hasattr(doc, "last_action_by"):
		doc.last_action_by = frappe.session.user
	if hasattr(doc, "last_action_on"):
		doc.last_action_on = now


def _assert_writeable(doc):
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to update this Bank Match Review.", frappe.PermissionError)


def _refresh_match_candidate_context(doc):
	"""Refresh live candidate evidence before binding or checking an approval identity.

	Older review rows can carry candidate-account context written by an earlier
	resolver. The DocType validator rehydrates that context from the submitted
	source document. Approval creation and approval-gate validation must use this
	same live hydration path; reconciliation preflight remains an independent
	safety check and must not be used as the approval fingerprint source.
	"""
	validator = getattr(doc, "validate", None)
	if callable(validator):
		validator()
	return doc


def build_live_reconciliation_approval_state(match_name, user=None, settings=None):
	"""Build approval state from the same live DocType context used at approval time."""
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	_refresh_match_candidate_context(doc)
	return build_reconciliation_approval_state(doc, user=user, settings=settings)


@frappe.whitelist()
def get_reconciliation_approval_state(match_name, user=None):
	assert_can_access_bank_transaction_matching(user=user)
	return build_live_reconciliation_approval_state(match_name, user=user)


@frappe.whitelist()
def request_reconciliation_approval(match_name, approval_note=None):
	assert_can_access_bank_transaction_matching()
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	_assert_writeable(doc)
	if cstr(doc.decision_status).strip() != "Confirmed":
		frappe.throw("Confirm the Bank Match Review before requesting reconciliation approval.")
	if cstr(getattr(doc, "execution_status", None)).strip() in {"Executed", "Already Handled"}:
		frappe.throw("This reconciliation has already been handled.")
	_refresh_match_candidate_context(doc)
	state = build_reconciliation_approval_state(doc)
	if not state["required"]:
		return {**state, "message": "Second approval is not required by RetailEdge Settings."}

	now = now_datetime()
	doc.approval_status = APPROVAL_PENDING
	doc.approval_requested_by = frappe.session.user
	doc.approval_requested_on = now
	doc.approved_by = None
	doc.approved_on = None
	doc.approval_note = approval_note
	doc.approval_candidate_identity = state["candidate_identity"]
	_append_action(
		doc,
		"Reconciliation Approval Requested",
		remarks=approval_note or "Second approval requested before reconciliation execution.",
		details={"candidate_identity": state["candidate_identity"]},
	)
	doc.save(ignore_permissions=True)
	return {
		**build_reconciliation_approval_state(doc),
		"message": "Second approval requested. A different authorised user must approve before reconciliation.",
	}


@frappe.whitelist()
def approve_reconciliation_for_match(match_name, approval_note=None):
	assert_can_access_bank_transaction_matching()
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	_assert_writeable(doc)
	if cstr(doc.decision_status).strip() != "Confirmed":
		frappe.throw("Only a confirmed Bank Match Review can receive reconciliation approval.")
	if cstr(getattr(doc, "execution_status", None)).strip() in {"Executed", "Already Handled"}:
		frappe.throw("This reconciliation has already been handled.")

	settings = _settings_snapshot()
	if not settings["required"]:
		return {
			**build_reconciliation_approval_state(doc),
			"message": "Second approval is not required by RetailEdge Settings.",
		}
	if frappe.session.user == cstr(getattr(doc, "confirmed_by", None)).strip():
		frappe.throw(
			"The user who confirmed the match cannot provide the second reconciliation approval.",
			frappe.PermissionError,
		)
	if not _has_allowed_role(frappe.session.user, settings["allowed_roles"]):
		frappe.throw(
			"You do not have an allowed role for reconciliation approval.",
			frappe.PermissionError,
		)

	_refresh_match_candidate_context(doc)

	# Import lazily to avoid a module cycle: reconciliation_bridge imports approval-state helpers.
	from retailedge.reconciliation_bridge import build_reconciliation_readiness_result, _load_match_for_preflight

	readiness = build_reconciliation_readiness_result(_load_match_for_preflight(match_name))
	if cstr(readiness.get("readiness_group")).strip() != "Ready":
		frappe.throw(
			readiness.get("block_reason")
			or "This match is not currently ready for reconciliation approval."
		)

	now = now_datetime()
	identity = _candidate_identity(doc)
	doc.approval_status = APPROVAL_APPROVED
	doc.approved_by = frappe.session.user
	doc.approved_on = now
	doc.approval_note = approval_note
	doc.approval_candidate_identity = identity
	_append_action(
		doc,
		"Reconciliation Approved",
		remarks=approval_note or "Second approval granted for the current confirmed candidate.",
		details={"candidate_identity": identity, "readiness_group": readiness.get("readiness_group")},
	)
	doc.save(ignore_permissions=True)
	return {
		**build_reconciliation_approval_state(doc),
		"message": "Reconciliation approved. A fresh safety check will still run before ERPNext reconciliation executes.",
	}


@frappe.whitelist()
def decline_reconciliation_for_match(match_name, approval_note=None):
	assert_can_access_bank_transaction_matching()
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	_assert_writeable(doc)
	if cstr(doc.decision_status).strip() != "Confirmed":
		frappe.throw("Only a confirmed Bank Match Review can receive a reconciliation approval decision.")
	settings = _settings_snapshot()
	if frappe.session.user == cstr(getattr(doc, "confirmed_by", None)).strip():
		frappe.throw(
			"The user who confirmed the match cannot provide the second reconciliation approval decision.",
			frappe.PermissionError,
		)
	if not _has_allowed_role(frappe.session.user, settings["allowed_roles"]):
		frappe.throw(
			"You do not have an allowed role for reconciliation approval.",
			frappe.PermissionError,
		)

	_refresh_match_candidate_context(doc)
	identity = _candidate_identity(doc)
	doc.approval_status = APPROVAL_DECLINED
	doc.approved_by = None
	doc.approved_on = None
	doc.approval_note = approval_note
	doc.approval_candidate_identity = identity
	_append_action(
		doc,
		"Reconciliation Approval Declined",
		remarks=approval_note or "Second approval declined; review the match before retrying.",
		details={"candidate_identity": identity},
	)
	doc.save(ignore_permissions=True)
	return {
		**build_reconciliation_approval_state(doc),
		"message": "Reconciliation approval declined. No accounting action was performed.",
	}
