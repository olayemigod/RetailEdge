from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.branch_profile import (
	_profile_matches_pos_profile,
	get_branch_profile,
)


class TestBranchProfilePosProfileResolution(unittest.TestCase):
	def test_blank_profile_is_not_wildcard_for_explicit_pos_profile(self):
		profile = SimpleNamespace(default_pos_profile=None)
		self.assertFalse(_profile_matches_pos_profile(profile, "Ketu POS Profile"))

	def test_blank_profile_remains_eligible_when_no_pos_profile_requested(self):
		profile = SimpleNamespace(default_pos_profile=None)
		self.assertTrue(_profile_matches_pos_profile(profile, None))

	@patch("retailedge.branch_profile._has_doctype", return_value=True)
	@patch("retailedge.branch_profile.frappe.get_doc")
	@patch("retailedge.branch_profile.frappe.get_all")
	@patch("retailedge.branch_profile._get_profile_by_filters")
	def test_company_default_blank_does_not_steal_explicit_pos_profile(
		self,
		mock_get_profile,
		mock_get_all,
		mock_get_doc,
		_mock_has_doctype,
	):
		company_default = SimpleNamespace(
			name="Lagos Island Setup",
			branch="Lagos Island",
			default_pos_profile=None,
		)
		ketu = SimpleNamespace(
			name="Ketu Setup",
			branch="Ketu",
			default_pos_profile="Ketu POS Profile",
		)
		mock_get_profile.return_value = company_default
		mock_get_all.return_value = [
			{"name": "Lagos Island Setup"},
			{"name": "Ketu Setup"},
		]
		mock_get_doc.side_effect = [company_default, ketu]

		profile = get_branch_profile(
			company="RetailEdge Consulting",
			pos_profile="Ketu POS Profile",
			active_only=True,
		)

		self.assertIs(profile, ketu)
		self.assertEqual(profile.branch, "Ketu")

	@patch("retailedge.branch_profile._has_doctype", return_value=True)
	@patch("retailedge.branch_profile.frappe.get_doc")
	@patch("retailedge.branch_profile.frappe.get_all")
	@patch("retailedge.branch_profile._get_profile_by_filters")
	def test_explicit_pos_profile_without_exact_mapping_fails_closed(
		self,
		mock_get_profile,
		mock_get_all,
		mock_get_doc,
		_mock_has_doctype,
	):
		company_default = SimpleNamespace(
			name="Lagos Island Setup",
			branch="Lagos Island",
			default_pos_profile=None,
		)
		mock_get_profile.return_value = company_default
		mock_get_all.return_value = [{"name": "Lagos Island Setup"}]
		mock_get_doc.return_value = company_default

		profile = get_branch_profile(
			company="RetailEdge Consulting",
			pos_profile="Unmapped POS Profile",
			active_only=True,
		)

		self.assertIsNone(profile)


if __name__ == "__main__":
	unittest.main()
