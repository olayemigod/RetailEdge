from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.branch_profile_queries import MAX_BRANCH_RESULTS, _reserved_enabled_branches

APP_ROOT = Path(__file__).resolve().parents[1]
BRANCH_PROFILE_JS = (
	APP_ROOT
	/ "retailedge"
	/ "doctype"
	/ "retailedge_branch_profile"
	/ "retailedge_branch_profile.js"
)


class TestBranchSetupCascade(unittest.TestCase):
	def test_company_change_clears_branch_and_rebinds_branch_query(self):
		source = BRANCH_PROFILE_JS.read_text(encoding="utf-8")
		for contract in (
			'frm.set_query("branch"',
			"retailedge.branch_profile_queries.search_available_branch_setup_branches",
			'company: frm.doc.company || ""',
			'profile_name: frm.doc.name || ""',
			'frm.toggle_enable("branch", Boolean(frm.doc.company))',
			'frm.set_value("branch", null)',
		):
			self.assertIn(contract, source)

	def test_branch_search_is_bounded_permission_aware_and_requires_company(self):
		source = (APP_ROOT / "branch_profile_queries.py").read_text(encoding="utf-8")
		for contract in (
			"MAX_BRANCH_RESULTS = 20",
			"if not company:",
			'frappe.get_list(\n\t\t"Branch"',
			'frappe.get_list(\n\t\t"RetailEdge Branch Profile"',
			'limit_page_length=min(cint(page_len) or MAX_BRANCH_RESULTS, MAX_BRANCH_RESULTS)',
		):
			self.assertIn(contract, source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertEqual(MAX_BRANCH_RESULTS, 20)

	@patch("retailedge.branch_profile_queries.frappe.get_list")
	def test_current_setup_is_not_reserved_but_other_enabled_setups_are(self, mock_get_list):
		mock_get_list.return_value = [
			frappe._dict(name="SETUP-LAGOS", branch="Lagos"),
			frappe._dict(name="SETUP-ABUJA", branch="Abuja"),
			frappe._dict(name="SETUP-PORT", branch="Port Harcourt"),
		]

		reserved = _reserved_enabled_branches(profile_name="SETUP-LAGOS")

		self.assertEqual(reserved, ["Abuja", "Port Harcourt"])
		mock_get_list.assert_called_once_with(
			"RetailEdge Branch Profile",
			filters={"enabled": 1},
			fields=["name", "branch"],
			limit_page_length=0,
			order_by="branch asc",
		)


if __name__ == "__main__":
	unittest.main()
