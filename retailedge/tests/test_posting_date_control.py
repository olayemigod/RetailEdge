from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import frappe

from retailedge.events.sales_invoice import validate_sales_invoice
from retailedge.posting_date_control import can_override_posting_date, get_posting_date_context


def _settings(*, enabled=0, allow_override=0, roles=None):
	return SimpleNamespace(
		enable_posting_date_control=enabled,
		allow_pos_posting_date_override=allow_override,
		posting_date_allowed_roles=[SimpleNamespace(role=role) for role in (roles or [])],
	)


class PostingDateControlTests(unittest.TestCase):
	@patch("retailedge.posting_date_control.get_retailedge_settings", return_value=_settings())
	def test_posting_date_control_disabled_returns_false(self, _mock_settings):
		self.assertFalse(can_override_posting_date(user="cashier@example.com"))

	@patch("retailedge.posting_date_control.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=1))
	def test_administrator_can_override(self, _mock_settings):
		self.assertTrue(can_override_posting_date(user="Administrator"))

	@patch("retailedge.posting_date_control.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=1))
	@patch("retailedge.posting_date_control.frappe.get_roles", return_value=["System Manager"])
	def test_system_manager_can_override(self, _mock_roles, _mock_settings):
		self.assertTrue(can_override_posting_date(user="manager@example.com"))

	@patch("retailedge.posting_date_control.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=1, roles=["Retail Supervisor"]))
	@patch("retailedge.posting_date_control.frappe.get_roles", return_value=["Retail Supervisor"])
	def test_configured_allowed_role_can_override(self, _mock_roles, _mock_settings):
		self.assertTrue(can_override_posting_date(user="supervisor@example.com"))

	@patch("retailedge.posting_date_control.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=1, roles=["Retail Supervisor"]))
	@patch("retailedge.posting_date_control.frappe.get_roles", return_value=["Sales User"])
	def test_unconfigured_role_cannot_override(self, _mock_roles, _mock_settings):
		self.assertFalse(can_override_posting_date(user="cashier@example.com"))

	@patch("retailedge.events.sales_invoice.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=0))
	@patch("retailedge.events.sales_invoice.can_override_posting_date", return_value=False)
	def test_backdated_pos_invoice_blocks_unauthorized_user(self, _mock_can_override, _mock_settings):
		doc = SimpleNamespace(is_pos=1, posting_date="2026-05-07")

		with patch("retailedge.events.sales_invoice.today", return_value="2026-05-08"):
			with self.assertRaises(frappe.ValidationError):
				validate_sales_invoice(doc)

	@patch("retailedge.events.sales_invoice.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=0))
	def test_non_pos_sales_invoice_is_not_blocked(self, _mock_settings):
		doc = SimpleNamespace(is_pos=0, posting_date="2026-05-07")

		with patch("retailedge.events.sales_invoice.today", return_value="2026-05-08"):
			self.assertIsNone(validate_sales_invoice(doc))

	@patch("retailedge.posting_date_control.get_retailedge_settings", return_value=_settings(enabled=1, allow_override=1, roles=["Retail Supervisor"]))
	@patch("retailedge.posting_date_control.frappe.get_roles", return_value=["System Manager"])
	def test_posting_date_context_exposes_roles_only_for_admin_or_system_manager(self, _mock_roles, _mock_settings):
		context = get_posting_date_context(user="manager@example.com")
		self.assertEqual(context["enabled"], 1)
		self.assertEqual(context["allow_override"], 1)
		self.assertEqual(context["allowed_roles"], ["Retail Supervisor"])
