from __future__ import annotations

from hashlib import sha256
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

DOCTYPE = "RetailEdge Action Follow Up"


def action_fingerprint(*, company: str, branch: str, source: str, kind: str, label: str, route: str) -> str:
	payload = "|".join(str(value or "").strip() for value in (company, branch, source, kind, label, route))
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
		item["follow_up"] = state_by_key.get(item["fingerprint"]) or {"status": "Open"}
	return items


@frappe.whitelist()
def update_action_follow_up(
	fingerprint: str,
	action: str,
	filters: dict[str, Any] | str | None = None,
	assigned_to: str = "",
	follow_up_on: str = "",
	snoozed_until: str = "",
	notes: str = "",
) -> dict[str, Any]:
	from retailedge.action_center import get_action_center_data

	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	payload = get_action_center_data(filters)
	visible = next((row for row in payload.get("items") or [] if row.get("fingerprint") == fingerprint), None)
	if not visible:
		frappe.throw(_("This Action Centre item is no longer available in your current scope."), frappe.PermissionError)

	action = str(action or "").strip().lower()
	if action not in {"acknowledge", "snooze", "assign", "reopen"}:
		frappe.throw(_("Unsupported follow-up action."))
	if not frappe.db.exists("DocType", DOCTYPE):
		frappe.throw(_("Action follow-up storage is not installed yet. Run migrate first."))

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
		if not snoozed_until:
			frappe.throw(_("Snoozed Until is required."))
		doc.status = "Snoozed"
		doc.snoozed_until = snoozed_until
	elif action == "reopen":
		doc.status = "Open"
		doc.snoozed_until = None
		doc.acknowledged_by = None
		doc.acknowledged_on = None
	if action == "assign" or assigned_to:
		doc.assigned_to = assigned_to or frappe.session.user
	if follow_up_on:
		doc.follow_up_on = follow_up_on
	if notes is not None:
		doc.notes = notes

	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return {"fingerprint": doc.fingerprint, "status": doc.status, "assigned_to": doc.assigned_to, "follow_up_on": doc.follow_up_on, "snoozed_until": doc.snoozed_until, "acknowledged_by": doc.acknowledged_by, "acknowledged_on": doc.acknowledged_on, "notes": doc.notes}
