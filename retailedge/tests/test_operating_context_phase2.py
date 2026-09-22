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
			"get_user_branch_profiles",
			"frappe.has_permission(\"Company\", \"read\"",
			"frappe.has_permission(\"Branch\", \"read\"",
			"Branch {0} does not belong to Company {1}",
			"Branch {0} is disabled",
		):
			self.assertIn(contract, source)

		# Unscoped reads are permitted only inside the operating-option resolvers
		# after RetailEdge has established global or assignment authority.
		self.assertEqual(source.count("frappe.get_all"), 2)
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

	def test_selected_branch_is_persisted_in_the_authenticated_frappe_session(self):
		source = self.read("operating_context.py")
		for contract in (
			'OPERATING_CONTEXT_SESSION_KEY = "retailedge_operating_context"',
			"def _read_session_context(",
			"def _write_session_context(",
			"def _clear_session_context(",
			'getattr(frappe.session, "data", None)',
			"data[OPERATING_CONTEXT_SESSION_KEY] = payload",
			"session_obj.update(force=True)",
			"persisted = _read_session_context()",
			"cached = persisted or _read_cached_context(user=user)",
		):
			self.assertIn(contract, source)

		switch_start = source.index("def switch_operating_context(")
		switch_end = source.index("\n\n@frappe.whitelist()\ndef clear_operating_context", switch_start)
		switch_source = source[switch_start:switch_end]
		self.assertLess(switch_source.index("_write_session_context(context)"), switch_source.index("_write_cached_context(context"))

		clear_start = source.index("def clear_operating_context(")
		clear_end = source.index("\n\ndef get_effective_operating_context", clear_start)
		clear_source = source[clear_start:clear_end]
		self.assertIn("_clear_session_context()", clear_source)
		self.assertIn("_clear_cached_context(user=user)", clear_source)

	def test_primary_branch_assignment_can_anchor_global_initial_context_without_restricting_scope(self):
		source = self.read("operating_context.py")
		fallback_start = source.index("def _resolve_fallback_context(")
		fallback_end = source.index("\n\ndef _resolve_assignment_fallback", fallback_start)
		fallback_source = source[fallback_start:fallback_end]
		for contract in (
			"has_assignments = has_branch_assignments(user=user)",
			"assignment_anchor = (",
			"_resolve_assignment_fallback(user=user, company=fallback_company)",
			'fallback_company = _clean(assignment_anchor.get("company"))',
			'if _clean(assignment_anchor.get("branch")):',
			"resolved = assignment_anchor",
		):
			self.assertIn(contract, fallback_source)

		# The assignment is only the initial anchor for a global RetailEdge manager.
		# Effective operational scope must still take the global-access path first.
		scope_start = source.index("def get_operational_branch_scope(")
		scope_end = source.index("\n\ndef resolve_operational_branch", scope_start)
		scope_source = source[scope_start:scope_end]
		self.assertLess(scope_source.index("if has_global_access:"), scope_source.index("if has_branch_assignments(user=user):"))
		self.assertIn('"restricted": False', scope_source)
		self.assertIn('"source": "global"', scope_source)

	def test_global_operating_options_follow_retailedge_authority_without_frappe_link_grants(self):
		source = self.read("operating_context.py")
		companies_start = source.index("def _allowed_companies(")
		companies_end = source.index("\n\ndef _allowed_branches", companies_start)
		companies_source = source[companies_start:companies_end]
		for contract in (
			"global_access = user_has_global_branch_access(user=user)",
			"reader = frappe.get_all if global_access else frappe.get_list",
			"if global_access or not assignment_authoritative:",
		):
			self.assertIn(contract, companies_source)

		branches_start = source.index("def _allowed_branches(")
		branches_end = source.index("\n\ndef _assert_company_access", branches_start)
		branches_source = source[branches_start:branches_end]
		for contract in (
			"global_access = user_has_global_branch_access(user=user)",
			"reader = frappe.get_all if (global_access or assignment_authoritative) else frappe.get_list",
			"if global_access:",
			"return permission_visible",
		):
			self.assertIn(contract, branches_source)

	def test_non_throwing_context_validation_does_not_leak_frappe_permission_modals(self):
		source = self.read("operating_context.py")
		validation_start = source.index("def _validate_context(")
		validation_end = source.index("\n\ndef _get_switch_blockers", validation_start)
		validation_source = source[validation_start:validation_end]
		for contract in (
			'previous_messages = list(getattr(frappe.local, "message_log", []) or []) if not throw else None',
			"finally:",
			"frappe.local.message_log = previous_messages",
		):
			self.assertIn(contract, validation_source)

	def test_context_preview_does_not_clear_valid_session_context(self):
		source = self.read("operating_context.py")
		preview_start = source.index("def preview_operating_context(")
		preview_end = source.index("\n\n@frappe.whitelist()\ndef switch_operating_context", preview_start)
		preview_source = source[preview_start:preview_end]
		self.assertIn("validate_operating_branch", preview_source)
		self.assertIn('source="preview"', preview_source)
		self.assertNotIn("_write_cached_context", preview_source)
		self.assertNotIn("_clear_cached_context", preview_source)
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

	def test_branch_setup_membership_adds_a_server_side_branch_constraint(self):
		source = self.read("operating_context.py")
		for contract in (
			"get_user_branch_profiles(user=user, company=company)",
			"profile_branches = {",
			'row.get("enabled")',
			"if profile_branches:",
			"if branch in profile_branches",
		):
			self.assertIn(contract, source)

	def test_default_context_restore_cannot_bypass_pos_switch_safety(self):
		source = self.read("operating_context.py")
		clear_start = source.index("def clear_operating_context(")
		clear_end = source.index("\n\ndef get_effective_operating_context", clear_start)
		clear_source = source[clear_start:clear_end]
		self.assertIn("_resolve_fallback_context", clear_source)
		self.assertIn("_assert_switch_safe", clear_source)
		self.assertIn("_clear_cached_context", clear_source)
		self.assertLess(clear_source.index("_assert_switch_safe"), clear_source.index("_clear_cached_context"))

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
			"_can_open_operating_context_page",
			'frappe.get_doc("Page", target).is_permitted()',
			'"company": operating.get("company")',
			'"branch": operating.get("branch")',
			'feature_flags["operating_branch_context"] = "phase2_active"',
		):
			self.assertIn(contract, source)

	def test_global_shell_branch_switcher_tracks_authoritative_business_hub_context(self):
		shell = self.read("public/js/retailedge_shell_context.js")
		hub = self.read("public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue")

		for contract in (
			'host.setAttribute("aria-label", "Working branch")',
			"current.branch_options",
			"current.active_branch",
			"current.can_switch_branch",
			"retailedgeSyncShellIdentity",
			"switch_operating_context",
			"userErrorMessage",
		):
			self.assertIn(contract, shell)

		for contract in (
			'window.retailedgeSyncShellIdentity({',
			'active_company: this.context.company || ""',
			'active_branch: this.context.branch || ""',
			"branch_options: Array.isArray(this.context.branch_options)",
			"can_switch_branch: Boolean(this.context.can_switch_branch)",
		):
			self.assertIn(contract, hub)

	def test_operating_context_page_is_edgesuite_and_preserves_switch_contract(self):
		loader = self.read("retailedge/page/operating_context/operating_context.js")
		component = self.read("public/js/operating_context/OperatingContext.vue")
		for contract in (
			'"edgeui.bundle.js"',
			'"operating_context.bundle.js"',
			"window.EdgeSuiteUI",
			"mountRetailEdgeOperatingContext",
		):
			self.assertIn(contract, loader)
		self.assertNotIn('className = "frappe-card"', loader)

		for contract in (
			"get_allowed_operating_contexts",
			"switch_operating_context",
			"clear_operating_context",
			"Operating Company",
			"Operating Branch",
			"onCompanyChange",
			"clientSwitchBlocker",
			"retailedgeOperatingContextGuard",
			"__retailedgeBusinessHubContextCache = null",
			"retailedge-operating-context-changed",
			"EdgePageLayout",
			"EdgePageHeader",
		):
			self.assertIn(contract, component)

	def test_page_fixture_is_customer_facing_and_keeps_internal_route_stable(self):
		source = self.read("retailedge/page/operating_context/operating_context.json")
		self.assertIn('"name": "operating-context"', source)
		self.assertIn('"page_name": "operating-context"', source)
		self.assertIn('"title": "Operating Context"', source)


if __name__ == "__main__":
	unittest.main()
