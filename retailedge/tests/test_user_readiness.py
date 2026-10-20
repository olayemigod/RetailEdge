from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import operating_context, user_readiness

USER = "cashier@example.com"
COMPANY = "RetailEdge Consulting"
BRANCH = "Ketu"
APP_ROOT = Path(__file__).resolve().parents[1]
BRANCH_ASSIGNMENTS_VUE = APP_ROOT / "public" / "js" / "branch_assignments" / "BranchAssignments.vue"
NAVIGATION = APP_ROOT / "navigation_consolidation.py"


def user_values():
	return frappe._dict(enabled=1, user_type="System User", full_name="QA Cashier")


def assignment(*, company=COMPANY, branch=BRANCH, is_primary=1):
	return frappe._dict(
		name="RE-BA-2026-00001",
		user=USER,
		company=company,
		branch=branch,
		branch_setup="RE-BP-00001",
		branch_role="Cashier",
		is_primary=is_primary,
		effective_from="2026-10-01",
		effective_to=None,
	)


class TestUserReadiness(unittest.TestCase):
	@patch("retailedge.user_readiness.frappe.get_roles", return_value=["RetailEdgeCashier"])
	@patch("retailedge.user_readiness.get_active_branch_assignments", return_value=[])
	@patch("retailedge.user_readiness.frappe.db.get_value", return_value=user_values())
	def test_retailedge_user_without_active_assignment_fails_closed(self, _get_value, _assignments, _roles):
		result = user_readiness.get_retailedge_user_readiness(user=USER, company=COMPANY)
		self.assertTrue(result["applicable"])
		self.assertFalse(result["ready"])
		self.assertEqual(result["status"], "Setup incomplete")
		self.assertEqual(result["reasons"][0]["code"], "missing_company_assignment")
		self.assertIn("Assign this User", result["message"])

	@patch("retailedge.user_readiness.frappe.get_roles", return_value=["RetailEdgeCashier"])
	@patch("retailedge.user_readiness.get_active_branch_assignments", return_value=[])
	@patch("retailedge.user_readiness.frappe.db.get_value", return_value=user_values())
	def test_expired_history_does_not_satisfy_readiness(self, _get_value, _assignments, _roles):
		result = user_readiness.get_retailedge_user_readiness(user=USER)
		self.assertFalse(result["ready"])
		self.assertEqual(result["reasons"][0]["code"], "missing_branch_assignment")

	@patch("retailedge.user_readiness.frappe.get_roles", return_value=["RetailEdgeCashier"])
	@patch(
		"retailedge.user_readiness.get_active_branch_assignments",
		return_value=[assignment(company="Another Company", branch="Another Branch")],
	)
	@patch("retailedge.user_readiness.frappe.db.get_value", return_value=user_values())
	def test_assignment_in_other_company_does_not_satisfy_selected_company(
		self, _get_value, _assignments, _roles
	):
		result = user_readiness.get_retailedge_user_readiness(user=USER, company=COMPANY)
		self.assertFalse(result["ready"])
		self.assertEqual(result["reasons"][0]["code"], "missing_company_assignment")

	@patch("retailedge.user_readiness._validate_pos_readiness", return_value=True)
	@patch("retailedge.user_readiness._has_document_read", return_value=True)
	@patch("retailedge.user_readiness.frappe.get_roles", return_value=["RetailEdgeCashier"])
	@patch("retailedge.user_readiness.get_active_branch_assignments", return_value=[assignment()])
	@patch("retailedge.user_readiness.frappe.db.get_value")
	def test_single_active_configured_assignment_is_ready(
		self,
		mock_get_value,
		_assignments,
		_roles,
		_document_read,
		_pos_ready,
	):
		def get_value(doctype, *_args, **_kwargs):
			if doctype == "User":
				return user_values()
			if doctype == "RetailEdge Branch Profile":
				return frappe._dict(name="RE-BP-00001", default_pos_profile="")
			return None

		mock_get_value.side_effect = get_value
		result = user_readiness.get_retailedge_user_readiness(user=USER, company=COMPANY)
		self.assertTrue(result["ready"])
		self.assertEqual(result["status"], "Ready")
		self.assertEqual(result["valid_assignment_count"], 1)
		self.assertEqual(result["starting_context"]["branch"], BRANCH)

	@patch("retailedge.user_readiness._validate_pos_readiness", return_value=True)
	@patch("retailedge.user_readiness._has_document_read", return_value=True)
	@patch("retailedge.user_readiness.frappe.get_roles", return_value=["RetailEdgeManager"])
	@patch(
		"retailedge.user_readiness.get_active_branch_assignments",
		return_value=[assignment(branch="Ketu", is_primary=0), assignment(branch="Ikeja", is_primary=0)],
	)
	@patch("retailedge.user_readiness.frappe.db.get_value")
	def test_multiple_branches_require_one_primary_starting_branch(
		self,
		mock_get_value,
		_assignments,
		_roles,
		_document_read,
		_pos_ready,
	):
		def get_value(doctype, *_args, **_kwargs):
			if doctype == "User":
				return user_values()
			if doctype == "RetailEdge Branch Profile":
				return frappe._dict(name="RE-BP-00001", default_pos_profile="")
			return None

		mock_get_value.side_effect = get_value
		result = user_readiness.get_retailedge_user_readiness(user=USER, company=COMPANY)
		self.assertFalse(result["ready"])
		self.assertIn("primary_branch_required", {reason["code"] for reason in result["reasons"]})

	@patch("retailedge.user_readiness._has_document_read", return_value=True)
	@patch("retailedge.user_readiness.frappe.db.exists", return_value=True)
	@patch("retailedge.user_readiness.frappe.get_all")
	@patch("retailedge.user_readiness.frappe.db.get_value")
	def test_pos_assignment_requires_branch_pos_profile_assignment(
		self,
		mock_get_value,
		mock_get_all,
		_exists,
		_document_read,
	):
		mock_get_all.return_value = [frappe._dict(parent="POS-KETU")]
		mock_get_value.return_value = frappe._dict(company=COMPANY, disabled=0)
		result = user_readiness._base_result(user=USER, company=COMPANY)
		result["applicable"] = True
		ready = user_readiness._validate_pos_readiness(
			user=USER,
			company=COMPANY,
			branch=BRANCH,
			default_pos_profile="POS-IKEJA",
			result=result,
		)
		self.assertFalse(ready)
		self.assertEqual(result["reasons"][0]["code"], "pos_profile_not_assigned")

	@patch("retailedge.operating_context.user_has_global_branch_access", return_value=False)
	@patch(
		"retailedge.operating_context.get_retailedge_user_readiness",
		return_value={"applicable": True, "ready": False, "message": "Assign Company and Branch."},
	)
	def test_operational_scope_is_restricted_zero_when_readiness_is_incomplete(self, _readiness, _global):
		scope = operating_context.get_operational_branch_scope(COMPANY, user=USER)
		self.assertTrue(scope["restricted"])
		self.assertEqual(scope["allowed_branches"], [])
		self.assertEqual(scope["source"], "user_readiness")

	@patch("retailedge.operating_context.user_has_global_branch_access", return_value=True)
	@patch(
		"retailedge.operating_context.get_retailedge_user_readiness",
		return_value={"applicable": True, "ready": True, "message": ""},
	)
	def test_ready_global_manager_remains_global_after_landing_readiness(self, mock_readiness, _global):
		scope = operating_context.get_operational_branch_scope("Another Company", user=USER)
		self.assertFalse(scope["restricted"])
		self.assertEqual(scope["source"], "global")
		mock_readiness.assert_called_with(user=USER, company="")

	@patch(
		"retailedge.operating_context._get_scope_readiness",
		return_value={"applicable": True, "ready": False, "message": "Assign Company and Branch."},
	)
	def test_branch_validation_returns_setup_incomplete_before_branch_fallback(self, _readiness):
		result = operating_context.validate_operating_branch(COMPANY, BRANCH, user=USER, throw=False)
		self.assertFalse(result["allowed"])
		self.assertEqual(result["reason"], "setup_incomplete")

	def test_reconciliation_contract_is_read_only(self):
		source = open(user_readiness.__file__, encoding="utf-8").read()
		self.assertIn("get_retailedge_user_readiness_reconciliation", source)
		self.assertIn('"Has Role"', source)
		self.assertIn("limit_page_length=0", source)
		for forbidden in (
			"frappe.db.commit",
			"frappe.db.set_value",
			"frappe.defaults.set_user_default",
			"add_user_permission",
			"create_branch_assignment(",
		):
			self.assertNotIn(forbidden, source)

	def test_edgesuite_reconciliation_and_fail_closed_navigation_contract(self):
		assignments_source = BRANCH_ASSIGNMENTS_VUE.read_text(encoding="utf-8")
		navigation_source = NAVIGATION.read_text(encoding="utf-8")
		for contract in (
			"User access readiness",
			"get_retailedge_user_readiness_reconciliation",
			"Include ready users",
			"row.repair_action.label",
			"repairReadiness(row)",
			"loadReadiness",
		):
			self.assertIn(contract, assignments_source)
		for contract in (
			"_apply_user_readiness",
			'context["quick_actions"] = []',
			"READINESS_REPAIR_TARGETS",
			'"branch-assignments"',
		):
			self.assertIn(contract, navigation_source)

	def test_assignment_repair_label_comes_from_server_contract(self):
		result = user_readiness._base_result(user=USER, company=COMPANY)
		user_readiness._block(result, "missing_branch_assignment", "Choose a Branch.", "assign_branch")
		self.assertEqual(
			user_readiness._first_repair_action(result),
			{"key": "assign_branch", "label": "Assign Company and Branch"},
		)

	def test_browser_gate_discovers_user_readiness_acceptance(self):
		config = (APP_ROOT.parent / "browser-tests" / "playwright.config.cjs").read_text(encoding="utf-8")
		self.assertIn("|user_readiness|", config)

	def test_readiness_assignment_and_complete_population_ui_state(self):
		result = subprocess.run(
			["node", "--test", str(APP_ROOT / "tests" / "branch_assignments_state.cjs")],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

	@patch("retailedge.user_readiness._has_document_read", return_value=False)
	@patch("retailedge.user_readiness.frappe.db.get_value")
	def test_assignment_cannot_replace_native_company_read_permission(self, get_value, document_read):
		get_value.return_value = frappe._dict(name="RE-BP-00001", default_pos_profile="")
		result = user_readiness._base_result(user=USER, company=COMPANY)
		self.assertFalse(user_readiness._validate_assignment(row=assignment(), user=USER, result=result))
		self.assertEqual(result["reasons"][0]["code"], "company_permission_missing")
		document_read.assert_called_once_with("Company", COMPANY, user=USER)


if __name__ == "__main__":
	unittest.main()
