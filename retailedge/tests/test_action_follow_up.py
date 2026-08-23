from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import action_follow_up


class TestActionFollowUp(unittest.TestCase):
	def setUp(self):
		frappe.session.user = "Administrator"

	def test_fingerprint_is_stable_and_scope_sensitive(self):
		base = dict(company="Test Company", branch="Main", source="stock", kind="management_exception", label="Out of stock", route="/app/stock-position")
		first = action_follow_up.action_fingerprint(**base)
		second = action_follow_up.action_fingerprint(**base)
		other_branch = action_follow_up.action_fingerprint(**{**base, "branch": "Other"})
		self.assertEqual(first, second)
		self.assertNotEqual(first, other_branch)

	@patch("retailedge.action_follow_up.frappe.db.exists")
	def test_decorate_adds_fingerprint_when_storage_is_not_installed(self, exists):
		exists.return_value = False
		items = [{"source": "stock", "kind": "management_exception", "label": "Out of stock", "route": "/app/stock-position"}]
		result = action_follow_up.decorate_action_items(items, company="Test Company", branch="Main")
		self.assertTrue(result[0]["fingerprint"])
		self.assertNotIn("follow_up", result[0])

	def test_expired_snooze_is_effectively_open_and_due(self):
		state = action_follow_up.effective_follow_up_state(
			{"status": "Snoozed", "snoozed_until": "2026-08-19 09:00:00", "follow_up_on": "2026-08-19 08:00:00"},
			now="2026-08-19 10:00:00",
		)
		self.assertEqual(state["status"], "Snoozed")
		self.assertEqual(state["effective_status"], "Open")
		self.assertTrue(state["snooze_expired"])
		self.assertTrue(state["is_due"])

	def test_active_snooze_is_not_due_until_visible_again(self):
		state = action_follow_up.effective_follow_up_state(
			{"status": "Snoozed", "snoozed_until": "2026-08-19 12:00:00", "follow_up_on": "2026-08-19 08:00:00"},
			now="2026-08-19 10:00:00",
		)
		self.assertEqual(state["effective_status"], "Snoozed")
		self.assertFalse(state["snooze_expired"])
		self.assertFalse(state["is_due"])

	def test_visibility_filters_remove_management_only_filters(self):
		filters = action_follow_up._visibility_filters(
			{
				"company": "Test Company",
				"branch": "Main",
				"follow_up_status": "Open",
				"assignment_scope": "mine",
				"due_scope": "due",
			}
		)
		self.assertEqual(filters, {"company": "Test Company", "branch": "Main"})

	@patch("retailedge.business_control_center.get_business_control_center")
	@patch("retailedge.action_follow_up.frappe.db.exists")
	def test_update_rejects_non_visible_fingerprint(self, exists, get_controls):
		exists.return_value = True
		get_controls.return_value = {"filters": {"company": "Test Company", "branch": ""}, "items": []}
		with self.assertRaises(frappe.PermissionError):
			action_follow_up.update_action_follow_up("not-visible", "acknowledge", {"company": "Test Company"})

	@patch("retailedge.action_follow_up.frappe.get_roles", return_value=["Sales User"])
	def test_non_action_center_role_cannot_manage_follow_up(self, _roles):
		frappe.session.user = "sales@example.com"
		with self.assertRaises(frappe.PermissionError):
			action_follow_up._assert_action_center_role()

	@patch("retailedge.action_follow_up.frappe.get_roles", return_value=["Sales User"])
	@patch("retailedge.action_follow_up.frappe.db.get_value", return_value=1)
	def test_assignment_target_must_have_action_center_role(self, _enabled, _roles):
		with self.assertRaises(frappe.PermissionError):
			action_follow_up._validate_assignment_user(
				"sales@example.com",
				company="Test Company",
				branch="",
			)

	@patch("retailedge.branch_context.user_has_global_branch_access", return_value=False)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	@patch("retailedge.action_follow_up.frappe.db.get_value", return_value=1)
	def test_company_level_r9_assignment_requires_global_branch_scope(self, _enabled, _has_role, _global):
		with self.assertRaises(frappe.PermissionError):
			action_follow_up._validate_assignment_user(
				"branch.manager@example.com",
				company="Test Company",
				branch="",
				require_global_scope=True,
			)

	@patch("retailedge.branch_context.user_has_global_branch_access", return_value=True)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	@patch("retailedge.action_follow_up.frappe.db.get_value", return_value=1)
	def test_company_level_r9_assignment_allows_global_branch_scope(self, _enabled, _has_role, _global):
		action_follow_up._validate_assignment_user(
			"owner@example.com",
			company="Test Company",
			branch="",
			require_global_scope=True,
		)

	@patch("retailedge.action_follow_up._has_action_center_role", return_value=False)
	def test_direct_query_denies_users_without_action_center_role(self, _has_role):
		self.assertEqual(action_follow_up.get_permission_query_conditions("sales@example.com"), "1=0")

	@patch("retailedge.action_follow_up.frappe.db.escape", return_value="'Main'")
	@patch("retailedge.branch_context.get_user_allowed_branches", return_value={"branches": ["Main"]})
	@patch("retailedge.branch_context.user_has_global_branch_access", return_value=False)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_direct_query_is_restricted_to_permitted_branches(
		self, _has_role, _global_access, _allowed_branches, _escape
	):
		condition = action_follow_up.get_permission_query_conditions("manager@example.com")
		self.assertIn("`branch` in ('Main')", condition)
		self.assertIn("RetailEdge Action Follow Up", condition)

	@patch("retailedge.action_follow_up._has_owner_financial_access", return_value=False)
	@patch("retailedge.branch_context.user_has_global_branch_access", return_value=True)
	@patch("retailedge.action_follow_up._has_action_center_role", return_value=True)
	def test_global_action_center_role_without_owner_access_excludes_only_r9_financial_followups(
		self, _has_role, _global_access, _owner_access
	):
		condition = action_follow_up.get_permission_query_conditions("manager@example.com")
		self.assertIn("source", condition)
		self.assertIn("r9_early_warning", condition)
		self.assertNotIn("`branch`", condition)

	def test_permission_hooks_are_registered(self):
		hooks_path = Path(action_follow_up.__file__).resolve().parent / "hooks.py"
		source = hooks_path.read_text(encoding="utf-8")
		self.assertIn("permission_query_conditions", source)
		self.assertIn("retailedge.action_follow_up.get_permission_query_conditions", source)
		self.assertIn("retailedge.action_follow_up.has_permission", source)

	def test_follow_up_source_contains_no_business_resolution_calls(self):
		source = Path(action_follow_up.__file__).read_text(encoding="utf-8")
		for forbidden in (".submit(", "apply_workflow(", "ignore_permissions=True", "frappe.db.commit("):
			self.assertNotIn(forbidden, source)
		self.assertIn("get_business_control_center", source)
		self.assertIn("require_global_scope", source)

	def test_doctype_is_follow_up_state_not_resolution(self):
		doc_path = Path(action_follow_up.__file__).resolve().parent / "retailedge/doctype/retailedge_action_follow_up/retailedge_action_follow_up.json"
		doc = doc_path.read_text(encoding="utf-8")
		self.assertIn('"Open\\nAcknowledged\\nSnoozed"', doc)
		self.assertNotIn("Resolved", doc)
		self.assertNotIn("Closed", doc)

	def test_doctype_controller_blocks_direct_non_admin_writes(self):
		controller_path = (
			Path(action_follow_up.__file__).resolve().parent
			/ "retailedge/doctype/retailedge_action_follow_up/retailedge_action_follow_up.py"
		)
		source = controller_path.read_text(encoding="utf-8")
		self.assertIn("retailedge_action_follow_up_api_write", source)
		self.assertIn("can only be changed from the Action Centre", source)
		self.assertIn("frappe.PermissionError", source)


if __name__ == "__main__":
	unittest.main()
