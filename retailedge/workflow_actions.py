from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import get_datetime

from retailedge.cashier_expense import (
	approve_cashier_expense,
	reject_cashier_expense,
	reopen_cashier_expense,
	submit_cashier_expense,
)
from retailedge.workflow_readiness import (
	_get_active_workflow,
	_retailedge_cashier_workflow_enabled,
	get_workflow_readiness,
)

CASHIER_EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
_CASHIER_ACTIONS = {"Submit", "Approve", "Reject", "Reopen"}


@frappe.whitelist(methods=["POST"])
def apply_document_workflow_action(
	doctype: str,
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_state: str | None = None,
	remarks: str | None = None,
) -> dict[str, Any]:
	"""Apply one EdgeSuite workflow action through the authoritative workflow engine.

	Active Frappe Workflow always wins. A RetailEdge-owned lifecycle is consulted only
	when no active Frappe Workflow exists for the document type. The endpoint never
	assigns workflow state or docstatus directly.
	"""
	doctype = str(doctype or "").strip()
	name = str(name or "").strip()
	action = str(action or "").strip()
	if not doctype or not name or not action:
		frappe.throw(_("Document Type, document name and workflow action are required."))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("Document Type {0} does not exist.").format(doctype))

	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, "read", doc=doc):
		frappe.throw(_("You do not have permission to read this document."), frappe.PermissionError)

	_assert_expected_snapshot(
		doc,
		expected_modified=expected_modified,
		expected_state=expected_state,
	)

	workflow = _get_active_workflow(doctype)
	if workflow:
		return _apply_frappe_workflow(
			doc=doc,
			workflow=workflow,
			action=action,
		)

	if doctype == CASHIER_EXPENSE_DOCTYPE and _retailedge_cashier_workflow_enabled():
		return _apply_cashier_expense_lifecycle(
			doc=doc,
			action=action,
			remarks=remarks,
		)

	frappe.throw(
		_("No active workflow-controlled transition is configured for {0}.").format(doctype),
		frappe.ValidationError,
	)


def _apply_frappe_workflow(*, doc, workflow: dict[str, Any], action: str) -> dict[str, Any]:
	readiness = get_workflow_readiness(doctype=doc.doctype, doc=doc)
	available = {
		str(row.get("action") or "").strip()
		for row in readiness.get("available_actions") or []
		if str(row.get("action") or "").strip()
	}
	if action not in available:
		frappe.throw(
			_("Workflow action {0} is not currently available for this document.").format(action),
			frappe.PermissionError,
		)

	result = apply_workflow(doc, action)
	queued = result is None
	current = result
	if current is None:
		try:
			current = frappe.get_doc(doc.doctype, doc.name)
		except Exception:
			current = doc

	return _result_payload(
		current,
		queued=queued,
		workflow_name=str(workflow.get("name") or ""),
	)


def _apply_cashier_expense_lifecycle(*, doc, action: str, remarks: str | None) -> dict[str, Any]:
	if action not in _CASHIER_ACTIONS:
		frappe.throw(_("Unsupported Cashier Expense workflow action."), frappe.ValidationError)

	readiness = get_workflow_readiness(doctype=doc.doctype, doc=doc)
	available = {
		str(row.get("action") or "").strip()
		for row in readiness.get("available_actions") or []
		if str(row.get("action") or "").strip()
	}
	if action not in available:
		frappe.throw(
			_("Cashier Expense action {0} is not currently available.").format(action),
			frappe.PermissionError,
		)
	if action == "Reject" and not str(remarks or "").strip():
		frappe.throw(_("Remarks are required when rejecting a Cashier Expense."))

	if action == "Submit":
		submit_cashier_expense(doc.name)
	elif action == "Approve":
		approve_cashier_expense(doc.name, remarks=remarks)
	elif action == "Reject":
		reject_cashier_expense(doc.name, remarks=remarks)
	elif action == "Reopen":
		reopen_cashier_expense(doc.name, remarks=remarks)

	current = frappe.get_doc(doc.doctype, doc.name)
	return _result_payload(
		current,
		queued=False,
		workflow_name="RetailEdge Cashier Expense Review",
	)


def _assert_expected_snapshot(
	doc,
	*,
	expected_modified: str | None,
	expected_state: str | None,
) -> None:
	if expected_modified:
		try:
			expected_dt = get_datetime(expected_modified)
			current_dt = get_datetime(doc.modified)
		except Exception:
			frappe.throw(_("Invalid workflow document version."), frappe.ValidationError)
		if expected_dt != current_dt:
			frappe.throw(
				_(
					"This document changed after it was loaded. Refresh the EdgeSuite page before applying a workflow action."
				),
				frappe.TimestampMismatchError,
			)

	if expected_state is not None:
		readiness = get_workflow_readiness(doctype=doc.doctype, doc=doc)
		current_state = str(readiness.get("current_state") or "").strip()
		if current_state != str(expected_state or "").strip():
			frappe.throw(
				_(
					"This document is no longer in the expected workflow state. Refresh before continuing."
				),
				frappe.ValidationError,
			)


def _result_payload(doc, *, queued: bool, workflow_name: str) -> dict[str, Any]:
	readiness = get_workflow_readiness(doctype=doc.doctype, doc=doc)
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": str(getattr(doc, "modified", "") or ""),
		"docstatus": int(getattr(doc, "docstatus", 0) or 0),
		"queued": bool(queued),
		"workflow": workflow_name,
		"workflow_readiness": readiness,
	}
