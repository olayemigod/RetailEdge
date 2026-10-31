from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge import user_onboarding


class TestUserOnboardingPOSPreflight(unittest.TestCase):
	@patch("retailedge.user_onboarding._resolve_or_create_user")
	@patch("retailedge.user_onboarding._profile_summary")
	@patch("retailedge.user_onboarding._assert_onboarding_read")
	def test_restricted_pos_write_permission_is_checked_before_user_write(
		self,
		_assert_read,
		mock_profile,
		mock_resolve_user,
	):
		mock_profile.return_value = {
			"configured": True,
			"default_pos_profile": "POS-KETU",
			"pos_required_supported": True,
			"pos_access_mode": "restricted",
			"pos_assigned": False,
			"pos_default": False,
			"can_manage_pos_profile": False,
		}
		with self.assertRaises(frappe.PermissionError):
			user_onboarding.complete_user_onboarding(
				{
					"mode": "new",
					"email": "new-cashier@example.com",
					"first_name": "New",
					"role": "RetailEdgeCashier",
					"branch_role": "Cashier",
					"company": "RetailEdge Consulting",
					"branch": "Ketu",
					"effective_from": "2026-10-23",
					"is_primary": 1,
					"requires_pos": 1,
					"send_welcome_email": 0,
				}
			)
		mock_resolve_user.assert_not_called()


if __name__ == "__main__":
	unittest.main()
