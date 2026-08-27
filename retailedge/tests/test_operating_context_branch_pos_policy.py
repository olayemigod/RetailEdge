from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestOperatingContextBranchPosPolicy(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_branch_setup_is_company_branch_authority_even_for_global_users(self):
		source = self.read("operating_context.py")
		for contract in (
			"get_enabled_branch_profiles",
			"configured_branches",
			"Branch Setup is the RetailEdge Company→Branch binding",
			"if configured_branches:",
			"if user_has_global_branch_access(user=user):",
			"get_allowed_operating_branches",
			"validate_operating_branch",
			"Branch {0} is not configured for Company {1}",
		):
			self.assertIn(contract, source)
		self.assertLess(
			source.index("if configured_branches:"),
			source.index("if user_has_global_branch_access(user=user):"),
		)

	def test_branch_setup_pos_profile_remains_optional_at_schema_level(self):
		path = (
			APP_ROOT
			/ "retailedge"
			/ "doctype"
			/ "retailedge_branch_profile"
			/ "retailedge_branch_profile.json"
		)
		payload = json.loads(path.read_text(encoding="utf-8"))
		field = next(row for row in payload["fields"] if row.get("fieldname") == "default_pos_profile")
		self.assertNotEqual(field.get("reqd"), 1)

	def test_pos_entitlement_is_explicit_erpnext_pos_profile_user_assignment(self):
		source = self.read("branch_profile.py")
		for contract in (
			"def get_user_pos_profiles(",
			'"POS Profile User"',
			'filters={"user": user, "parenttype": "POS Profile"}',
			"Generic permission to read/administer POS Profile is deliberately not treated",
			"def user_has_pos_profile_assignment(",
			"def resolve_branch_pos_requirement(",
		):
			self.assertIn(contract, source)
		entitlement = source[source.index("def get_user_pos_profiles("):source.index("def user_has_pos_profile_assignment(")]
		self.assertNotIn('frappe.has_permission("POS Profile", "read")', entitlement)

	def test_pos_enabled_user_must_have_matching_branch_setup_profile(self):
		source = self.read("branch_profile.py")
		for contract in (
			"No POS Profile is configured for your access in Branch",
			"belongs to another Company",
			"You are not assigned to the POS Profile configured for Branch",
			'result["pos_ready"] = False',
			'result["pos_profile"] = pos_profile',
		):
			self.assertIn(contract, source)

		operating = self.read("operating_context.py")
		self.assertIn('pos_state.get("pos_required") and not pos_state.get("pos_ready")', operating)
		self.assertIn('"pos_profile_required"', operating)

	def test_operating_context_ui_blocks_invalid_required_pos_context(self):
		component = self.read("public/js/operating_context/OperatingContext.vue")
		for contract in (
			"preview_operating_context",
			"onBranchChange",
			"posRequired",
			"posProfile",
			"posReady",
			"posMessage",
			"(posRequired && !posReady)",
			"Required POS access",
		):
			self.assertIn(contract, component)

	def test_guided_and_professional_selling_share_operating_branch_policy(self):
		guided = self.read("guided_sales_invoice.py")
		professional = self.read("professional_selling.py")
		resolver = self.read("guided_entry_context.py")
		preview = self.read("new_document_defaults.py")

		for source in (guided, professional):
			self.assertIn("get_allowed_operating_branches", source)
			self.assertIn("validate_operating_branch", source)

		self.assertIn("validate_operating_branch", resolver)
		self.assertIn("validate_operating_branch", preview)

	def test_new_policy_keeps_accounting_and_document_safety_boundaries(self):
		for relative in (
			"operating_context.py",
			"guided_entry_context.py",
			"professional_selling.py",
			"new_document_defaults.py",
		):
			source = self.read(relative)
			self.assertNotIn("ignore_permissions=True", source)
			self.assertNotIn("frappe.db.commit(", source)
			self.assertNotIn(".submit()", source)


if __name__ == "__main__":
	unittest.main()
