from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.navigation_visibility import (
	_page_is_functionally_available,
	_quiet_probe,
	_report_is_permitted,
	filter_context_for_runtime_capabilities,
)


class TestNavigationVisibility(unittest.TestCase):
	@patch("retailedge.navigation_visibility._page_is_functionally_available")
	def test_final_filter_removes_inaccessible_pages_but_keeps_pos_url(self, page_available):
		page_available.side_effect = lambda target, **_kwargs: target == "allowed-page"
		context = {
			"context": {"company": "ACME", "branch": "Main"},
			"navigation_groups": [
				{
					"key": "sales",
					"items": [
						{"label": "Start POS", "target_type": "URL", "target": "/pos/"},
						{"label": "Allowed", "target_type": "Page", "target": "allowed-page"},
					],
				},
				{
					"key": "management",
					"items": [
						{"label": "Assets", "target_type": "Page", "target": "assets-control"},
					],
				},
			],
			"quick_actions": [
				{"label": "Start POS", "target_type": "URL", "target": "/pos/"},
				{"label": "Blocked", "target_type": "Page", "target": "blocked-page"},
			],
		}

		filtered = filter_context_for_runtime_capabilities(context)

		self.assertEqual([group["key"] for group in filtered["navigation_groups"]], ["sales"])
		self.assertEqual(
			[item["target"] for item in filtered["navigation_groups"][0]["items"]],
			["/pos/", "allowed-page"],
		)
		self.assertEqual([item["target"] for item in filtered["quick_actions"]], ["/pos/"])

	@patch("retailedge.navigation_visibility.frappe.has_permission")
	@patch("retailedge.navigation_visibility.frappe.db.exists")
	def test_quick_actions_use_doctype_create_permission_instead_of_navigation_target(self, exists, has_permission):
		exists.side_effect = lambda doctype, name: doctype == "DocType" and name in {"Stock Entry", "Journal Entry"}
		has_permission.side_effect = (
			lambda doctype, ptype=None, user=None: doctype == "Stock Entry" and ptype == "create"
		)
		context = {
			"context": {"company": "ACME", "branch": "Main"},
			"navigation_groups": [],
			"quick_actions": [
				{"key": "transfer-stock", "label": "Quick Transfer", "doctype": "Stock Entry"},
				{"key": "journal-entry", "label": "Journal Entry", "doctype": "Journal Entry"},
			],
		}

		filtered = filter_context_for_runtime_capabilities(context)

		self.assertEqual(
			[action["key"] for action in filtered["quick_actions"]],
			["transfer-stock"],
		)
		has_permission.assert_any_call("Stock Entry", ptype="create", user=frappe.session.user)
		has_permission.assert_any_call("Journal Entry", ptype="create", user=frappe.session.user)

	@patch("retailedge.navigation_visibility.get_dashboard_capabilities")
	def test_dashboard_link_is_hidden_when_dashboard_capability_denies_view(self, capabilities):
		capabilities.return_value = {"can_view": False}

		self.assertFalse(
			_page_is_functionally_available(
				"owner-dashboard",
				company="ACME",
				branch="Main",
			)
		)

	@patch("retailedge.navigation_visibility.get_report_capabilities")
	def test_report_link_is_hidden_when_report_capability_denies_view(self, capabilities):
		capabilities.return_value = {"can_view": False}

		self.assertFalse(
			_page_is_functionally_available(
				"cash-movement",
				company="ACME",
				branch="Main",
			)
		)

	@patch("retailedge.navigation_visibility._native_workspace_is_available", return_value=False)
	def test_native_workspace_link_is_hidden_when_no_source_is_accessible(self, _available):
		self.assertFalse(_page_is_functionally_available("assets-control"))
		self.assertFalse(_page_is_functionally_available("service-warranty-control"))
		self.assertFalse(_page_is_functionally_available("sales-team-control"))

	@patch("retailedge.navigation_visibility.assert_can_access_bank_transaction_matching")
	def test_bank_matching_link_is_hidden_when_server_boundary_rejects_user(self, access):
		access.side_effect = frappe.PermissionError("blocked")
		self.assertFalse(_page_is_functionally_available("bank-matching-reconciliation"))

	@patch("retailedge.navigation_visibility._page_is_permitted", return_value=True)
	@patch("retailedge.navigation_visibility.frappe.has_permission", return_value=False)
	@patch("retailedge.navigation_visibility.frappe.db.exists", return_value=True)
	def test_project_operations_is_hidden_without_native_project_read(
		self,
		_exists,
		has_permission,
		_page_permitted,
	):
		self.assertFalse(_page_is_functionally_available("project-operations"))
		has_permission.assert_called_once_with(
			"Project",
			ptype="read",
			user=frappe.session.user,
		)

	@patch("retailedge.navigation_visibility._report_is_permitted", return_value=False)
	def test_managed_review_page_is_hidden_without_underlying_report_access(self, report_permitted):
		self.assertFalse(_page_is_functionally_available("unmatched-bank-payments"))
		report_permitted.assert_called_once_with("RetailEdge Unmatched Bank Payment Events")

	@patch("retailedge.navigation_visibility.frappe.has_permission", return_value=False)
	@patch("retailedge.navigation_visibility.frappe.get_doc")
	@patch("retailedge.navigation_visibility.frappe.db.exists", return_value=True)
	def test_report_discovery_requires_reference_doctype_report_permission(
		self,
		_exists,
		get_doc,
		has_permission,
	):
		report = get_doc.return_value
		report.disabled = False
		report.is_permitted.return_value = True
		report.ref_doctype = "Sales Invoice"

		self.assertFalse(_report_is_permitted("RetailEdge Unmatched Bank Payment Events"))
		has_permission.assert_called_once_with(
			"Sales Invoice",
			ptype="report",
			user=frappe.session.user,
		)

	def test_quiet_probe_restores_message_log_when_permission_probe_fails(self):
		original = list(getattr(frappe.local, "message_log", []) or [])
		try:
			frappe.local.message_log = ["existing"]

			def denied():
				frappe.local.message_log.append("permission probe noise")
				raise frappe.PermissionError("blocked")

			self.assertFalse(_quiet_probe(denied))
			self.assertEqual(frappe.local.message_log, ["existing"])
		finally:
			frappe.local.message_log = original


if __name__ == "__main__":
	unittest.main()
