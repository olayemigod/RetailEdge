from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge import workflow_actions


class _Doc(SimpleNamespace):
	def __init__(self, **values):
		super().__init__(**values)
		self.doctype = values.get("doctype", "Sales Invoice")
		self.name = values.get("name", "TEST-1")
		self.modified = values.get("modified", "2026-09-10 12:00:00")
		self.docstatus = values.get("docstatus", 0)


@patch.object(workflow_actions.frappe.db, "exists", return_value=True)
@patch.object(workflow_actions.frappe, "has_permission", return_value=True)
def test_active_frappe_workflow_has_precedence_and_uses_framework_apply(
	_mock_permission,
	_mock_exists,
):
	doc = _Doc(workflow_state="Draft")
	result_doc = _Doc(workflow_state="Pending Approval", modified="2026-09-10 12:01:00")
	with (
		patch.object(workflow_actions.frappe, "get_doc", return_value=doc),
		patch.object(
			workflow_actions,
			"_get_active_workflow",
			return_value={"name": "Sales Approval", "workflow_state_field": "workflow_state"},
		),
		patch.object(
			workflow_actions,
			"get_workflow_readiness",
			side_effect=[
				{
					"current_state": "Draft",
					"available_actions": [
						{"action": "Send for Approval", "next_state": "Pending Approval"}
					],
				},
				{
					"current_state": "Pending Approval",
					"available_actions": [],
				},
			],
		),
		patch.object(workflow_actions, "apply_workflow", return_value=result_doc) as apply_action,
	):
		result = workflow_actions.apply_document_workflow_action(
			"Sales Invoice",
			"TEST-1",
			"Send for Approval",
		)

	apply_action.assert_called_once_with(doc, "Send for Approval")
	assert result["workflow"] == "Sales Approval"
	assert result["workflow_readiness"]["current_state"] == "Pending Approval"


@patch.object(workflow_actions.frappe.db, "exists", return_value=True)
@patch.object(workflow_actions.frappe, "has_permission", return_value=True)
def test_frappe_action_not_in_live_transition_set_fails_closed(
	_mock_permission,
	_mock_exists,
):
	doc = _Doc(workflow_state="Pending Manager")
	with (
		patch.object(workflow_actions.frappe, "get_doc", return_value=doc),
		patch.object(
			workflow_actions,
			"_get_active_workflow",
			return_value={"name": "Approval", "workflow_state_field": "workflow_state"},
		),
		patch.object(
			workflow_actions,
			"get_workflow_readiness",
			return_value={"current_state": "Pending Manager", "available_actions": []},
		),
		patch.object(workflow_actions.frappe, "throw", side_effect=frappe.PermissionError),
		patch.object(workflow_actions, "apply_workflow") as apply_action,
	):
		try:
			workflow_actions.apply_document_workflow_action(
				"Sales Invoice", "TEST-1", "Approve"
			)
		except frappe.PermissionError:
			pass
		else:
			raise AssertionError("Expected unavailable workflow action to fail")
	apply_action.assert_not_called()


@patch.object(workflow_actions.frappe.db, "exists", return_value=True)
@patch.object(workflow_actions.frappe, "has_permission", return_value=True)
def test_cashier_lifecycle_is_used_only_without_frappe_workflow(
	_mock_permission,
	_mock_exists,
):
	doc = _Doc(
		doctype="RetailEdge Cashier Expense",
		expense_status="Draft",
		ledger_status="Not Applicable",
	)
	updated = _Doc(
		doctype="RetailEdge Cashier Expense",
		expense_status="Submitted",
		ledger_status="Not Applicable",
		docstatus=1,
		modified="2026-09-10 12:01:00",
	)
	with (
		patch.object(workflow_actions.frappe, "get_doc", side_effect=[doc, updated]),
		patch.object(workflow_actions, "_get_active_workflow", return_value=None),
		patch.object(workflow_actions, "_retailedge_cashier_workflow_enabled", return_value=True),
		patch.object(
			workflow_actions,
			"get_workflow_readiness",
			side_effect=[
				{
					"current_state": "Draft",
					"available_actions": [{"action": "Submit"}],
				},
				{
					"current_state": "Submitted",
					"available_actions": [],
				},
			],
		),
		patch.object(workflow_actions, "submit_cashier_expense") as submit,
	):
		result = workflow_actions.apply_document_workflow_action(
			"RetailEdge Cashier Expense",
			"CE-1",
			"Submit",
		)

	submit.assert_called_once_with("CE-1")
	assert result["workflow"] == "RetailEdge Cashier Expense Review"


@patch.object(workflow_actions.frappe.db, "exists", return_value=True)
@patch.object(workflow_actions.frappe, "has_permission", return_value=True)
def test_stale_modified_snapshot_fails_before_transition(
	_mock_permission,
	_mock_exists,
):
	doc = _Doc(modified="2026-09-10 12:00:00")
	with (
		patch.object(workflow_actions.frappe, "get_doc", return_value=doc),
		patch.object(workflow_actions, "_get_active_workflow", return_value={"name": "Approval"}),
		patch.object(workflow_actions.frappe, "throw", side_effect=frappe.TimestampMismatchError),
		patch.object(workflow_actions, "apply_workflow") as apply_action,
	):
		try:
			workflow_actions.apply_document_workflow_action(
				"Sales Invoice",
				"TEST-1",
				"Approve",
				expected_modified="2026-09-10 11:59:00",
			)
		except frappe.TimestampMismatchError:
			pass
		else:
			raise AssertionError("Expected stale workflow snapshot to fail")
	apply_action.assert_not_called()


def test_workflow_action_module_has_no_direct_state_or_docstatus_mutation():
	source = open(workflow_actions.__file__, encoding="utf-8").read()
	assert ".docstatus =" not in source
	assert ".workflow_state =" not in source
	assert "frappe.db.commit" not in source
	assert "ignore_permissions" not in source
