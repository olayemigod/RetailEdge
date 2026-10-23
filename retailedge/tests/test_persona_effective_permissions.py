from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from retailedge.patches.ensure_retailedge_cashier_company_read import execute as ensure_cashier_company_read
from retailedge.patches.ensure_retailedge_cashier_operational_permissions import execute as ensure_cashier_operational_permissions
from retailedge.patches.ensure_retailedge_manager_payment_entry_read import execute as ensure_manager_payment_entry_read
from retailedge.setup_roles import MANAGEMENT_READ_DOCTYPES, ensure_retailedge_roles
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_transaction_masters,
)


PERSONAS = {
	"permission-cashier@example.com": ("Permission Cashier", ("RetailEdgeCashier",)),
	"permission-retail-manager@example.com": ("Permission Retail Manager", ("RetailEdgeManager",)),
	"permission-branch-manager@example.com": ("Permission Branch Manager", ("RetailEdgeBranchManager",)),
	"permission-auditor@example.com": ("Permission Auditor", ("RetailEdgeAuditor",)),
	"permission-accounts@example.com": ("Permission Accounts", ("Accounts User",)),
	"permission-stock@example.com": ("Permission Stock", ("Stock User",)),
	"permission-sales@example.com": ("Permission Sales", ("Sales User",)),
	"permission-purchase@example.com": ("Permission Purchase", ("Purchase User",)),
	"permission-no-access@example.com": ("Permission No Access", ()),
	"permission-global-manager@example.com": (
		"Permission Global Manager",
		("System Manager", "Sales Manager", "Accounts Manager", "Stock Manager", "Purchase Manager"),
	),
}


MUTATION_PERMISSIONS = {
	"create": False,
	"write": False,
	"submit": False,
	"cancel": False,
	"delete": False,
}


def _ensure_permission_user(email: str, first_name: str, roles: tuple[str, ...]) -> None:
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)

	# Permission personas must remain role-exact. Preserving an accidental extra
	# role would make negative permission assertions meaningless.
	user.set("roles", [{"role": role} for role in dict.fromkeys(roles)])
	user.enabled = 1
	user.user_type = "System User"
	if user.meta.has_field("edgesuite_desk_access_level"):
		user.edgesuite_desk_access_level = (
			"Native Desk + EdgeSuite" if "System Manager" in roles else "EdgeSuite Only"
		)
	user.save(ignore_permissions=True)
	frappe.defaults.set_user_default("Company", COMPANY, user=email)
	frappe.clear_cache(user=email)


class PersonaEffectivePermissionTests(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._original_user = frappe.session.user
		frappe.set_user("Administrator")

		ensure_retailedge_roles()
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()

		# Execute the idempotent product permission repairs so this test verifies
		# their effective Frappe result instead of only their source text.
		ensure_cashier_company_read()
		ensure_cashier_operational_permissions()
		ensure_manager_payment_entry_read()

		for email, (first_name, roles) in PERSONAS.items():
			_ensure_permission_user(email, first_name, roles)

		frappe.clear_cache()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(cls._original_user or "Administrator")
		super().tearDownClass()

	def assert_permissions(self, user: str, doctype: str, expected: dict[str, bool]) -> None:
		for permission_type, allowed in expected.items():
			with self.subTest(user=user, doctype=doctype, permission_type=permission_type):
				actual = bool(
					frappe.has_permission(
						doctype,
						ptype=permission_type,
						user=user,
					)
				)
				self.assertEqual(actual, allowed)

	def test_permission_personas_are_role_exact(self):
		for email, (_first_name, expected_roles) in PERSONAS.items():
			with self.subTest(user=email):
				actual_roles = {row.role for row in frappe.get_doc("User", email).roles}
				self.assertEqual(actual_roles, set(expected_roles))

	def test_cashier_has_sales_authority_without_accounting_posting_authority(self):
		user = "permission-cashier@example.com"
		self.assert_permissions(user, "Company", {"read": True, "write": False, "create": False})
		self.assert_permissions(user, "Customer", {"read": True, "write": False, "create": False})
		self.assert_permissions(
			user,
			"Sales Invoice",
			{
				"read": True,
				"create": True,
				"write": True,
				"submit": True,
				"cancel": False,
				"delete": False,
				"amend": False,
			},
		)
		for doctype in ("Payment Entry", "Journal Entry", "Purchase Invoice"):
			self.assert_permissions(
				user,
				doctype,
				{"read": False, "create": False, "write": False, "submit": False, "cancel": False},
			)

	def test_retailedge_management_roles_get_only_context_master_read_by_default(self):
		users = (
			"permission-retail-manager@example.com",
			"permission-branch-manager@example.com",
			"permission-auditor@example.com",
		)
		self.assertEqual(MANAGEMENT_READ_DOCTYPES, ("Company",))
		for user in users:
			for doctype in MANAGEMENT_READ_DOCTYPES:
				with self.subTest(user=user, doctype=doctype):
					self.assert_permissions(
						user,
						doctype,
						{"read": True, "select": True, **MUTATION_PERMISSIONS},
					)

	def test_retailedge_management_roles_do_not_override_native_transaction_visibility(self):
		for user in (
			"permission-retail-manager@example.com",
			"permission-branch-manager@example.com",
			"permission-auditor@example.com",
		):
			for doctype in ("Quotation", "Sales Invoice", "Purchase Invoice", "Stock Entry"):
				with self.subTest(user=user, doctype=doctype):
					self.assert_permissions(user, doctype, {"read": False})

	def test_retailedge_managers_do_not_gain_journal_entry_posting_authority(self):
		for user in (
			"permission-retail-manager@example.com",
			"permission-branch-manager@example.com",
			"permission-auditor@example.com",
		):
			self.assert_permissions(
				user,
				"Journal Entry",
				{"read": False, "create": False, "write": False, "submit": False, "cancel": False},
			)

	def test_global_native_manager_composition_can_read_business_documents(self):
		user = "permission-global-manager@example.com"
		for doctype in (
			"Quotation",
			"Sales Order",
			"Delivery Note",
			"Sales Invoice",
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
			"Stock Entry",
			"Stock Reconciliation",
			"Payment Entry",
		):
			self.assert_permissions(user, doctype, {"read": True})

	def test_native_accounts_user_retains_erpnext_read_access(self):
		user = "permission-accounts@example.com"
		for doctype in ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Journal Entry"):
			self.assert_permissions(user, doctype, {"read": True})

	def test_native_stock_user_retains_erpnext_read_access(self):
		user = "permission-stock@example.com"
		for doctype in ("Item", "Warehouse", "Stock Entry"):
			self.assert_permissions(user, doctype, {"read": True})


	def test_native_sales_user_retains_sales_workflow_authority_only(self):
		user = "permission-sales@example.com"
		for doctype in ("Quotation", "Sales Order", "Delivery Note"):
			self.assert_permissions(user, doctype, {"read": True, "create": True, "write": True})
		for doctype in ("Sales Invoice", "Purchase Order", "Purchase Invoice", "Stock Entry", "Journal Entry"):
			self.assert_permissions(user, doctype, {"read": False, "create": False})

	def test_native_purchase_user_retains_purchase_workflow_authority_only(self):
		user = "permission-purchase@example.com"
		for doctype in ("Supplier Quotation", "Purchase Order", "Purchase Receipt"):
			self.assert_permissions(user, doctype, {"read": True, "create": True, "write": True})
		self.assert_permissions(user, "Purchase Invoice", {"read": True, "create": False, "write": False})
		for doctype in ("Quotation", "Sales Order", "Stock Entry", "Journal Entry"):
			self.assert_permissions(user, doctype, {"read": False, "create": False})

	def test_no_access_user_has_no_retailedge_or_native_transaction_authority(self):
		user = "permission-no-access@example.com"
		for doctype in (
			"Company",
			"Sales Invoice",
			"Purchase Invoice",
			"Stock Entry",
			"Payment Entry",
			"Journal Entry",
		):
			self.assert_permissions(user, doctype, {"read": False, "create": False, "write": False})
