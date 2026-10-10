from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from retailedge.master_experience import get_retailedge_business_hub_context
from retailedge.operating_context import (
	_clear_cached_context,
	_clear_session_context,
	get_allowed_operating_contexts,
	get_operating_context,
	get_operational_branch_scope,
	switch_operating_context,
)
from retailedge.report_center import get_reports_centre_context
from retailedge.tests.rc3_browser_fixture import (
	BRANCHES,
	_ensure_assignment,
	_ensure_branch,
	_ensure_branch_profile,
	_ensure_warehouse,
)
from retailedge.tests.test_persona_effective_permissions import _ensure_permission_user
from retailedge.tests.upgrade_validation_fixture import COMPANY, _ensure_company


ONE_BRANCH_USER = "isolation-one-branch@example.com"
MULTI_BRANCH_USER = "isolation-multi-branch@example.com"
ZERO_BRANCH_USER = "isolation-zero-branch@example.com"
ISOLATION_USERS = (
	ONE_BRANCH_USER,
	MULTI_BRANCH_USER,
	ZERO_BRANCH_USER,
)
OTHER_COMPANY = "RetailEdge Isolation Other"
OTHER_COMPANY_ABBR = "REIO"
LAGOS, IKEJA, ABUJA = BRANCHES


def _ensure_other_company() -> None:
	if frappe.db.exists("Company", OTHER_COMPANY):
		return
	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": OTHER_COMPANY,
			"abbr": OTHER_COMPANY_ABBR,
			"default_currency": "NGN",
			"country": "Nigeria",
		}
	).insert(ignore_permissions=True)


def _reset_isolation_user(email: str) -> None:
	_ensure_permission_user(email, email.split("@", 1)[0], ("Stock User",))
	frappe.db.delete("RetailEdge Branch Assignment", {"user": email})
	frappe.db.delete("User Permission", {"user": email, "allow": "Company"})
	frappe.db.delete("DefaultValue", {"parent": email, "defkey": "Company"})
	frappe.db.delete("DefaultValue", {"parent": email, "defkey": "company"})
	frappe.defaults.set_user_default("company", COMPANY, user=email)
	frappe.clear_cache(user=email)


def _activate_user(email: str) -> None:
	frappe.set_user(email)
	_clear_session_context()
	_clear_cached_context(user=email)


class PersonaBranchCompanyIsolationTests(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._original_user = frappe.session.user
		frappe.set_user("Administrator")

		_ensure_company()
		_ensure_other_company()

		for branch_name in BRANCHES:
			_ensure_branch(branch_name)
			warehouse = _ensure_warehouse(branch_name)
			_ensure_branch_profile(
				branch_name,
				default_warehouse=warehouse,
				is_default=branch_name == LAGOS,
			)

		for email in ISOLATION_USERS:
			_reset_isolation_user(email)

		_ensure_assignment(
			ONE_BRANCH_USER,
			LAGOS,
			"Stock",
			is_primary=True,
			active=True,
		)
		_ensure_assignment(
			MULTI_BRANCH_USER,
			LAGOS,
			"Stock",
			is_primary=True,
			active=True,
		)
		_ensure_assignment(
			MULTI_BRANCH_USER,
			IKEJA,
			"Stock",
			is_primary=False,
			active=True,
		)
		_ensure_assignment(
			ZERO_BRANCH_USER,
			ABUJA,
			"Stock",
			is_primary=True,
			active=False,
		)

		frappe.clear_cache()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(cls._original_user or "Administrator")
		super().tearDownClass()

	def test_effective_scope_matrix_is_one_multi_and_restricted_zero(self):
		one = get_operational_branch_scope(COMPANY, user=ONE_BRANCH_USER)
		self.assertTrue(one["restricted"])
		self.assertEqual(one["source"], "branch_assignment")
		self.assertEqual(one["allowed_branches"], [LAGOS])

		multi = get_operational_branch_scope(COMPANY, user=MULTI_BRANCH_USER)
		self.assertTrue(multi["restricted"])
		self.assertEqual(multi["source"], "branch_assignment")
		self.assertEqual(set(multi["allowed_branches"]), {LAGOS, IKEJA})

		zero = get_operational_branch_scope(COMPANY, user=ZERO_BRANCH_USER)
		self.assertTrue(zero["restricted"])
		self.assertEqual(zero["source"], "branch_assignment")
		self.assertEqual(zero["allowed_branches"], [])

	def test_operating_options_do_not_leak_unassigned_branches_or_companies(self):
		_activate_user(ONE_BRANCH_USER)
		one = get_allowed_operating_contexts()
		self.assertEqual(one["companies"], [COMPANY])
		self.assertEqual(one["branches"], [LAGOS])
		self.assertEqual(one["selected_company"], COMPANY)

		_activate_user(MULTI_BRANCH_USER)
		multi = get_allowed_operating_contexts()
		self.assertEqual(multi["companies"], [COMPANY])
		self.assertEqual(set(multi["branches"]), {LAGOS, IKEJA})
		self.assertEqual(multi["selected_company"], COMPANY)

		_activate_user(ZERO_BRANCH_USER)
		zero = get_allowed_operating_contexts()
		self.assertEqual(zero["companies"], [])
		self.assertEqual(zero["branches"], [])
		self.assertEqual(zero["selected_company"], "")
		self.assertEqual(zero["current"].get("company"), "")
		self.assertEqual(zero["current"].get("branch"), "")

	def test_existing_unassigned_company_is_denied_for_restricted_personas(self):
		self.assertTrue(bool(frappe.db.exists("Company", OTHER_COMPANY)))
		for email in ISOLATION_USERS:
			with self.subTest(user=email):
				_activate_user(email)
				with self.assertRaises(frappe.PermissionError):
					get_allowed_operating_contexts(company=OTHER_COMPANY)

	def test_explicit_branch_switching_stays_inside_assignment_scope(self):
		_activate_user(ONE_BRANCH_USER)
		one = switch_operating_context(COMPANY, LAGOS)
		self.assertEqual(one["branch"], LAGOS)
		with self.assertRaises(frappe.PermissionError):
			switch_operating_context(COMPANY, IKEJA)

		_activate_user(MULTI_BRANCH_USER)
		ikeja = switch_operating_context(COMPANY, IKEJA)
		self.assertEqual(ikeja["branch"], IKEJA)
		lagos = switch_operating_context(COMPANY, LAGOS)
		self.assertEqual(lagos["branch"], LAGOS)

		_activate_user(ZERO_BRANCH_USER)
		with self.assertRaises(frappe.PermissionError):
			switch_operating_context(COMPANY, LAGOS)

	def test_business_hub_context_exposes_only_effective_branch_scope(self):
		expected = {
			ONE_BRANCH_USER: (COMPANY, LAGOS, {LAGOS}, False),
			MULTI_BRANCH_USER: (COMPANY, LAGOS, {LAGOS, IKEJA}, True),
			ZERO_BRANCH_USER: ("", "", set(), False),
		}
		for email, (company, branch, branch_options, can_switch) in expected.items():
			with self.subTest(user=email):
				_activate_user(email)
				context = get_retailedge_business_hub_context().get("context") or {}
				self.assertEqual(context.get("company") or "", company)
				self.assertEqual(context.get("branch") or "", branch)
				self.assertEqual(set(context.get("branch_options") or []), branch_options)
				self.assertEqual(bool(context.get("can_switch_branch")), can_switch)

	def test_reports_centre_context_preserves_resolved_identity_without_scope_expansion(self):
		expected = {
			ONE_BRANCH_USER: (COMPANY, LAGOS),
			MULTI_BRANCH_USER: (COMPANY, LAGOS),
			ZERO_BRANCH_USER: ("", ""),
		}
		for email, (company, branch) in expected.items():
			with self.subTest(user=email):
				_activate_user(email)
				context = get_reports_centre_context().get("context") or {}
				self.assertEqual(context.get("company") or "", company)
				self.assertEqual(context.get("branch") or "", branch)
				self.assertNotIn("branch_options", context)
				self.assertNotIn("company_options", context)

	def test_passive_fallback_context_uses_primary_only_when_active(self):
		_activate_user(ONE_BRANCH_USER)
		one = get_operating_context()
		self.assertEqual((one.get("company"), one.get("branch")), (COMPANY, LAGOS))

		_activate_user(MULTI_BRANCH_USER)
		multi = get_operating_context()
		self.assertEqual((multi.get("company"), multi.get("branch")), (COMPANY, LAGOS))

		_activate_user(ZERO_BRANCH_USER)
		zero = get_operating_context()
		self.assertEqual((zero.get("company"), zero.get("branch")), ("", ""))
