from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from retailedge.master_experience import get_retailedge_business_hub_context
from retailedge.patches.ensure_retailedge_cashier_company_read import execute as ensure_cashier_company_read
from retailedge.patches.ensure_retailedge_cashier_operational_permissions import execute as ensure_cashier_operational_permissions
from retailedge.patches.ensure_retailedge_manager_payment_entry_read import execute as ensure_manager_payment_entry_read
from retailedge.report_center import get_reports_centre_context
from retailedge.setup_roles import ensure_retailedge_roles
from retailedge.tests.rc3_browser_fixture import (
	BRANCHES,
	_ensure_assignment,
	_ensure_branch,
	_ensure_branch_profile,
	_ensure_warehouse,
)
from retailedge.tests.test_persona_effective_permissions import PERSONAS, _ensure_permission_user
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_transaction_masters,
)


BUSINESS_HUB_USERS = (
	"permission-cashier@example.com",
	"permission-retail-manager@example.com",
	"permission-branch-manager@example.com",
	"permission-accounts@example.com",
	"permission-stock@example.com",
)
REPORTS_CENTRE_USERS = (*BUSINESS_HUB_USERS, "permission-auditor@example.com")
BRANCH_SCOPED_PERSONAS = {
	"permission-branch-manager@example.com": "Manager",
	"permission-auditor@example.com": "Auditor",
}


class PersonaPageApiAccessTests(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._original_user = frappe.session.user
		frappe.set_user("Administrator")

		ensure_retailedge_roles(migrate_alias_assignments=True)
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()
		ensure_cashier_company_read()
		ensure_cashier_operational_permissions()
		ensure_manager_payment_entry_read()

		for email, (first_name, roles) in PERSONAS.items():
			_ensure_permission_user(email, first_name, roles)

		# Branch Manager and Auditor are intentionally branch-scoped product roles,
		# not global Company roles. Give these page/API personas one deterministic
		# active assignment instead of widening native Company permission.
		branch = BRANCHES[0]
		_ensure_branch(branch)
		warehouse = _ensure_warehouse(branch)
		_ensure_branch_profile(branch, default_warehouse=warehouse, is_default=False)
		for email, branch_role in BRANCH_SCOPED_PERSONAS.items():
			_ensure_assignment(
				email,
				branch,
				branch_role,
				is_primary=True,
				active=True,
			)

		frappe.clear_cache()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(cls._original_user or "Administrator")
		super().tearDownClass()

	def test_business_hub_page_is_available_to_operational_personas(self):
		for user in BUSINESS_HUB_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				self.assertTrue(bool(frappe.get_doc("Page", "retailedge-business-hub").is_permitted()))

	def test_auditor_does_not_gain_business_hub_page_access(self):
		frappe.set_user("permission-auditor@example.com")
		self.assertFalse(bool(frappe.get_doc("Page", "retailedge-business-hub").is_permitted()))

	def test_reports_centre_page_is_available_to_review_personas(self):
		for user in REPORTS_CENTRE_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				self.assertTrue(bool(frappe.get_doc("Page", "reports-centre").is_permitted()))

	def test_branch_scoped_page_personas_do_not_gain_native_company_read(self):
		for user in BRANCH_SCOPED_PERSONAS:
			with self.subTest(user=user):
				self.assertFalse(bool(frappe.has_permission("Company", ptype="read", user=user)))

	def test_business_hub_context_loads_without_requiring_write_authority(self):
		for user in BUSINESS_HUB_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				context = get_retailedge_business_hub_context()
				self.assertIsInstance(context, dict)
				self.assertIsInstance(context.get("navigation_groups"), list)

	def test_reports_centre_context_loads_without_requiring_write_authority(self):
		for user in REPORTS_CENTRE_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				context = get_reports_centre_context()
				self.assertIsInstance(context, dict)
				self.assertIsInstance(context.get("groups"), list)
