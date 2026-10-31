from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.retailedge.page.retailedge_setup import retailedge_setup


class TestUserOnboardingSetupVisibility(unittest.TestCase):
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup.frappe.utils.get_fullname", return_value="QA Admin")
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup._bounded_visible_count", return_value={"count": 0, "count_capped": False})
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup._doctype_available", return_value=True)
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup._has_permission")
	def test_onboarding_card_requires_branch_assignment_read(
		self,
		mock_has_permission,
		_doctype_available,
		_count,
		_fullname,
	):
		def permission(doctype: str, ptype: str) -> bool:
			if doctype == "RetailEdge Branch Assignment" and ptype == "read":
				return False
			return True

		mock_has_permission.side_effect = permission
		resources = retailedge_setup.get_setup_context()["resources"]
		self.assertNotIn("user-onboarding", {row["key"] for row in resources})

	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup.frappe.utils.get_fullname", return_value="QA Admin")
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup._bounded_visible_count", return_value={"count": 7, "count_capped": False})
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup._doctype_available", return_value=True)
	@patch("retailedge.retailedge.page.retailedge_setup.retailedge_setup._has_permission", return_value=True)
	def test_onboarding_card_is_available_without_user_count_when_required_reads_are_present(
		self,
		_has_permission,
		_doctype_available,
		_count,
		_fullname,
	):
		resources = retailedge_setup.get_setup_context()["resources"]
		onboarding = next(row for row in resources if row["key"] == "user-onboarding")
		self.assertIsNone(onboarding["count"])
		self.assertFalse(onboarding["count_capped"])


if __name__ == "__main__":
	unittest.main()
