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

	@patch("retailedge.action_center.get_action_center_data")
	@patch("retailedge.action_follow_up.frappe.db.exists")
	def test_update_rejects_non_visible_fingerprint(self, exists, get_actions):
		exists.return_value = True
		get_actions.return_value = {"filters": {"company": "Test Company", "branch": ""}, "items": []}
		with self.assertRaises(frappe.PermissionError):
			action_follow_up.update_action_follow_up("not-visible", "acknowledge", {"company": "Test Company"})

	def test_follow_up_source_contains_no_business_resolution_calls(self):
		source = Path(action_follow_up.__file__).read_text(encoding="utf-8")
		for forbidden in (".submit(", "apply_workflow(", "ignore_permissions=True", "frappe.db.commit("):
			self.assertNotIn(forbidden, source)

	def test_doctype_is_follow_up_state_not_resolution(self):
		doc_path = Path(action_follow_up.__file__).resolve().parent / "retailedge/doctype/retailedge_action_follow_up/retailedge_action_follow_up.json"
		doc = doc_path.read_text(encoding="utf-8")
		self.assertIn('"Open\\nAcknowledged\\nSnoozed"', doc)
		self.assertNotIn("Resolved", doc)
		self.assertNotIn("Closed", doc)


if __name__ == "__main__":
	unittest.main()
