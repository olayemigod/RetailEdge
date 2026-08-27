from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.branch_profile_queries import (
	MAX_BRANCH_RESULTS,
	MAX_BRANCH_SCAN_RESULTS,
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
			"if (!frm.is_new())",
			'frm.set_value("branch", null)',
			"Choose an unassigned Branch here to assign it to this Company",
		):
			self.assertIn(contract, source)

	def test_saved_setup_locks_company_and_branch_identity(self):
		frontend = BRANCH_PROFILE_JS.read_text(encoding="utf-8")
		controller = BRANCH_PROFILE_CONTROLLER.read_text(encoding="utf-8")
		for contract in (
			'frm.toggle_enable("company", isNew)',
			'frm.toggle_enable("branch", isNew && Boolean(frm.doc.company))',
			"assignment is fixed after the Branch Setup is saved",
		):
			self.assertIn(contract, frontend)
		for contract in (
			"_validate_company_branch_identity",
			"cannot be changed after save",
			'"branch": self.branch',
			"Disabling that setup does not release the Branch",
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
			"considered assigned as soon as any Branch Setup exists",
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("limit_page_length=0", source)
		self.assertEqual(MAX_BRANCH_RESULTS, 20)
		self.assertEqual(MAX_BRANCH_SCAN_RESULTS, 200)

	@patch("retailedge.branch_profile_queries.frappe.get_list")
	def test_disabled_and_enabled_setups_both_preserve_branch_ownership(self, mock_get_list):
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

	def test_operational_branch_use_remains_enabled_only(self):
		source = (APP_ROOT / "branch_profile.py").read_text(encoding="utf-8")
		self.assertIn('filters = {"enabled": 1}', source)
		self.assertIn("get_enabled_branch_profiles", source)
		self.assertIn("get_exact_branch_profile", source)


if __name__ == "__main__":
	unittest.main()
