from __future__ import annotations

from typing import Any

import frappe
from frappe import _


@frappe.whitelist()
def get_document_workflow_readiness(doctype: str, name: str) -> dict[str, Any]:
	"""Return workflow state and currently permitted next actions for one readable document."""
	doctype = str(doctype or "").strip()
	name = str(name or "").strip()
	if not doctype or not name:
		frappe.throw(_("Document Type and document name are required."))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("Document Type {0} does not exist.").format(doctype))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to read this document."), frappe.PermissionError)

	doc = frappe.get_doc(doctype, name)
	return get_workflow_readiness(doctype=doctype, doc=doc)


def get_workflow_readiness(*, doctype: str, doc=None) -> dict[str, Any]:
	"""Describe active Workflow readiness without applying any transition.

	This helper is intentionally read-only. Guided Entry may create a draft, but workflow
	transitions remain owned by Frappe/ERPNext and the user's normal workflow permissions.
	"""
	doctype = str(doctype or "").strip()
	workflow = _get_active_workflow(doctype)
	if not workflow:
		return {
			"enabled": False,
			"workflow": "",
			"state_field": "",
			"current_state": "",
			"docstatus": getattr(doc, "docstatus", 0) if doc is not None else 0,
			"available_actions": [],
			"requires_action": False,
			"message": _("No active workflow is configured. Normal document permissions and submission rules apply."),
		}

	state_field = str(workflow.get("workflow_state_field") or "workflow_state").strip()
	current_state = ""
	if doc is not None:
		current_state = str(getattr(doc, state_field, None) or getattr(doc, "workflow_state", None) or "").strip()

	actions = _get_permitted_transitions(doc) if doc is not None else []
	docstatus = int(getattr(doc, "docstatus", 0) or 0) if doc is not None else 0
	requires_action = bool(docstatus == 0 and workflow)
	if doc is not None and actions:
		message = _("This draft is workflow-controlled. Choose the appropriate workflow action on the document before it can progress.")
	elif doc is not None and docstatus == 0:
		message = _("This draft is workflow-controlled. No workflow action is currently available to you; review its state or send it to an authorised user.")
	else:
		message = _("This document is controlled by an active workflow.")

	return {
		"enabled": True,
		"workflow": workflow.get("name") or "",
		"state_field": state_field,
		"current_state": current_state,
		"docstatus": docstatus,
		"available_actions": actions,
		"requires_action": requires_action,
		"message": message,
	}


def get_doctype_workflow_summary(doctype: str) -> dict[str, Any]:
	"""Cheap workflow metadata for Create menus; does not inspect a document."""
	workflow = _get_active_workflow(doctype)
	if not workflow:
		return {"enabled": False, "workflow": "", "state_field": ""}
	return {
		"enabled": True,
		"workflow": workflow.get("name") or "",
		"state_field": str(workflow.get("workflow_state_field") or "workflow_state").strip(),
	}


def _get_active_workflow(doctype: str) -> dict[str, Any] | None:
	if not doctype or not frappe.db.exists("DocType", "Workflow"):
		return None
	rows = frappe.get_all(
		"Workflow",
		filters={"document_type": doctype, "is_active": 1},
		fields=["name", "document_type", "workflow_state_field"],
		limit=2,
	)
	if not rows:
		return None
	# Frappe allows only one active workflow per DocType. If legacy data violates that,
	# do not choose silently; surface the governance problem instead.
	if len(rows) > 1:
		frappe.throw(_("More than one active Workflow is configured for {0}. Resolve the Workflow setup before using Guided Entry.").format(doctype))
	return rows[0]


def _get_permitted_transitions(doc) -> list[dict[str, str]]:
	try:
		from frappe.model.workflow import get_transitions

		transitions = get_transitions(doc) or []
	except (frappe.PermissionError, frappe.ValidationError):
		return []
	except Exception:
		# Workflow introspection must never block opening a saved draft. Frappe remains
		# authoritative when the user opens the document and attempts a transition.
		return []

	result: list[dict[str, str]] = []
	for transition in transitions:
		action = str(transition.get("action") or "").strip()
		if not action:
			continue
		result.append(
			{
				"action": action,
				"next_state": str(transition.get("next_state") or "").strip(),
				"allowed": str(transition.get("allowed") or "").strip(),
			}
		)
	return result
