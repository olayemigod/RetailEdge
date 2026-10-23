from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from retailedge.navigation_consolidation import get_retailedge_business_hub_context
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
	"permission-sales@example.com",
	"permission-purchase@example.com",
)
REPORTS_CENTRE_USERS = (*BUSINESS_HUB_USERS, "permission-auditor@example.com")
BRANCH_SCOPED_PERSONAS = {
	"permission-branch-manager@example.com": "Manager",
	"permission-auditor@example.com": "Auditor",
}

ROLE_PAGE_EXPECTATIONS = {
	"permission-cashier@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "make-sale", "cashier-expenses", "expense-register"},
		"denied": {"professional-selling", "professional-purchasing", "record-purchase", "stock-position", "transfer-stock", "banking-readiness", "payment-management", "retail-settings"},
	},
	"permission-retail-manager@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "make-sale", "professional-selling", "sales-invoice-register", "record-purchase", "purchase-register", "stock-position", "transfer-stock", "stock-adjustment", "banking-readiness", "branch-assignments"},
		"denied": {"professional-purchasing", "payment-management", "retail-settings"},
	},
	"permission-branch-manager@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "make-sale", "professional-selling", "sales-invoice-register", "record-purchase", "purchase-register", "stock-position", "transfer-stock", "stock-adjustment", "banking-readiness", "branch-assignments"},
		"denied": {"professional-purchasing", "payment-management", "retail-settings"},
	},
	"permission-auditor@example.com": {
		"allowed": {"reports-centre", "sales-invoice-register", "purchase-register", "stock-position", "cashier-expenses", "expense-register", "branch-assignments"},
		"denied": {"retailedge-business-hub", "make-sale", "professional-selling", "professional-purchasing", "record-purchase", "transfer-stock", "stock-adjustment", "banking-readiness", "payment-management", "retail-settings"},
	},
	"permission-accounts@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "make-sale", "professional-selling", "sales-invoice-register", "professional-purchasing", "record-purchase", "purchase-register", "cashier-expenses", "expense-register", "banking-readiness", "payment-management"},
		"denied": {"stock-position", "transfer-stock", "stock-adjustment", "retail-settings"},
	},
	"permission-stock@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "stock-position", "transfer-stock", "stock-adjustment"},
		"denied": {"make-sale", "professional-selling", "sales-invoice-register", "professional-purchasing", "record-purchase", "purchase-register", "banking-readiness", "payment-management", "retail-settings"},
	},
	"permission-sales@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "make-sale", "professional-selling", "sales-invoice-register"},
		"denied": {"professional-purchasing", "record-purchase", "purchase-register", "stock-position", "transfer-stock", "stock-adjustment", "banking-readiness", "payment-management", "retail-settings"},
	},
	"permission-purchase@example.com": {
		"allowed": {"retailedge-business-hub", "reports-centre", "professional-purchasing", "record-purchase", "purchase-register"},
		"denied": {"make-sale", "professional-selling", "sales-invoice-register", "stock-position", "transfer-stock", "stock-adjustment", "banking-readiness", "payment-management", "retail-settings"},
	},
	"permission-no-access@example.com": {
		"allowed": set(),
		"denied": {"retailedge-business-hub", "reports-centre", "make-sale", "professional-selling", "sales-invoice-register", "professional-purchasing", "record-purchase", "purchase-register", "stock-position", "transfer-stock", "stock-adjustment", "cashier-expenses", "expense-register", "banking-readiness", "payment-management", "branch-assignments", "retail-settings"},
	},
}


def _reset_branch_scoped_company_context(user: str) -> None:
	"""Keep dedicated QA users deterministic without adding Company User Permission scope."""
	frappe.db.delete("User Permission", {"user": user, "allow": "Company"})
	frappe.defaults.clear_user_default("Company", user=user)
	frappe.defaults.clear_user_default("company", user=user)
	# Company is a Frappe permission-key. get_user_default("Company") resolves
	# the scrubbed `company` default before falling back to User Permission data.
	frappe.defaults.set_user_default("company", COMPANY, user=user)
	frappe.clear_cache(user=user)


class PersonaPageApiAccessTests(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._original_user = frappe.session.user
		frappe.set_user("Administrator")

		ensure_retailedge_roles()
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()
		ensure_cashier_company_read()
		ensure_cashier_operational_permissions()
		ensure_manager_payment_entry_read()

		for email, (first_name, roles) in PERSONAS.items():
			_ensure_permission_user(email, first_name, roles)

		# Branch Manager and Auditor remain branch-scoped product roles. Their
		# read-only Company context comes from RetailEdge role setup, while Branch
		# Assignment controls the working branch; do not add Company User Permission.
		branch = BRANCHES[0]
		_ensure_branch(branch)
		warehouse = _ensure_warehouse(branch)
		_ensure_branch_profile(branch, default_warehouse=warehouse, is_default=False)
		for email, branch_role in BRANCH_SCOPED_PERSONAS.items():
			_reset_branch_scoped_company_context(email)
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

	def test_branch_scoped_page_personas_get_read_only_company_context_without_user_permission(self):
		for user in BRANCH_SCOPED_PERSONAS:
			with self.subTest(user=user):
				self.assertTrue(bool(frappe.has_permission("Company", ptype="read", user=user)))
				for permission_type in ("write", "create", "delete"):
					self.assertFalse(bool(frappe.has_permission("Company", ptype=permission_type, user=user)))
				self.assertEqual(frappe.defaults.get_user_default("Company", user=user), COMPANY)
				self.assertFalse(
					bool(frappe.db.exists("User Permission", {"user": user, "allow": "Company"}))
				)

	def test_business_hub_context_loads_without_requiring_write_authority(self):
		for user in BUSINESS_HUB_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				context = get_retailedge_business_hub_context()
				self.assertIsInstance(context, dict)
				self.assertIsInstance(context.get("navigation_groups"), list)
				if user in BRANCH_SCOPED_PERSONAS:
					self.assertEqual(context.get("context", {}).get("company"), COMPANY)
					self.assertTrue(context.get("context", {}).get("branch"))

	def test_auditor_can_load_shared_shell_context_without_business_hub_page_access(self):
		frappe.set_user("permission-auditor@example.com")
		self.assertFalse(bool(frappe.get_doc("Page", "retailedge-business-hub").is_permitted()))
		context = get_retailedge_business_hub_context()
		self.assertIsInstance(context.get("navigation_groups"), list)
		self.assertTrue(
			any(
				item.get("target") == "reports-centre"
				for group in context.get("navigation_groups") or []
				for item in group.get("items") or []
			)
		)

	def test_reports_centre_context_loads_without_requiring_write_authority(self):
		for user in REPORTS_CENTRE_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				context = get_reports_centre_context()
				self.assertIsInstance(context, dict)
				self.assertIsInstance(context.get("groups"), list)
				if user in BRANCH_SCOPED_PERSONAS:
					self.assertEqual(context.get("context", {}).get("company"), COMPANY)
					self.assertTrue(context.get("context", {}).get("branch"))


	def test_role_page_matrix_allows_expected_modules_and_denies_unrelated_modules(self):
		for user, expectation in ROLE_PAGE_EXPECTATIONS.items():
			frappe.set_user(user)
			for page_name in expectation["allowed"]:
				with self.subTest(user=user, page=page_name, expected="allowed"):
					self.assertTrue(bool(frappe.get_doc("Page", page_name).is_permitted()))
			for page_name in expectation["denied"]:
				with self.subTest(user=user, page=page_name, expected="denied"):
					self.assertFalse(bool(frappe.get_doc("Page", page_name).is_permitted()))

	def test_direct_context_apis_deny_user_without_product_page_access(self):
		frappe.set_user("permission-no-access@example.com")
		with self.assertRaises(frappe.PermissionError):
			get_retailedge_business_hub_context()
		with self.assertRaises(frappe.PermissionError):
			get_reports_centre_context()

	def test_advanced_native_desk_exposure_is_explicit(self):
		frappe.set_user("permission-global-manager@example.com")
		manager_context = get_retailedge_business_hub_context()
		self.assertTrue(bool(manager_context.get("access", {}).get("can_use_native_desk")))

		for user in BUSINESS_HUB_USERS:
			with self.subTest(user=user):
				frappe.set_user(user)
				context = get_retailedge_business_hub_context()
				self.assertFalse(bool(context.get("access", {}).get("can_use_native_desk")))
