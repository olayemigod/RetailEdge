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

	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, "read", doc=doc):
		frappe.throw(_("You do not have permission to read this document."), frappe.PermissionError)
	return get_workflow_readiness(doctype=doctype, doc=doc)


def get_workflow_readiness(*, doctype: str, doc=None) -> dict[str, Any]:
	"""Describe workflow readiness without applying any transition.

	Frappe Workflow is checked first. If none is active, a RetailEdge-owned lifecycle
	provider may describe an app-specific review/posting process. This helper is read-only:
	Guided Entry may create a draft, but transitions remain owned by the underlying
	document/workflow and the user's normal permissions.
	"""
	doctype = str(doctype or "").strip()
	workflow = _get_active_workflow(doctype)
	if workflow:
		return _get_frappe_workflow_readiness(workflow=workflow, doc=doc)

	custom = _get_retailedge_workflow_readiness(doctype=doctype, doc=doc)
	if custom:
		return custom

	return {
		"enabled": False,
		"source": "none",
		"workflow": "",
		"state_field": "",
		"current_state": "",
		"docstatus": getattr(doc, "docstatus", 0) if doc is not None else 0,
		"available_actions": [],
		"requires_action": False,
		"message": _("No active workflow is configured. Normal document permissions and submission rules apply."),
	}


def get_doctype_workflow_summary(doctype: str) -> dict[str, Any]:
	"""Cheap workflow metadata for Create menus; does not inspect a document."""
	workflow = _get_active_workflow(doctype)
	if workflow:
		return {
			"enabled": True,
			"source": "frappe",
			"workflow": workflow.get("name") or "",
			"state_field": str(workflow.get("workflow_state_field") or "workflow_state").strip(),
		}
	if doctype == "RetailEdge Cashier Expense":
		return {
			"enabled": True,
			"source": "retailedge",
			"workflow": "RetailEdge Cashier Expense Review",
			"state_field": "expense_status",
		}
	return {"enabled": False, "source": "none", "workflow": "", "state_field": ""}


def _get_frappe_workflow_readiness(*, workflow: dict[str, Any], doc=None) -> dict[str, Any]:
	state_field = str(workflow.get("workflow_state_field") or "workflow_state").strip()
	current_state = ""
	if doc is not None:
		current_state = str(
			getattr(doc, state_field, None) or getattr(doc, "workflow_state", None) or ""
		).strip()

	actions = _get_permitted_transitions(doc) if doc is not None else []
	docstatus = int(getattr(doc, "docstatus", 0) or 0) if doc is not None else 0
	requires_action = bool(docstatus == 0 and workflow)
	if doc is not None and actions:
		message = _(
			"This draft is workflow-controlled. Choose the appropriate workflow action on the document before it can progress."
		)
	elif doc is not None and docstatus == 0:
		message = _(
			"This draft is workflow-controlled. No workflow action is currently available to you; review its state or send it to an authorised user."
		)
	else:
		message = _("This document is controlled by an active workflow.")

	return {
		"enabled": True,
		"source": "frappe",
		"workflow": workflow.get("name") or "",
		"state_field": state_field,
		"current_state": current_state,
		"docstatus": docstatus,
		"available_actions": actions,
		"requires_action": requires_action,
		"message": message,
	}


def _get_retailedge_workflow_readiness(*, doctype: str, doc=None) -> dict[str, Any] | None:
	if doctype != "RetailEdge Cashier Expense":
		return None
	if doc is None:
		return {
			"enabled": True,
			"source": "retailedge",
			"workflow": "RetailEdge Cashier Expense Review",
			"state_field": "expense_status",
			"current_state": "",
			"docstatus": 0,
			"available_actions": [],
			"requires_action": True,
			"message": _("RetailEdge Cashier Expense uses a controlled submit, review, and posting lifecycle."),
		}

	from retailedge.cashier_expense import get_effective_expense_status, user_is_reviewer

	docstatus = int(getattr(doc, "docstatus", 0) or 0)
	state = get_effective_expense_status(doc)
	ledger_status = str(getattr(doc, "ledger_status", None) or "Not Applicable")
	actions: list[dict[str, str]] = []
	requires_action = False

	if docstatus == 0:
		requires_action = True
		if doc.has_permission("submit"):
			actions.append({"action": "Submit", "next_state": "Submitted", "allowed": "submit permission"})
		message = _(
			"This cashier expense is still a draft. It must be submitted before RetailEdge review and ledger posting can proceed."
		)
	elif docstatus == 1 and state == "Submitted":
		requires_action = True
		if user_is_reviewer():
			actions.extend(
			[
				{"action": "Approve", "next_state": "Pending Ledger", "allowed": "RetailEdge reviewer"},
				{"action": "Reject", "next_state": "Rejected", "allowed": "RetailEdge reviewer"},
			]
		)
		message = _(
			"This cashier expense has been submitted and still requires RetailEdge review before ledger posting."
		)
	elif docstatus == 1 and state == "Pending Ledger":
		requires_action = ledger_status != "Posted"
		message = (
			_("This cashier expense is approved and pending ledger posting.")
			if requires_action
			else _("This cashier expense review and ledger posting lifecycle is complete.")
		)
	elif docstatus == 1 and state == "Rejected":
		if user_is_reviewer():
			actions.append({"action": "Reopen", "next_state": "Submitted", "allowed": "RetailEdge reviewer"})
		message = _("This cashier expense was rejected. A reviewer may reopen it when correction is appropriate.")
	else:
		message = _("This cashier expense is controlled by the RetailEdge review lifecycle.")

	return {
		"enabled": True,
		"source": "retailedge",
		"workflow": "RetailEdge Cashier Expense Review",
		"state_field": "expense_status",
		"current_state": state,
		"docstatus": docstatus,
		"available_actions": actions,
		"requires_action": requires_action,
		"ledger_status": ledger_status,
		"message": message,
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
		frappe.throw(
			_(
				"More than one active Workflow is configured for {0}. Resolve the Workflow setup before using Guided Entry."
			).format(doctype)
		)
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
