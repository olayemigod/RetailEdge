from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestOperatingContextPhase2(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_operating_context_is_session_scoped_and_permission_aware(self):
		source = self.read("operating_context.py")
		for contract in (
			"OPERATING_CONTEXT_TTL_SECONDS",
			"frappe.session.sid",
			"frappe.cache.get_value",
			"frappe.cache.set_value",
			"frappe.cache.delete_value",
			"frappe.get_list(",
			"validate_user_branch_access",
			"frappe.has_permission(\"Company\", \"read\"",
			"frappe.has_permission(\"Branch\", \"read\"",
			"Branch {0} does not belong to Company {1}",
			"Branch {0} is disabled",
		):
			self.assertIn(contract, source)

		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn("frappe.db.commit", source)

	def test_switcher_exposes_explicit_get_switch_and_clear_api(self):
		source = self.read("operating_context.py")
		for contract in (
			"def get_operating_context(",
			"def get_allowed_operating_contexts(",
			"def switch_operating_context(",
			"def clear_operating_context(",
			"def get_effective_operating_context(",
		):
			self.assertIn(contract, source)

	def test_context_guides_new_work_but_explicit_selection_wins(self):
		source = self.read("operating_context.py")
		self.assertIn("Explicit arguments win", source)
		self.assertIn("Existing documents continue to use", source)
		self.assertNotIn("db.set_value", source)
		self.assertNotIn("set_value(\"Sales Invoice\"", source)
		self.assertNotIn("set_value(\"Payment Entry\"", source)
		self.assertNotIn("set_value(\"Stock Entry\"", source)

	def test_branch_profile_defaults_are_returned_for_active_context(self):
		source = self.read("operating_context.py")
		for contract in (
			"get_branch_profile_defaults",
			'"default_pos_profile"',
			'"default_stock_location"',
			'"default_source_stock_location"',
			'"default_destination_stock_location"',
		):
			self.assertIn(contract, source)

	def test_guided_entry_uses_operating_context_only_when_selection_is_missing(self):
		source = self.read("guided_entry_context.py")
		self.assertIn("get_effective_operating_context", source)
		self.assertIn("if not company or (not branch and not warehouse):", source)
		self.assertIn("if not branch and not warehouse:", source)
		self.assertIn("Warehouse is authoritative", source)
		self.assertIn('"source": "warehouse"', source)
		self.assertNotIn("frappe.get_all(", source)

	def test_customer_wording_uses_stock_location_without_renaming_warehouse_identity(self):
		source = self.read("guided_entry_context.py")
		self.assertIn("Branch/Stock Location pair", source)
		self.assertIn("Stock Location {0} does not belong to Company {1}", source)
		self.assertIn('"Warehouse"', source)
		self.assertIn('frappe.db.get_value("Warehouse"', source)


if __name__ == "__main__":
	unittest.main()
