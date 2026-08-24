from __future__ import annotations

from hashlib import sha256
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

DOCTYPE = "RetailEdge Action Follow Up"
MANAGEMENT_FILTER_KEYS = {"follow_up_status", "assignment_scope", "due_scope"}


def action_fingerprint(
	*,
	company: str,
	branch: str,
	source: str,
	kind: str,
	label: str,
	route: str,
	scope: str = "",
) -> str:
	"""Build a stable follow-up identity while preserving all legacy hashes.

	Existing actions hash the original six fields exactly. A provider may opt into
	an additional bounded scope; only then is the seventh field appended.
	"""
	values = [company, branch, source, kind, label, route]
	if str(scope or "").strip():
		values.append(scope)
	payload = "|".join(str(value or "").strip() for value in values)
	return sha256(payload.encode("utf-8")).hexdigest()


def decorate_action_items(items: list[dict[str, Any]], *, company: str, branch: str) -> list[dict[str, Any]]:
	for item in items:
		item["fingerprint"] = action_fingerprint(
			company=company,
			branch=branch,
			source=str(item.get("source") or ""),
			kind=str(item.get("kind") or ""),
			label=str(item.get("label") or ""),
			route=str(item.get("route") or ""),
			scope=str(item.get("fingerprint_scope") or ""),
		)
	if not items or not frappe.db.exists("DocType", DOCTYPE):
		return items
	fingerprints = [item["fingerprint"] for item in items]
	states = frappe.get_list(
		DOCTYPE,
		filters={"fingerprint": ["in", fingerprints]},
		fields=["fingerprint", "status", "assigned_to", "follow_up_on", "snoozed_until", "acknowledged_by", "acknowledged_on", "notes"],
		limit_page_length=len(fingerprints),
	)
	state_by_key = {row.fingerprint: dict(row) for row in states}
	for item in items:
		item["follow_up"] = effective_follow_up_state(
			state_by_key.get(item["fingerprint"]) or {"status": "Open"}
		)
	return items


def effective_follow_up_state(state: dict[str, Any] | None, *, now=None) -> dict[str, Any]:
	result = dict(state or {})
	stored_status = str(result.get("status") or "Open")
	current = get_datetime(now) if now else now_datetime()
	snoozed_until = _as_datetime(result.get("snoozed_until"))
	follow_up_on = _as_datetime(result.get("follow_up_on"))
	snooze_expired = stored_status == "Snoozed" and bool(snoozed_until and snoozed_until <= current)
	effective_status = "Open" if snooze_expired else stored_status
	result["status"] = stored_status
	result["effective_status"] = effective_status
	result["snooze_expired"] = snooze_expired
	result["is_due"] = bool(follow_up_on and follow_up_on <= current and effective_status != "Snoozed")
	return result


def _as_datetime(value):
	if not value:
		return None
	try:
		return get_datetime(value)
	except (TypeError, ValueError):
		return None


def _visibility_filters(filters: dict[str, Any]) -> dict[str, Any]:
	return {key: value for key, value in filters.items() if key not in MANAGEMENT_FILTER_KEYS}


def _action_center_roles() -> set[str]:
	from retailedge.edgesuite_ui import ACTION_CENTER_ROLES

	return set(ACTION_CENTER_ROLES)


def _has_action_center_role(user: str) -> bool:
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)).intersection(_action_center_roles()))


def _has_owner_financial_access(user: str, *, company: str = "", branch: str = "") -> bool:
	"""Return whether a user may view owner-level R9 financial intelligence in this scope."""
	from retailedge.dashboard_capabilities import get_dashboard_capabilities

	if user == "Administrator":
		return True
	try:
		return bool(
			get_dashboard_capabilities(
				"owner-dashboard",
				company=company,
				branch=branch,
				user=user,
			).get("can_view")
		)
	except (frappe.PermissionError, frappe.ValidationError):
		return False


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Restrict direct list/report reads to operational scope and R9 financial entitlement."""
	from retailedge.branch_context import get_user_allowed_branches, user_has_global_branch_access

	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	if not _has_action_center_role(user):
		return "1=0"
	conditions: list[str] = []
	if not _has_owner_financial_access(user):
		conditions.append(f"`tab{DOCTYPE}`.`source` != {frappe.db.escape('r9_early_warning')}")
	if not user_has_global_branch_access(user=user):
		branches = list(get_user_allowed_branches(user=user).get("branches") or [])
		if not branches:
			return "1=0"
		escaped = ", ".join(frappe.db.escape(branch) for branch in branches)
		conditions.append(f"`tab{DOCTYPE}`.`branch` in ({escaped})")
	return " AND ".join(conditions)


def has_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	"""Apply financial, company and branch visibility to direct form access as well as lists."""
	from retailedge.branch_context import user_has_global_branch_access, validate_user_branch_access

	user = user or frappe.session.user
	if user == "Administrator":
		return True
	if not _has_action_center_role(user):
		return False
	company = str(getattr(doc, "company", "") or "").strip()
	branch = str(getattr(doc, "branch", "") or "").strip()
	source = str(getattr(doc, "source", "") or "").strip()
	if company and not frappe.has_permission("Company", "read", doc=company, user=user):
		return False
	if source == "r9_early_warning" and not _has_owner_financial_access(user, company=company, branch=branch):
		return False
	if user_has_global_branch_access(user=user):
		return True
	if not branch:
		return False
	return bool(validate_user_branch_access(branch, user=user, company=company or None, throw=False).get("allowed"))


def _assert_action_center_role(user: str | None = None) -> None:
	user = user or frappe.session.user
	if not _has_action_center_role(user):
		frappe.throw(_("You do not have permission to manage Action Centre follow-ups."), frappe.PermissionError)


def _validate_assignment_user(
	user: str,
	*,
	company: str,
	branch: str,
	require_global_scope: bool = False,
	require_owner_scope: bool = False,
) -> None:
	from retailedge.branch_context import user_has_global_branch_access, validate_user_branch_access

	user = str(user or "").strip()
	if not user:
		return
	if not frappe.db.get_value("User", user, "enabled"):
		frappe.throw(_("Assigned user must be enabled."))
	if not _has_action_center_role(user):
		frappe.throw(_("Assigned user must have access to the RetailEdge Action Centre."), frappe.PermissionError)
	if require_owner_scope and not _has_owner_financial_access(user, company=company, branch=branch):
		frappe.throw(
			_("Business Control financial warnings can only be assigned to users permitted to view owner-level financial intelligence for this scope."),
			frappe.PermissionError,
		)
	if require_global_scope and not user_has_global_branch_access(user=user):
		frappe.throw(
			_("Company-level Business Control warnings can only be assigned to users with global Branch access."),
			frappe.PermissionError,
		)
	if branch:
		allowed = validate_user_branch_access(branch, user=user, company=company, throw=False)
		if not allowed.get("allowed"):
			frappe.throw(_("Assigned user does not have access to this Branch."), frappe.PermissionError)


@frappe.whitelist()
def update_action_follow_up(
	fingerprint: str,
	action: str,
	filters: dict[str, Any] | str | None = None,
	assigned_to: str = "",
	follow_up_on: str = "",
	snoozed_until: str = "",
	notes: str | None = None,
) -> dict[str, Any]:
	from retailedge.business_control_center import get_business_control_center

	_assert_action_center_role()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	payload = get_business_control_center(_visibility_filters(filters))
	visible = next((row for row in payload.get("items") or [] if row.get("fingerprint") == fingerprint), None)
	if not visible:
		frappe.throw(_("This Business Control Centre item is no longer available in your current scope."), frappe.PermissionError)

	action = str(action or "").strip().lower()
	if action not in {"acknowledge", "snooze", "assign", "schedule", "reopen"}:
		frappe.throw(_("Unsupported follow-up action."))
	if not frappe.db.exists("DocType", DOCTYPE):
		frappe.throw(_("Action follow-up storage is not installed yet. Run migrate first."))
	if action == "snooze" and not snoozed_until:
		frappe.throw(_("Snoozed Until is required."))
	if action == "schedule" and not follow_up_on:
		frappe.throw(_("Follow Up On is required."))

	doc = frappe.db.exists(DOCTYPE, fingerprint)
	doc = frappe.get_doc(DOCTYPE, fingerprint) if doc else frappe.new_doc(DOCTYPE)
	if doc.is_new():
		doc.fingerprint = fingerprint
		doc.company = payload["filters"]["company"]
		doc.branch = payload["filters"].get("branch") or ""
		doc.source = visible.get("source")
		doc.kind = visible.get("kind")
		doc.exception_label = visible.get("label")
		doc.route = visible.get("route")
		doc.severity = visible.get("severity")

	now = now_datetime()
	doc.last_seen_on = now
	doc.last_seen_value = str(visible.get("value") if visible.get("value") is not None else "")
	if action == "acknowledge":
		doc.status = "Acknowledged"
		doc.acknowledged_by = frappe.session.user
		doc.acknowledged_on = now
		doc.snoozed_until = None
	elif action == "snooze":
		doc.status = "Snoozed"
		doc.snoozed_until = snoozed_until
	elif action == "reopen":
		doc.status = "Open"
		doc.snoozed_until = None
		doc.acknowledged_by = None
		doc.acknowledged_on = None
	if action == "assign" or assigned_to:
		resolved_assignee = assigned_to or frappe.session.user
		resolved_branch = str(payload["filters"].get("branch") or "")
		is_r9_warning = str(visible.get("source") or "") == "r9_early_warning"
		_validate_assignment_user(
			resolved_assignee,
			company=str(payload["filters"].get("company") or ""),
			branch=resolved_branch,
			require_global_scope=(is_r9_warning and not resolved_branch),
			require_owner_scope=is_r9_warning,
		)
		doc.assigned_to = resolved_assignee
	if follow_up_on:
		doc.follow_up_on = follow_up_on
	if notes is not None:
		doc.notes = notes

	previous_api_write = getattr(frappe.flags, "retailedge_action_follow_up_api_write", False)
	frappe.flags.retailedge_action_follow_up_api_write = True
	try:
		if doc.is_new():
			doc.insert()
		else:
			doc.save()
	finally:
		frappe.flags.retailedge_action_follow_up_api_write = previous_api_write
	return effective_follow_up_state(
		{
			"fingerprint": doc.fingerprint,
			"status": doc.status,
			"assigned_to": doc.assigned_to,
			"follow_up_on": doc.follow_up_on,
			"snoozed_until": doc.snoozed_until,
			"acknowledged_by": doc.acknowledged_by,
			"acknowledged_on": doc.acknowledged_on,
			"notes": doc.notes,
		}
	)
