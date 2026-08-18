from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.workflow_readiness import get_workflow_readiness


class TestWorkflowReadiness(unittest.TestCase):
	@patch("retailedge.workflow_readiness._get_active_workflow", return_value=None)
	def test_no_active_workflow_uses_normal_document_rules(self, _mock_workflow):
		doc = SimpleNamespace(docstatus=0)
		result = get_workflow_readiness(doctype="Sales Invoice", doc=doc)

		self.assertFalse(result["enabled"])
		self.assertFalse(result["requires_action"])
		self.assertEqual(result["available_actions"], [])

	@patch(
		"retailedge.workflow_readiness._get_permitted_transitions",
		return_value=[{"action": "Send for Approval", "next_state": "Pending Approval", "allowed": "Sales User"}],
	)
	@patch(
		"retailedge.workflow_readiness._get_active_workflow",
		return_value={"name": "Sales Invoice Approval", "workflow_state_field": "workflow_state"},
	)
	def test_active_workflow_reports_state_and_only_permitted_next_actions(
		self, _mock_workflow, _mock_transitions
	):
		doc = SimpleNamespace(docstatus=0, workflow_state="Draft")
		result = get_workflow_readiness(doctype="Sales Invoice", doc=doc)

		self.assertTrue(result["enabled"])
		self.assertTrue(result["requires_action"])
		self.assertEqual(result["workflow"], "Sales Invoice Approval")
		self.assertEqual(result["current_state"], "Draft")
		self.assertEqual(result["available_actions"][0]["action"], "Send for Approval")
		self.assertIn("workflow-controlled", result["message"])

	@patch("retailedge.workflow_readiness._get_permitted_transitions", return_value=[])
	@patch(
		"retailedge.workflow_readiness._get_active_workflow",
		return_value={"name": "Purchase Approval", "workflow_state_field": "approval_state"},
	)
	def test_active_workflow_without_user_transition_does_not_claim_completion(
		self, _mock_workflow, _mock_transitions
	):
		doc = SimpleNamespace(docstatus=0, approval_state="Pending Manager")
		result = get_workflow_readiness(doctype="Purchase Invoice", doc=doc)

		self.assertTrue(result["requires_action"])
		self.assertEqual(result["available_actions"], [])
		self.assertIn("authorised user", result["message"])

	@patch("retailedge.workflow_readiness.frappe.get_all")
	@patch("retailedge.workflow_readiness.frappe.db.exists", return_value=True)
	def test_duplicate_active_workflows_are_rejected_instead_of_selected_silently(
		self, _mock_exists, mock_get_all
	):
		mock_get_all.return_value = [
			{"name": "Workflow A", "workflow_state_field": "workflow_state"},
			{"name": "Workflow B", "workflow_state_field": "workflow_state"},
		]

		with self.assertRaises(frappe.ValidationError):
			get_workflow_readiness(doctype="Stock Entry", doc=SimpleNamespace(docstatus=0))


if __name__ == "__main__":
	unittest.main()
