from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from retailedge.cashier_expense_accounting import post_cashier_expense_to_accounts
from retailedge.managed_review_reports import run_review_report
from retailedge.patches.ensure_retailedge_cashier_company_read import execute as ensure_cashier_company_read
from retailedge.tests.browser_persona_fixture import _ensure_user
from retailedge.tests.rc3_browser_fixture import (
	_ensure_assignment,
	_ensure_branch,
	_ensure_branch_profile,
)
from retailedge.tests.upgrade_validation_fixture import (
	COMPANY,
	_ensure_company,
	_ensure_fiscal_year,
	_ensure_transaction_masters,
	_first_cost_center,
	_first_leaf_account,
)
from retailedge.user_readiness import get_retailedge_user_readiness

BRANCH = "RetailEdge QA Cashier Closure"
CASHIER = "qa-cashier-closure@example.com"
POSTER = "qa-cashier-poster@example.com"
EXPENSE_CATEGORY = "RetailEdge QA Cashier Closure Expense"


def _direct_posting_settings() -> SimpleNamespace:
	return SimpleNamespace(
		enable_cashier_expense_workflow=1,
		require_open_shift_for_cashier_expense=0,
		allow_cashier_expense_without_cash_account=0,
		allow_cashier_expense_date_edit=1,
		require_cashier_expense_attachment=0,
		enable_cashier_expense_accounting_posting=1,
		cashier_expense_posting_mode="Direct Posting",
		cashier_expense_posting_document_type="Journal Entry",
		cashier_expense_posting_roles=[],
		cashier_expense_posting_workflow_state="",
		default_cashier_expense_payable_account=None,
		require_cashier_expense_approval_before_posting=0,
		allow_rejected_cashier_expense_posting=0,
		cashier_expense_posting_remark_template="RetailEdge Cashier Expense {expense_name} - {expense_category}",
	)


@contextmanager
def _direct_posting_policy():
	settings = _direct_posting_settings()
	with (
		patch(
			"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
			return_value=settings,
		),
		patch("retailedge.cashier_expense_posting.get_retailedge_settings", return_value=settings),
		patch("retailedge.cashier_expense_posting._get_active_workflow", return_value=None),
		patch("retailedge.cashier_expense_accounting._get_active_workflow", return_value=None),
	):
		yield


class TestCashierExpensePermissionDeferralAcceptance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._original_user = frappe.session.user
		frappe.set_user("Administrator")
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()
		_ensure_branch(BRANCH)
		_ensure_branch_profile(BRANCH, is_default=False)
		_ensure_user(CASHIER, "QA Cashier Closure", ("RetailEdgeCashier",))
		_ensure_user(POSTER, "QA Cashier Poster", ("RetailEdgeManager", "Accounts Manager"))
		_ensure_assignment(CASHIER, BRANCH, "Cashier", is_primary=True, active=True)
		_ensure_assignment(POSTER, BRANCH, "Manager", is_primary=True, active=True)
		# Match the migration hook even when this class runs in isolation.
		ensure_cashier_company_read()

		cls.expense_account = _first_leaf_account(COMPANY, root_type="Expense")
		cls.cash_account = _first_leaf_account(COMPANY, root_type="Asset", account_type="Cash")
		cls.cost_center = _first_cost_center(COMPANY)
		if not frappe.db.exists("RetailEdge Expense Category", EXPENSE_CATEGORY):
			frappe.get_doc(
				{
					"doctype": "RetailEdge Expense Category",
					"category_name": EXPENSE_CATEGORY,
					"category_code": "QA-CASHIER-CLOSURE",
					"company": COMPANY,
					"expense_account": cls.expense_account,
					"default_cost_center": cls.cost_center,
					"is_active": 1,
					"description": "Deterministic runtime QA category.",
				}
			).insert(ignore_permissions=True)
		frappe.clear_cache()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(cls._original_user or "Administrator")
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _make_cashier_expense(self):
		frappe.set_user(CASHIER)
		readiness = get_retailedge_user_readiness(user=CASHIER, company=COMPANY)
		self.assertTrue(readiness["ready"], readiness["message"])
		self.assertTrue(frappe.has_permission("Company", "read", doc=COMPANY))
		self.assertFalse(frappe.has_permission("Company", "write", doc=COMPANY))
		self.assertTrue(frappe.has_permission("RetailEdge Cashier Expense", "create"))
		self.assertTrue(frappe.has_permission("RetailEdge Cashier Expense", "submit"))
		self.assertFalse(frappe.has_permission("Journal Entry", "create"))
		self.assertFalse(frappe.has_permission("Journal Entry", "submit"))

		doc = frappe.get_doc(
			{
				"doctype": "RetailEdge Cashier Expense",
				"expense_category": EXPENSE_CATEGORY,
				"amount": 1250,
				"description": "Runtime permission deferral acceptance",
				"company": COMPANY,
				"cashier": CASHIER,
				"expense_date": nowdate(),
				"branch": BRANCH,
				"payment_account": self.cash_account,
				"cost_center": self.cost_center,
			}
		)
		doc.insert()
		doc.submit()
		doc.reload()
		return doc

	def test_cashier_defers_ledger_then_authorized_poster_posts_exactly_once(self):
		with _direct_posting_policy():
			doc = self._make_cashier_expense()

			self.assertEqual(doc.docstatus, 1)
			self.assertEqual(doc.cash_movement_status, "Disbursed")
			self.assertEqual(doc.posting_mode_applied, "Direct Posting")
			self.assertEqual(doc.ledger_status, "Pending Ledger")
			self.assertFalse(doc.posting_reference)
			self.assertEqual(doc.expense_status, "Submitted")
			self.assertTrue(doc.posting_ready)
			self.assertIn("accounting posting is pending", (doc.user_message or "").lower())

			frappe.set_user(POSTER)
			self.assertTrue(frappe.has_permission("RetailEdge Cashier Expense", "write", doc=doc))
			self.assertTrue(frappe.has_permission("Journal Entry", "read"))
			self.assertTrue(frappe.has_permission("Journal Entry", "create"))
			self.assertTrue(frappe.has_permission("Journal Entry", "submit"))

			first = post_cashier_expense_to_accounts(doc.name)
			self.assertTrue(first["posted"])
			self.assertFalse(first["idempotent"])
			reference = first["posting_reference"]
			self.assertTrue(reference)
			self.assertEqual(frappe.db.get_value("Journal Entry", reference, "docstatus"), 1)

			posted = frappe.get_doc("RetailEdge Cashier Expense", doc.name)
			self.assertEqual(posted.ledger_status, "Posted")
			self.assertEqual(posted.posting_reference_type, "Journal Entry")
			self.assertEqual(posted.posting_reference, reference)
			self.assertEqual(posted.cash_movement_status, "Disbursed")

			gl_before = frappe.db.count(
				"GL Entry",
				{"voucher_type": "Journal Entry", "voucher_no": reference, "is_cancelled": 0},
			)
			self.assertGreater(gl_before, 0)

			second = post_cashier_expense_to_accounts(doc.name)
			self.assertTrue(second["posted"])
			self.assertTrue(second["idempotent"])
			self.assertEqual(second["posting_reference"], reference)
			self.assertEqual(
				frappe.db.count(
					"GL Entry",
					{"voucher_type": "Journal Entry", "voucher_no": reference, "is_cancelled": 0},
				),
				gl_before,
			)
			self.assertEqual(
				len(
					frappe.get_all(
						"Journal Entry",
						filters={
							"docstatus": 1,
							"user_remark": ["like", f"%{doc.name}%"],
						},
						fields=["name"],
						limit_page_length=0,
					)
				),
				1,
			)


class TestShiftReconciliationRealDataAcceptance(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._original_user = frappe.session.user
		frappe.set_user("Administrator")
		_ensure_company()
		_ensure_fiscal_year(COMPANY)
		_ensure_transaction_masters()
		_ensure_branch(BRANCH)
		_ensure_branch_profile(BRANCH, is_default=False)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user(cls._original_user or "Administrator")
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def _insert_audit(
		self,
		*,
		opening: str,
		closing: str,
		opening_cash: float,
		cash_sales: float,
		expenses: float,
		actual: float,
		audit_status: str,
	):
		name = f"RE-DSA-QA-{uuid4().hex[:10].upper()}"
		doc = frappe.get_doc(
			{
				"doctype": "RetailEdge Daily Sales Audit",
				"name": name,
				"naming_series": "RE-DSA-.YYYY.-.####",
				"company": COMPANY,
				"audit_date": nowdate(),
				"branch": BRANCH,
				"cashier": CASHIER,
				"pos_opening_shift": opening,
				"pos_closing_shift": closing,
				"audit_status": audit_status,
				"audit_result": "Not Checked",
				"review_required": 1,
				"opening_cash_amount": opening_cash,
				"cash_sales_amount": cash_sales,
				"cashier_expense_amount": expenses,
				"expected_cash_amount": opening_cash + cash_sales - expenses,
				"actual_closing_cash_amount": actual,
				"cash_variance_amount": actual - (opening_cash + cash_sales - expenses),
			}
		)
		doc.db_insert()
		return name

	def _insert_submitted_deposit(self, *, opening_shift: str, amount: float):
		meta = frappe.get_meta("Payment Entry")
		for fieldname in (
			"retailedge_cash_custody_type",
			"retailedge_pos_opening_shift",
			"retailedge_cashier",
		):
			self.assertTrue(meta.has_field(fieldname), f"Payment Entry is missing {fieldname}")
		name = f"ACC-PAY-QA-{uuid4().hex[:10].upper()}"
		doc = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"name": name,
				"docstatus": 1,
				"payment_type": "Internal Transfer",
				"company": COMPANY,
				"posting_date": nowdate(),
				"paid_amount": amount,
				"received_amount": amount,
				"retailedge_cash_custody_type": "Cash Deposit",
				"retailedge_cashier": CASHIER,
				"retailedge_pos_opening_shift": opening_shift,
			}
		)
		doc.db_insert()
		return name

	def test_shift_reconciliation_uses_expenses_deposits_and_flags_balanced_short_over(self):
		balanced_opening = f"QA-OPEN-{uuid4().hex[:8]}"
		short_opening = f"QA-OPEN-{uuid4().hex[:8]}"
		over_opening = f"QA-OPEN-{uuid4().hex[:8]}"

		balanced = self._insert_audit(
			opening=balanced_opening,
			closing=f"QA-CLOSE-{uuid4().hex[:8]}",
			opening_cash=1000,
			cash_sales=500,
			expenses=100,
			actual=1200,
			audit_status="Approved",
		)
		short = self._insert_audit(
			opening=short_opening,
			closing=f"QA-CLOSE-{uuid4().hex[:8]}",
			opening_cash=1000,
			cash_sales=500,
			expenses=100,
			actual=1350,
			audit_status="Variance Found",
		)
		over = self._insert_audit(
			opening=over_opening,
			closing=f"QA-CLOSE-{uuid4().hex[:8]}",
			opening_cash=1000,
			cash_sales=500,
			expenses=100,
			actual=1450,
			audit_status="Variance Found",
		)
		self._insert_submitted_deposit(opening_shift=balanced_opening, amount=200)

		result = run_review_report(
			"pos-closing-variance",
			{
				"company": COMPANY,
				"branch": BRANCH,
				"from_date": nowdate(),
				"to_date": nowdate(),
			},
		)
		rows = {row.get("daily_sales_audit"): row for row in result.get("rows") or []}
		self.assertEqual(set(rows), {balanced, short, over})

		self.assertEqual(rows[balanced]["included_cashier_expenses"], 100)
		self.assertEqual(rows[balanced]["cash_deposits"], 200)
		self.assertEqual(rows[balanced]["expected_cash"], 1200)
		self.assertEqual(rows[balanced]["actual_closing_cash"], 1200)
		self.assertEqual(rows[balanced]["cash_variance"], 0)
		self.assertEqual(rows[balanced]["cash_status"], "Balanced")

		self.assertEqual(rows[short]["expected_cash"], 1400)
		self.assertEqual(rows[short]["cash_variance"], -50)
		self.assertEqual(rows[short]["cash_status"], "Shortage")
		self.assertEqual(rows[over]["expected_cash"], 1400)
		self.assertEqual(rows[over]["cash_variance"], 50)
		self.assertEqual(rows[over]["cash_status"], "Overage")

		summary = {row.get("label"): row.get("value") for row in result.get("summary") or []}
		self.assertEqual(summary.get("Cash Deposits"), 200)
		self.assertEqual(summary.get("Exceptions"), 2)
		self.assertFalse(result.get("truncated"))
