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
			'getattr(frappe.session, "sid"',
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

	def test_context_preview_does_not_clear_valid_session_context(self):
		source = self.read("operating_context.py")
		self.assertIn("Previewing Branch", source)
		self.assertIn("current = get_operating_context()", source)
		self.assertIn('"selected_company": selected_company', source)

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

	def test_open_pos_sessions_block_cross_branch_context_switch(self):
		source = self.read("operating_context.py")
		for contract in (
			"find_open_pos_opening_shift",
			"resolve_branch_from_opening_shift",
			'"code": "open_pos_shift"',
			'"POS Opening Entry"',
			"_find_open_erpnext_pos_opening",
			"resolve_branch_from_pos_profile",
			'"code": "open_erpnext_pos"',
			"_assert_switch_safe",
			"Close the active POS shift before switching",
			"Close the active POS Opening Entry before switching",
		):
			self.assertIn(contract, source)

	def test_guided_entry_uses_operating_context_only_when_selection_is_missing(self):
		source = self.read("guided_entry_context.py")
		self.assertIn("get_effective_operating_context", source)
		self.assertIn("if not company or (not branch and not warehouse):", source)
		self.assertIn("if not branch and not warehouse:", source)
		self.assertIn("explicitly selected Stock Location remains authoritative", source)
		self.assertIn("used_operating_context", source)
		self.assertIn('"source": "warehouse"', source)
		self.assertNotIn("frappe.get_all(", source)

	def test_customer_wording_uses_stock_location_without_renaming_warehouse_identity(self):
		source = self.read("guided_entry_context.py")
		self.assertIn("Branch/Stock Location pair", source)
		self.assertIn("Stock Location {0} does not belong to Company {1}", source)
		self.assertIn('"Warehouse"', source)
		self.assertIn('frappe.db.get_value("Warehouse"', source)

	def test_shell_context_uses_operating_company_branch_and_exposes_switcher(self):
		source = self.read("master_experience.py")
		for contract in (
			"get_operating_context",
			'"label": "Operating Context"',
			'"target": "operating-context"',
			'"company": operating.get("company")',
			'"branch": operating.get("branch")',
			'feature_flags["operating_branch_context"] = "phase2_active"',
		):
			self.assertIn(contract, source)

	def test_operating_context_page_cascades_company_branch_and_invalidates_shell_cache(self):
		source = self.read("retailedge/page/operating_context/operating_context.js")
		for contract in (
			"get_allowed_operating_contexts",
			"switch_operating_context",
			"clear_operating_context",
			"Operating Company",
			"Operating Branch",
			"preserveCompanySelection",
			"getClientSwitchBlocker",
			"retailedgeOperatingContextGuard",
			"__retailedgeBusinessHubContextCache = null",
			"retailedge-operating-context-changed",
		):
			self.assertIn(contract, source)

	def test_page_fixture_is_customer_facing_and_keeps_internal_route_stable(self):
		source = self.read("retailedge/page/operating_context/operating_context.json")
		self.assertIn('"name": "operating-context"', source)
		self.assertIn('"page_name": "operating-context"', source)
		self.assertIn('"title": "Operating Context"', source)


if __name__ == "__main__":
	unittest.main()
