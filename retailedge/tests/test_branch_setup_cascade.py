from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.branch_profile_queries import (
	MAX_BRANCH_RESULTS,
	MAX_BRANCH_SCAN_RESULTS,
	_active_candidate_branches,
	_assigned_candidate_branches,
)

APP_ROOT = Path(__file__).resolve().parents[1]
BRANCH_PROFILE_JS = (
	APP_ROOT
	/ "retailedge"
	/ "doctype"
	/ "retailedge_branch_profile"
	/ "retailedge_branch_profile.js"
)
BRANCH_PROFILE_CONTROLLER = (
	APP_ROOT
	/ "retailedge"
	/ "doctype"
	/ "retailedge_branch_profile"
	/ "retailedge_branch_profile.py"
)


class TestBranchSetupCascade(unittest.TestCase):
	def test_new_setup_company_change_clears_branch_and_uses_unassigned_query(self):
		source = BRANCH_PROFILE_JS.read_text(encoding="utf-8")
		for contract in (
			'frm.set_query("branch"',
			"retailedge.branch_profile_queries.search_available_branch_setup_branches",
			'company: frm.doc.company || ""',
			'profile_name: frm.doc.name || ""',
			'frm.set_value("branch", null)',
			"Choose an unassigned Branch to establish its Company mapping",
		):
			self.assertIn(contract, source)

	def test_unused_setup_identity_remains_directly_editable(self):
		frontend = BRANCH_PROFILE_JS.read_text(encoding="utf-8")
		controller = BRANCH_PROFILE_CONTROLLER.read_text(encoding="utf-8")
		for contract in (
			"identity_editable",
			"No operational history was found. Company and Branch can be corrected directly",
			"clearIdentityDependentDefaults(frm)",
			"BRANCH_USER_TABLE_FIELDS",
		):
			self.assertIn(contract, frontend)
		for contract in (
			"identity_changed",
			"get_branch_operational_usage",
			"if usage or _has_assignment_history(self.name):",
			"controlled_branch_reassignment",
			"_clear_identity_dependent_values(self)",
			"_clear_branch_users(self)",
			"API/import",
		):
			self.assertIn(contract, controller)
		self.assertNotIn('frm.toggle_enable("company", isNew)', frontend)
		self.assertNotIn("cannot be changed after save", controller)

	def test_used_setup_has_controlled_reassignment_action(self):
		frontend = BRANCH_PROFILE_JS.read_text(encoding="utf-8")
		controller = BRANCH_PROFILE_CONTROLLER.read_text(encoding="utf-8")
		for contract in (
			'__("Change Company / Branch")',
			"requires_controlled_reassignment",
			"search_reassignment_target_branches",
			"Validate & Reassign",
			"will not change submitted ERPNext documents",
		):
			self.assertIn(contract, frontend)
		for contract in (
			"def reassign_branch_profile",
			"_create_historical_snapshot",
			"archive.enabled = 0",
			"doc.flags.controlled_branch_reassignment = True",
			"Close active POS work before changing this Branch assignment",
			"IDENTITY_DEPENDENT_FIELDS",
			"BRANCH_USER_TABLE_FIELDS",
		):
			self.assertIn(contract, controller)
		self.assertNotIn("ignore_permissions=True", controller)
		self.assertNotIn("frappe.db.commit", controller)

	def test_branch_search_is_bounded_permission_aware_and_requires_company(self):
		source = (APP_ROOT / "branch_profile_queries.py").read_text(encoding="utf-8")
		for contract in (
			"MAX_BRANCH_RESULTS = 20",
			"MAX_BRANCH_SCAN_RESULTS = 200",
			"if not company:",
			'frappe.get_list(\n\t\t\t"Branch"',
			'frappe.get_list(\n\t\t"RetailEdge Branch Profile"',
			"while len(available) < needed and scanned < MAX_BRANCH_SCAN_RESULTS",
			"including disabled historical mappings",
			"search_reassignment_target_branches",
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("limit_page_length=0", source)
		self.assertEqual(MAX_BRANCH_RESULTS, 20)
		self.assertEqual(MAX_BRANCH_SCAN_RESULTS, 200)

	@patch("retailedge.branch_profile_queries.frappe.get_list")
	def test_normal_setup_treats_disabled_and_enabled_mappings_as_assigned(self, mock_get_list):
		mock_get_list.return_value = [
			frappe._dict(name="SETUP-LAGOS", branch="Lagos", company="Company A", enabled=0),
			frappe._dict(name="SETUP-ABUJA", branch="Abuja", company="Company B", enabled=1),
			frappe._dict(name="CURRENT", branch="Current", company="Company A", enabled=0),
		]

		assigned = _assigned_candidate_branches(
			["Lagos", "Abuja", "Current"], profile_name="CURRENT"
		)

		self.assertEqual(assigned, {"Lagos", "Abuja"})
		mock_get_list.assert_called_once_with(
			"RetailEdge Branch Profile",
			filters={"branch": ["in", ["Lagos", "Abuja", "Current"]]},
			fields=["name", "branch", "company", "enabled"],
			limit_page_length=20,
			order_by="branch asc",
		)

	@patch("retailedge.branch_profile_queries.frappe.get_list")
	def test_controlled_reassignment_only_reserves_enabled_mappings(self, mock_get_list):
		mock_get_list.return_value = [
			frappe._dict(name="SETUP-ABUJA", branch="Abuja", company="Company B", enabled=1),
			frappe._dict(name="CURRENT", branch="Current", company="Company A", enabled=1),
		]

		active = _active_candidate_branches(
			["Lagos", "Abuja", "Current"], profile_name="CURRENT"
		)

		self.assertEqual(active, {"Abuja"})
		mock_get_list.assert_called_once_with(
			"RetailEdge Branch Profile",
			filters={"branch": ["in", ["Lagos", "Abuja", "Current"]], "enabled": 1},
			fields=["name", "branch", "company", "enabled"],
			limit_page_length=20,
			order_by="branch asc",
		)

	def test_operational_branch_use_remains_enabled_only(self):
		source = (APP_ROOT / "branch_profile.py").read_text(encoding="utf-8")
		self.assertIn('filters = {"enabled": 1}', source)
		self.assertIn("get_enabled_branch_profiles", source)
		self.assertIn("get_exact_branch_profile", source)


if __name__ == "__main__":
	unittest.main()
