from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from retailedge import user_onboarding


USER = "cashier@example.com"
COMPANY = "RetailEdge Consulting"
BRANCH = "Ketu"
APP_ROOT = Path(__file__).resolve().parents[1]
WIZARD_VUE = APP_ROOT / "public" / "js" / "retailedge_setup" / "UserOnboardingManager.vue"
SETUP_VUE = APP_ROOT / "public" / "js" / "retailedge_setup" / "RetailEdgeSetup.vue"
SETUP_PY = APP_ROOT / "retailedge" / "page" / "retailedge_setup" / "retailedge_setup.py"


def payload(**overrides):
	values = {
		"mode": "existing",
		"user": USER,
		"role": "RetailEdgeCashier",
		"branch_role": "Cashier",
		"company": COMPANY,
		"branch": BRANCH,
		"effective_from": "2026-10-23",
		"is_primary": True,
		"requires_pos": False,
		"send_welcome_email": False,
	}
	values.update(overrides)
	return values


class TestUserOnboardingWizard(unittest.TestCase):
	def test_payload_normalizes_governed_values(self):
		result = user_onboarding._parse_payload(payload(is_primary=True, requires_pos=False))
		self.assertEqual(result["role"], "RetailEdgeCashier")
		self.assertEqual(result["branch_role"], "Cashier")
		self.assertEqual(result["company"], COMPANY)
		self.assertEqual(result["branch"], BRANCH)
		self.assertEqual(result["is_primary"], 1)
		self.assertEqual(result["requires_pos"], 0)

	def test_payload_rejects_non_retailedge_role(self):
		with self.assertRaises(frappe.ValidationError):
			user_onboarding._parse_payload(payload(role="Accounts User"))

	def test_payload_requires_company_and_branch(self):
		with self.assertRaises(frappe.ValidationError):
			user_onboarding._parse_payload(payload(company=""))
		with self.assertRaises(frappe.ValidationError):
			user_onboarding._parse_payload(payload(branch=""))

	@patch("retailedge.user_onboarding.create_branch_assignment")
	@patch("retailedge.user_onboarding._assert_assignment_create")
	@patch("retailedge.user_onboarding.get_active_branch_assignments")
	def test_matching_active_assignment_is_reused_without_create_permission(
		self, mock_assignments, mock_assert_create, mock_create
	):
		mock_assignments.return_value = [frappe._dict(name="RE-BA-0001", company=COMPANY, branch=BRANCH)]
		name, created = user_onboarding._ensure_branch_assignment(user=USER, values=payload())
		self.assertEqual(name, "RE-BA-0001")
		self.assertFalse(created)
		mock_assert_create.assert_not_called()
		mock_create.assert_not_called()

	@patch("retailedge.user_onboarding.create_branch_assignment")
	@patch("retailedge.user_onboarding._assert_assignment_create")
	@patch("retailedge.user_onboarding.get_active_branch_assignments")
	def test_different_active_branch_blocks_silent_transfer(self, mock_assignments, mock_assert_create, mock_create):
		mock_assignments.return_value = [frappe._dict(name="RE-BA-0001", company=COMPANY, branch="Ikeja")]
		with self.assertRaises(frappe.ValidationError):
			user_onboarding._ensure_branch_assignment(user=USER, values=payload())
		mock_assert_create.assert_not_called()
		mock_create.assert_not_called()

	@patch("retailedge.user_onboarding.frappe.get_doc")
	@patch("retailedge.user_onboarding._profile_summary")
	def test_shared_pos_profile_stays_shared(self, mock_profile_summary, mock_get_doc):
		mock_profile_summary.return_value = {
			"configured": True,
			"default_pos_profile": "POS-KETU",
			"pos_required_supported": True,
			"pos_access_mode": "shared",
			"pos_assigned": False,
		}
		result = user_onboarding._ensure_pos_access(user=USER, company=COMPANY, branch=BRANCH)
		self.assertEqual(result["access"], "shared")
		self.assertFalse(result["changed"])
		mock_get_doc.assert_not_called()

	@patch("retailedge.user_onboarding.frappe.get_doc")
	@patch("retailedge.user_onboarding.frappe.has_permission")
	@patch("retailedge.user_onboarding.get_exact_branch_profile")
	def test_non_pos_branch_review_does_not_require_pos_profile_read(
		self, mock_branch_profile, mock_has_permission, mock_get_doc
	):
		mock_branch_profile.return_value = frappe._dict(name="RE-BP-0001", default_pos_profile="POS-KETU")

		def permission(doctype, ptype, **_kwargs):
			if doctype == "RetailEdge Branch Profile" and ptype == "read":
				return True
			if doctype == "POS Profile" and ptype == "read":
				return False
			return False

		mock_has_permission.side_effect = permission
		result = user_onboarding._profile_summary(company=COMPANY, branch=BRANCH, user=USER)
		self.assertTrue(result["configured"])
		self.assertEqual(result["default_pos_profile"], "POS-KETU")
		self.assertEqual(result["pos_access_mode"], "unavailable")
		self.assertFalse(result["pos_required_supported"])
		mock_get_doc.assert_not_called()

	def test_role_profile_is_not_bypassed(self):
		user_doc = MagicMock()
		user_doc.get.side_effect = lambda key: (
			[frappe._dict(role="Sales User")] if key == "roles" else [frappe._dict(role_profile="Store Staff")]
		)
		with self.assertRaises(frappe.ValidationError):
			user_onboarding._ensure_retailedge_role(user_doc, "RetailEdgeCashier")
		user_doc.append.assert_not_called()
		user_doc.save.assert_not_called()

	@patch("retailedge.user_onboarding.get_retailedge_user_readiness")
	@patch("retailedge.user_onboarding._ensure_pos_access")
	@patch("retailedge.user_onboarding._ensure_branch_assignment")
	@patch("retailedge.user_onboarding._ensure_retailedge_role")
	@patch("retailedge.user_onboarding._resolve_or_create_user")
	@patch("retailedge.user_onboarding._profile_summary")
	@patch("retailedge.user_onboarding._assert_onboarding_read")
	def test_non_pos_completion_does_not_mutate_pos(
		self,
		_assert_read,
		mock_profile,
		mock_resolve_user,
		mock_role,
		mock_assignment,
		mock_pos,
		mock_readiness,
	):
		mock_profile.return_value = {
			"configured": True,
			"default_pos_profile": "POS-KETU",
			"pos_required_supported": False,
			"pos_access_mode": "unavailable",
		}
		mock_resolve_user.return_value = (SimpleNamespace(name=USER, full_name="QA Cashier"), False)
		mock_role.return_value = True
		mock_assignment.return_value = ("RE-BA-0001", True)
		mock_readiness.return_value = {"ready": True, "status": "Ready", "reasons": []}

		result = user_onboarding.complete_user_onboarding(payload(requires_pos=False))
		self.assertTrue(result["readiness"]["ready"])
		self.assertEqual(result["pos"]["access"], "not_required")
		mock_pos.assert_not_called()

	@patch("retailedge.user_onboarding._resolve_or_create_user")
	@patch("retailedge.user_onboarding._profile_summary")
	@patch("retailedge.user_onboarding._assert_onboarding_read")
	def test_pos_requirement_is_validated_before_any_user_write(self, _assert_read, mock_profile, mock_resolve_user):
		mock_profile.return_value = {
			"configured": True,
			"default_pos_profile": "POS-KETU",
			"pos_required_supported": False,
			"pos_message": "You do not have permission to review the Branch POS Profile.",
		}
		with self.assertRaises(frappe.ValidationError):
			user_onboarding.complete_user_onboarding(payload(requires_pos=True))
		mock_resolve_user.assert_not_called()

	def test_service_has_no_parallel_permission_or_default_shortcuts(self):
		source = Path(user_onboarding.__file__).read_text(encoding="utf-8")
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("get_retailedge_user_readiness", source)
		self.assertIn("create_branch_assignment", source)
		for forbidden in (
			"ignore_permissions=True",
			"frappe.db.commit",
			"frappe.defaults.set_user_default",
			"add_user_permission",
			'frappe.new_doc("User Permission")',
		):
			self.assertNotIn(forbidden, source)

	def test_setup_exposes_guided_user_onboarding_manager(self):
		setup_py = SETUP_PY.read_text(encoding="utf-8")
		setup_vue = SETUP_VUE.read_text(encoding="utf-8")
		self.assertIn('"key": "user-onboarding"', setup_py)
		self.assertIn('"manager": "user-onboarding"', setup_py)
		self.assertIn("UserOnboardingManager", setup_vue)
		self.assertIn("openUserOnboardingManager", setup_vue)

	def test_wizard_uses_edgesuite_fields_and_required_five_business_stages(self):
		source = WIZARD_VUE.read_text(encoding="utf-8")
		for component in ("EdgeLinkField", "EdgeDropdown", "EdgeInput", "EdgeCheckbox"):
			self.assertIn(component, source)
		for label in ("Person", "Access", "Location", "Point of Sale", "Review"):
			self.assertIn(f'label: "{label}"', source)
		self.assertIn("Step {{ step }} of {{ steps.length }}", source)
		self.assertIn("This User will work at Point of Sale", source)
		self.assertIn("Existing shared access will be preserved.", source)

	def test_company_change_clears_dependent_branch(self):
		source = WIZARD_VUE.read_text(encoding="utf-8")
		self.assertIn('this.form.company = next;', source)
		self.assertIn('this.form.branch = "";', source)
		self.assertIn('searchBranch(query) { return this.search("branch", query, { company: this.form.company }); }', source)


if __name__ == "__main__":
	unittest.main()
