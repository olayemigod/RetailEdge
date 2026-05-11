from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.integrations.branch_context import get_active_branch, get_user_allowed_branches
from retailedge.integrations.coreedge import is_coreedge_enabled, is_coreedge_installed
from retailedge.integrations.notifications import send_retailedge_notification
from retailedge.integrations.payments import create_payment_request_for_sales_invoice


class _Settings:
	enable_coreedge_integration = 0
	enable_coreedge_payment_requests = 0
	enable_coreedge_notifications = 0
	enable_coreedge_branch_context = 0
	coreedge_required_for_portal = 0


class CoreEdgeReadinessTests(unittest.TestCase):
	@patch("retailedge.integrations.coreedge.frappe.get_installed_apps", return_value=[])
	def test_is_coreedge_installed_returns_boolean(self, _mock_get_installed_apps):
		self.assertIs(is_coreedge_installed(), False)

	@patch("retailedge.integrations.coreedge.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.integrations.coreedge.frappe.get_installed_apps", return_value=["frappe", "coreedge"])
	def test_is_coreedge_enabled_respects_settings(self, _mock_get_installed_apps, mock_settings):
		self.assertFalse(is_coreedge_enabled())
		mock_settings.return_value.enable_coreedge_integration = 1
		self.assertTrue(is_coreedge_enabled())

	@patch("retailedge.integrations.coreedge.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.integrations.coreedge.frappe.get_installed_apps", return_value=[])
	def test_coreedge_not_installed_does_not_crash(self, _mock_get_installed_apps, _mock_settings):
		self.assertFalse(is_coreedge_enabled())

	@patch("retailedge.integrations.payments.frappe.db.exists", return_value=False)
	def test_payment_request_adapter_returns_fallback_when_invoice_missing(self, _mock_exists):
		result = create_payment_request_for_sales_invoice("SINV-TEST-DOES-NOT-EXIST")
		self.assertEqual(result["provider"], "manual")
		self.assertIn(result["status"], {"unavailable", "fallback"})

	@patch("retailedge.integrations.notifications.get_coreedge_status", return_value={"notifications_enabled": 0})
	def test_notification_adapter_returns_fallback_when_coreedge_unavailable(self, _mock_status):
		result = send_retailedge_notification("test_event", ["user@example.com"])
		self.assertEqual(result["provider"], "frappe")
		self.assertEqual(result["status"], "fallback")

	@patch("retailedge.integrations.branch_context.get_coreedge_status", return_value={"branch_context_enabled": 0})
	def test_branch_context_returns_safe_defaults_when_coreedge_unavailable(self, _mock_status):
		self.assertIsNone(get_active_branch())
		self.assertEqual(get_user_allowed_branches(), [])
