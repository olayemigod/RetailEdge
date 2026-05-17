from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import frappe

from retailedge.cashier_context import (
	debug_shift_cash_sales,
	get_current_cashier_context,
	get_shift_cash_sales,
	get_shift_cash_snapshot,
	resolve_branch,
	resolve_cash_payment_account,
	resolve_cost_center,
)
from retailedge.cashier_expense import (
	approve_cashier_expense,
	append_cashier_expense_action_log,
	get_effective_expense_status,
	get_cashier_roles,
	get_cashier_expenses_for_variance,
	get_cashier_expense_totals,
	get_cashier_expense_totals_for_variance,
	get_cashier_expense_summary,
	get_reviewer_roles,
	reject_cashier_expense,
	reopen_cashier_expense,
	submit_cashier_expense,
	user_has_any_role,
	user_is_reviewer,
)
from retailedge.cashier_expense_audit import (
	get_cashier_expense_daily_audit_settings,
	get_cashier_expense_daily_audit_totals,
	get_cashier_expenses_for_daily_audit,
	mark_cashier_expense_excluded_from_daily_audit,
	mark_cashier_expense_included_for_daily_audit,
	mark_cashier_expense_needs_clarification,
	should_include_cashier_expense_in_daily_audit,
)
from retailedge.cashier_expense_dashboard import (
	assert_can_access_cashier_expense_dashboard,
	get_cashier_expense_dashboard_summary,
)
from retailedge.branch_context import (
	apply_branch_context_to_doc,
	backfill_retailedge_branch_context,
	get_branch_query_filters,
	get_user_allowed_branches as get_branch_context_allowed_branches,
	has_field as branch_context_has_field,
	has_doctype as branch_context_has_doctype,
	resolve_branch_from_pos_profile,
	resolve_retailedge_operational_defaults,
	resolve_retailedge_branch_context,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.branch_profile import (
	get_branch_profile,
	get_branch_profile_defaults,
	get_default_branch_for_user,
	get_user_branch_profiles,
	validate_branch_profile,
)
from retailedge.cashier_expense_posting import (
	get_cashier_expense_posting_preview,
	refresh_cashier_expense_posting_readiness,
)
from retailedge.daily_sales_audit import (
	create_daily_sales_audit_draft,
	get_daily_sales_audit_context,
	get_daily_sales_audit_context_options,
	get_daily_sales_audit_reviewer_roles,
	get_daily_sales_audit_settings,
	refresh_daily_sales_audit_preview,
	resolve_daily_sales_audit_context_from_selection,
	user_is_daily_sales_audit_reviewer,
)
from retailedge.events.pos_closing_shift import update_cashier_expenses_with_closing_shift
from retailedge.retailedge.doctype.retailedge_daily_sales_audit.retailedge_daily_sales_audit import (
	RetailEdgeDailySalesAudit,
)
from retailedge.retailedge.report.retailedge_daily_sales_audit_register.retailedge_daily_sales_audit_register import (
	execute as execute_daily_sales_audit_register_report,
)
from retailedge.retailedge.report.pos_closing_variance_vs_expenses.pos_closing_variance_vs_expenses import (
	_build_retailedge_expense_totals,
	_deduplicate_retailedge_expenses,
	get_retailedge_cashier_expense_context,
)
from retailedge.retailedge.report.retailedge_cashier_expense_review.retailedge_cashier_expense_review import (
	execute as execute_cashier_expense_review_report,
)
from retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense import (
	RetailEdgeCashierExpense,
)


class _Settings(SimpleNamespace):
	require_open_shift_for_cashier_expense = 1
	allow_cashier_expense_date_edit = 0
	include_draft_cashier_expenses_in_cash_check = 1
	include_rejected_cashier_expenses_in_cash_check = 1
	include_cashier_expenses_in_variance_report = 1
	allow_cashier_expense_without_cash_account = 0
	enable_cashier_expense_accounting_posting = 0
	cashier_expense_posting_document_type = "Journal Entry"
	default_cashier_expense_payable_account = None
	require_cashier_expense_approval_before_posting = 1
	allow_rejected_cashier_expense_posting = 0
	cashier_expense_posting_remark_template = "RetailEdge Cashier Expense {expense_name} - {expense_category}"
	include_draft_cashier_expenses_in_daily_audit = 1
	include_submitted_cashier_expenses_in_daily_audit = 1
	include_pending_ledger_cashier_expenses_in_daily_audit = 1
	include_rejected_cashier_expenses_in_daily_audit = 1
	exclude_cancelled_cashier_expenses_from_daily_audit = 1
	enable_daily_sales_audit = 1
	require_pos_closing_shift_for_daily_audit = 0
	include_cashier_expenses_in_daily_sales_audit_preview = 1
	include_rejected_cashier_expenses_in_daily_sales_audit_preview = 1
	daily_sales_audit_variance_tolerance = 0
	daily_sales_audit_reviewer_roles = []


class _Row(SimpleNamespace):
	def as_dict(self):
		return dict(self.__dict__)


class _Doc(SimpleNamespace):
	doctype = None

	def is_new(self):
		return getattr(self, "_is_new", True)


class CashierExpenseControllerTests(unittest.TestCase):
	def _make_doc(self, **kwargs):
		doc = _Doc(
			doctype="RetailEdge Cashier Expense",
			name=kwargs.pop("name", None),
			docstatus=kwargs.pop("docstatus", 0),
			expense_status=kwargs.pop("expense_status", None),
			ledger_status=kwargs.pop("ledger_status", None),
			cashier=kwargs.pop("cashier", None),
			expense_date=kwargs.pop("expense_date", None),
			company=kwargs.pop("company", None),
			branch=kwargs.pop("branch", None),
			pos_profile=kwargs.pop("pos_profile", None),
			linked_pos_opening_shift=kwargs.pop("linked_pos_opening_shift", None),
			payment_account=kwargs.pop("payment_account", None),
			cost_center=kwargs.pop("cost_center", None),
			expense_category=kwargs.pop("expense_category", None),
			expense_account=kwargs.pop("expense_account", None),
			amount=kwargs.pop("amount", 0),
			shift_opening_cash_amount=0,
			shift_cash_sales_amount=0,
			prior_shift_expense_amount=0,
			available_shift_cash_before_expense=0,
			available_shift_cash_after_expense=0,
			cash_balance_source=None,
			cash_control_message=None,
			posting_ready=0,
			posting_block_reason=None,
			resolved_debit_account=None,
			resolved_credit_account=None,
			resolved_posting_cost_center=None,
			posting_preview=None,
			include_in_daily_audit=kwargs.pop("include_in_daily_audit", 1),
			daily_audit_inclusion_status=kwargs.pop("daily_audit_inclusion_status", "Pending Review"),
			daily_audit_classification=kwargs.pop("daily_audit_classification", "Cash Expense"),
			daily_audit_note=kwargs.pop("daily_audit_note", None),
			daily_audit_reviewed_by=kwargs.pop("daily_audit_reviewed_by", None),
			daily_audit_reviewed_on=kwargs.pop("daily_audit_reviewed_on", None),
			daily_audit_exclusion_reason=kwargs.pop("daily_audit_exclusion_reason", None),
			review_required=0,
			user_message=None,
			last_readiness_refresh_on=None,
			last_readiness_refresh_by=None,
			posting_reference=kwargs.pop("posting_reference", None),
			_is_new=kwargs.pop("_is_new", True),
		)
		doc.set_cashier_defaults = RetailEdgeCashierExpense.set_cashier_defaults.__get__(doc, _Doc)
		doc.apply_expense_category = RetailEdgeCashierExpense.apply_expense_category.__get__(doc, _Doc)
		doc.apply_shift_cash_snapshot = RetailEdgeCashierExpense.apply_shift_cash_snapshot.__get__(doc, _Doc)
		doc.validate_open_shift_requirement = RetailEdgeCashierExpense.validate_open_shift_requirement.__get__(doc, _Doc)
		doc.validate_cash_account_requirement = RetailEdgeCashierExpense.validate_cash_account_requirement.__get__(doc, _Doc)
		doc.validate_required_values = RetailEdgeCashierExpense.validate_required_values.__get__(doc, _Doc)
		doc.validate_cash_availability = RetailEdgeCashierExpense.validate_cash_availability.__get__(doc, _Doc)
		doc.set_posting_readiness_preview = RetailEdgeCashierExpense.set_posting_readiness_preview.__get__(doc, _Doc)
		doc.before_submit = RetailEdgeCashierExpense.before_submit.__get__(doc, _Doc)
		doc.on_submit = RetailEdgeCashierExpense.on_submit.__get__(doc, _Doc)
		doc.before_cancel = RetailEdgeCashierExpense.before_cancel.__get__(doc, _Doc)
		doc.on_cancel = RetailEdgeCashierExpense.on_cancel.__get__(doc, _Doc)
		return doc

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.today", return_value="2026-05-11")
	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_current_cashier_context")
	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings", return_value=_Settings())
	def test_defaults_cashier_and_expense_date(self, _mock_settings, mock_context, _mock_today):
		mock_context.return_value = {}
		doc = self._make_doc()
		with patch.object(frappe, "session", SimpleNamespace(user="cashier@example.com")):
			doc.set_cashier_defaults()
		self.assertEqual(doc.cashier, "cashier@example.com")
		self.assertEqual(doc.expense_date, "2026-05-11")

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.today", return_value="2026-05-11")
	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_current_cashier_context")
	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
		return_value=_Settings(allow_cashier_expense_date_edit=0),
	)
	def test_date_edit_disabled_resets_new_doc_to_today(self, _mock_settings, mock_context, _mock_today):
		mock_context.return_value = {}
		doc = self._make_doc(expense_date="2026-05-01")
		doc.set_cashier_defaults()
		self.assertEqual(doc.expense_date, "2026-05-11")

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_current_cashier_context")
	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
		return_value=_Settings(allow_cashier_expense_date_edit=1),
	)
	def test_date_edit_enabled_preserves_selected_date(self, _mock_settings, mock_context):
		mock_context.return_value = {}
		doc = self._make_doc(expense_date="2026-05-01")
		doc.set_cashier_defaults()
		self.assertEqual(doc.expense_date, "2026-05-01")

	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
		return_value=_Settings(require_open_shift_for_cashier_expense=1),
	)
	def test_missing_open_shift_blocks_when_required(self, _mock_settings):
		doc = self._make_doc()
		with self.assertRaises(frappe.ValidationError):
			doc.validate_open_shift_requirement()

	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
		return_value=_Settings(require_open_shift_for_cashier_expense=0),
	)
	def test_missing_open_shift_does_not_block_when_disabled(self, _mock_settings):
		doc = self._make_doc()
		self.assertIsNone(doc.validate_open_shift_requirement())

	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
		return_value=_Settings(allow_cashier_expense_without_cash_account=0),
	)
	def test_payment_account_required_when_setting_disabled(self, _mock_settings):
		doc = self._make_doc(payment_account=None)
		with self.assertRaises(frappe.ValidationError):
			doc.validate_cash_account_requirement()

	def test_insufficient_shift_cash_blocks_save(self):
		doc = self._make_doc(linked_pos_opening_shift="OPEN-1", amount=500, available_shift_cash_before_expense=100)
		with self.assertRaises(frappe.ValidationError):
			doc.validate_cash_availability()

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_shift_cash_snapshot")
	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_retailedge_settings",
		return_value=_Settings(),
	)
	def test_shift_snapshot_excludes_current_document_on_update(self, _mock_settings, mock_snapshot):
		mock_snapshot.return_value = {
			"opening_cash": 1000,
			"cash_sales": 0,
			"prior_expenses": 200,
			"available_before": 800,
			"source": "opening_shift.payments",
			"message": None,
		}
		doc = self._make_doc(name="RE-CE-0001", linked_pos_opening_shift="OPEN-1", amount=50, _is_new=False)
		doc.apply_shift_cash_snapshot()
		self.assertEqual(mock_snapshot.call_args.kwargs["expense_name"], "RE-CE-0001")
		self.assertEqual(doc.available_shift_cash_after_expense, 750)

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.append_cashier_expense_action_log")
	def test_before_submit_sets_submitted_status(self, mock_log):
		doc = self._make_doc(expense_status="Draft", ledger_status=None)
		doc.before_submit()
		doc.on_submit()
		self.assertEqual(doc.expense_status, "Submitted")
		self.assertEqual(doc.ledger_status, "Not Applicable")
		mock_log.assert_called_once()

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.append_cashier_expense_action_log")
	def test_before_cancel_sets_cancelled_status(self, mock_log):
		doc = self._make_doc(expense_status="Submitted")
		doc.before_cancel()
		doc.on_cancel()
		self.assertEqual(doc.expense_status, "Cancelled")
		mock_log.assert_called_once()

	def test_effective_expense_status_uses_submitted_docstatus(self):
		doc = SimpleNamespace(docstatus=1, expense_status="Draft")
		self.assertEqual(get_effective_expense_status(doc), "Submitted")

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.build_cashier_expense_posting_preview")
	def test_set_posting_readiness_preview_sets_fields_in_memory(self, mock_preview):
		mock_preview.return_value = {
			"posting_ready": True,
			"posting_block_reason": None,
			"debit_account": "Travel Expenses - DEMO",
			"credit_account": "Cash - DEMO",
			"cost_center": "Main - DEMO",
			"posting_preview": "preview text",
		}
		doc = self._make_doc()
		doc.set_posting_readiness_preview()
		self.assertEqual(doc.posting_ready, 1)
		self.assertEqual(doc.resolved_debit_account, "Travel Expenses - DEMO")
		self.assertEqual(doc.posting_preview, "preview text")
		self.assertEqual(doc.user_message, None)


class CashierContextTests(unittest.TestCase):
	@patch("retailedge.cashier_context.find_open_pos_opening_shift", return_value=None)
	def test_get_current_cashier_context_returns_message_without_open_shift(self, _mock_shift):
		context = get_current_cashier_context(user="cashier@example.com")
		self.assertIsNone(context["linked_pos_opening_shift"])
		self.assertIn("No open POS Opening Shift found", context["message"])

	@patch("retailedge.cashier_context.resolve_cash_payment_account")
	@patch("retailedge.cashier_context.resolve_cost_center")
	@patch("retailedge.cashier_context.resolve_branch")
	@patch("retailedge.cashier_context._coerce_doc")
	@patch("retailedge.cashier_context.find_open_pos_opening_shift")
	def test_get_current_cashier_context_populates_shift_profile_and_account(
		self,
		mock_find_shift,
		mock_coerce_doc,
		mock_resolve_branch,
		mock_resolve_cost_center,
		mock_payment,
	):
		mock_find_shift.return_value = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			pos_profile="PROFILE-1",
			company="Demo Company",
			status="Open",
		)
		mock_coerce_doc.return_value = SimpleNamespace(
			doctype="POS Profile",
			company="Demo Company",
			branch="Main Branch",
			cost_center="Main - CC",
			write_off_cost_center=None,
		)
		mock_payment.return_value = {
			"payment_account": "Cash - DEMO",
			"mode_of_payment": "Cash",
			"source": "mode_of_payment_account",
			"message": None,
		}
		mock_resolve_branch.return_value = {"branch": "Main Branch", "source": "user_default", "message": None}
		mock_resolve_cost_center.return_value = {"cost_center": "Main - CC", "source": "pos_profile", "message": None}
		context = get_current_cashier_context(user="cashier@example.com")
		self.assertEqual(context["linked_pos_opening_shift"], "OPEN-1")
		self.assertEqual(context["pos_profile"], "PROFILE-1")
		self.assertEqual(context["payment_account"], "Cash - DEMO")
		self.assertEqual(context["branch"], "Main Branch")
		self.assertEqual(context["branch_source"], "user_default")
		self.assertEqual(context["cost_center"], "Main - CC")
		self.assertEqual(context["cost_center_source"], "pos_profile")

	def test_resolve_cash_payment_account_prefers_opening_shift_cash_row(self):
		opening_shift = SimpleNamespace(
			doctype="POS Opening Shift",
			payments=[_Row(mode_of_payment="Cash", account="Cash - DEMO", amount=400)],
		)
		result = resolve_cash_payment_account(company="Demo Company", opening_shift=opening_shift)
		self.assertEqual(result["payment_account"], "Cash - DEMO")
		self.assertEqual(result["source"], "opening_shift.payments")

	@patch("retailedge.cashier_context._get_pos_profile_cash_mode", return_value="Profile Cash")
	@patch("retailedge.cashier_context._coerce_doc")
	@patch("retailedge.cashier_context.frappe.db.get_value", return_value="Cash - DEMO")
	def test_resolve_cash_payment_account_uses_pos_profile_cash_mode_setting(
		self, mock_get_value, mock_coerce_doc, _mock_cash_mode
	):
		mock_coerce_doc.return_value = SimpleNamespace(doctype="POS Profile")
		result = resolve_cash_payment_account(company="Demo Company", pos_profile="PROFILE-1")
		self.assertEqual(result["payment_account"], "Cash - DEMO")
		self.assertEqual(result["mode_of_payment"], "Profile Cash")
		self.assertEqual(result["source"], "pos_profile.posa_cash_mode_of_payment")

	@patch("retailedge.cashier_context._coerce_doc")
	def test_resolve_branch_uses_user_default_when_profile_and_shift_lack_branch(self, mock_coerce_doc):
		mock_coerce_doc.return_value = SimpleNamespace(doctype="POS Profile")
		with patch("retailedge.cashier_context._get_coreedge_branch_value", return_value=None):
			with patch.object(frappe.defaults, "get_user_default", return_value="Main Branch"):
				result = resolve_branch(company="Demo Company", pos_profile="PROFILE-1", opening_shift=None, user="cashier@example.com")
		self.assertEqual(result["branch"], "Main Branch")
		self.assertEqual(result["source"], "User Default")

	@patch("retailedge.cashier_context._is_valid_cost_center", return_value=True)
	@patch("retailedge.cashier_context._coerce_doc")
	def test_resolve_cost_center_uses_pos_profile_cost_center(self, mock_coerce_doc, _mock_valid):
		mock_coerce_doc.side_effect = [
			None,
			SimpleNamespace(
				doctype="POS Profile",
				cost_center="Main - CC",
				write_off_cost_center="Fallback - CC",
			),
		]
		result = resolve_cost_center(company="Demo Company", pos_profile="PROFILE-1")
		self.assertEqual(result["cost_center"], "Main - CC")
		self.assertEqual(result["source"], "pos_profile")

	@patch("retailedge.cashier_context.get_shift_cash_sales", return_value={"cash_sales": 100, "source": "sales_invoice.payments", "message": None})
	@patch("retailedge.cashier_context._safe_settings", return_value=_Settings())
	@patch("retailedge.cashier_context.frappe.get_all")
	def test_prior_expenses_reduce_available_cash(self, mock_get_all, _mock_settings, _mock_cash_sales):
		mock_get_all.return_value = [SimpleNamespace(amount=150), SimpleNamespace(amount=50)]
		opening_shift = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			payments=[_Row(mode_of_payment="Cash", amount=1000)],
		)
		snapshot = get_shift_cash_snapshot(opening_shift=opening_shift, expense_name="RE-CE-0001")
		self.assertEqual(snapshot["opening_cash"], 1000)
		self.assertEqual(snapshot["cash_sales"], 100)
		self.assertEqual(snapshot["prior_expenses"], 200)
		self.assertEqual(snapshot["available_before"], 900)
		self.assertEqual(mock_get_all.call_args.kwargs["filters"]["name"], ["!=", "RE-CE-0001"])

	@patch("retailedge.cashier_context.resolve_cash_payment_account")
	@patch("retailedge.cashier_context._get_shift_window")
	@patch("retailedge.cashier_context._coerce_doc")
	@patch("retailedge.cashier_context.frappe.get_meta")
	@patch("retailedge.cashier_context.frappe.get_all")
	def test_get_shift_cash_sales_counts_only_cash_payments_in_shift(
		self, mock_get_all, mock_get_meta, mock_coerce_doc, mock_shift_window, mock_payment_account
	):
		opening_shift = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			company="Demo Company",
			pos_profile="PROFILE-1",
			user="cashier@example.com",
			period_start_date=datetime(2026, 5, 11, 9, 0, 0),
		)
		invoice = SimpleNamespace(
			doctype="Sales Invoice",
			name="SINV-1",
			posting_date=datetime(2026, 5, 11, 9, 30, 0),
			posting_time=None,
			payments=[
				_Row(mode_of_payment="Cash", account="Cash - DEMO", amount=500, base_amount=500),
				_Row(mode_of_payment="Card", account="Bank - DEMO", amount=200, base_amount=200),
			],
		)
		mock_shift_window.return_value = {
			"opening_shift": opening_shift,
			"closing_shift": None,
			"company": "Demo Company",
			"pos_profile": "PROFILE-1",
			"user": "cashier@example.com",
			"shift_start": datetime(2026, 5, 11, 9, 0, 0),
			"shift_end": datetime(2026, 5, 11, 11, 0, 0),
		}
		def _meta_for(doctype):
			if doctype == "Sales Invoice":
				return SimpleNamespace(has_field=lambda field: field in {"payments", "is_pos", "company", "posa_pos_opening_shift", "pos_profile"})
			if doctype == "Sales Invoice Payment":
				return SimpleNamespace(has_field=lambda field: field in {"mode_of_payment", "account", "amount", "base_amount"})
			return SimpleNamespace(has_field=lambda field: False)

		mock_get_meta.side_effect = _meta_for
		mock_get_all.return_value = [SimpleNamespace(name="SINV-1")]
		mock_coerce_doc.return_value = invoice
		mock_payment_account.return_value = {
			"payment_account": "Cash - DEMO",
			"mode_of_payment": "Cash",
			"source": "mode_of_payment_account",
			"message": None,
		}
		result = get_shift_cash_sales(opening_shift="OPEN-1", company="Demo Company", pos_profile="PROFILE-1")
		self.assertEqual(result["cash_sales"], 500)
		self.assertEqual(result["matched_invoice_count"], 1)
		self.assertEqual(result["matched_payment_count"], 1)
		self.assertEqual(result["source"], "sales_invoice.payments")

	@patch("retailedge.cashier_context.resolve_cash_payment_account")
	@patch("retailedge.cashier_context._get_shift_window")
	@patch("retailedge.cashier_context._coerce_doc")
	@patch("retailedge.cashier_context.frappe.get_meta")
	@patch("retailedge.cashier_context.frappe.get_all")
	def test_get_shift_cash_sales_ignores_non_cash_and_cancelled_invoices(
		self, mock_get_all, mock_get_meta, mock_coerce_doc, mock_shift_window, mock_payment_account
	):
		opening_shift = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			company="Demo Company",
			pos_profile="PROFILE-1",
			user="cashier@example.com",
			period_start_date=datetime(2026, 5, 11, 9, 0, 0),
		)
		invoice = SimpleNamespace(
			doctype="Sales Invoice",
			name="SINV-1",
			posting_date=datetime(2026, 5, 11, 10, 0, 0),
			posting_time=None,
			payments=[
				_Row(mode_of_payment="Card", account="Bank - DEMO", amount=200, base_amount=200),
			],
		)
		mock_shift_window.return_value = {
			"opening_shift": opening_shift,
			"closing_shift": None,
			"company": "Demo Company",
			"pos_profile": "PROFILE-1",
			"user": "cashier@example.com",
			"shift_start": datetime(2026, 5, 11, 9, 0, 0),
			"shift_end": datetime(2026, 5, 11, 11, 0, 0),
		}
		def _meta_for(doctype):
			if doctype == "Sales Invoice":
				return SimpleNamespace(has_field=lambda field: field in {"payments", "is_pos", "company", "posa_pos_opening_shift", "pos_profile"})
			if doctype == "Sales Invoice Payment":
				return SimpleNamespace(has_field=lambda field: field in {"mode_of_payment", "account", "amount", "base_amount"})
			return SimpleNamespace(has_field=lambda field: False)

		mock_get_meta.side_effect = _meta_for
		mock_get_all.return_value = [SimpleNamespace(name="SINV-1")]
		mock_coerce_doc.return_value = invoice
		mock_payment_account.return_value = {
			"payment_account": "Cash - DEMO",
			"mode_of_payment": "Cash",
			"source": "mode_of_payment_account",
			"message": None,
		}
		result = get_shift_cash_sales(opening_shift="OPEN-1", company="Demo Company", pos_profile="PROFILE-1")
		self.assertEqual(result["cash_sales"], 0)
		self.assertEqual(result["matched_invoice_count"], 0)
		self.assertIn("could not be safely resolved", result["message"])


class PosClosingShiftHookTests(unittest.TestCase):
	@patch("retailedge.events.pos_closing_shift.frappe.db.set_value")
	@patch("retailedge.events.pos_closing_shift.frappe.get_all")
	def test_pos_closing_shift_updates_linked_cashier_expenses(self, mock_get_all, mock_set_value):
		mock_get_all.return_value = [SimpleNamespace(name="RE-CE-0001"), SimpleNamespace(name="RE-CE-0002")]
		doc = SimpleNamespace(name="POSC-0001", pos_opening_shift="OPEN-1")
		update_cashier_expenses_with_closing_shift(doc)
		self.assertEqual(mock_set_value.call_count, 2)


class CashierExpenseServiceTests(unittest.TestCase):
	def test_reviewer_roles_include_spaced_and_compact_names(self):
		roles = get_reviewer_roles()
		self.assertIn("RetailEdge Auditor", roles)
		self.assertIn("RetailEdgeAuditor", roles)

	def test_cashier_roles_include_spaced_and_compact_names(self):
		roles = get_cashier_roles()
		self.assertIn("RetailEdge Cashier", roles)
		self.assertIn("RetailEdgeCashier", roles)

	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	def test_user_is_reviewer(self, _mock_roles):
		self.assertTrue(user_is_reviewer("auditor@example.com"))

	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdgeCashier"])
	def test_user_has_any_role_supports_compact_cashier_role(self, _mock_roles):
		self.assertTrue(user_has_any_role("cashier@example.com", get_cashier_roles()))

	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_submit_cashier_expense_submits_draft(self, mock_get_doc):
		doc = SimpleNamespace(
			name="RE-CE-0001",
			docstatus=0,
			expense_status="Draft",
			ledger_status="Not Applicable",
			has_permission=lambda perm: perm == "submit",
		)
		def _submit():
			doc.docstatus = 1
			doc.expense_status = "Submitted"
		doc.submit = _submit
		mock_get_doc.return_value = doc
		result = submit_cashier_expense("RE-CE-0001")
		self.assertEqual(result["docstatus"], 1)
		self.assertEqual(result["expense_status"], "Submitted")

	@patch("retailedge.cashier_expense.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_approve_moves_submitted_to_pending_ledger(self, mock_get_doc, _mock_roles, mock_log):
		doc = SimpleNamespace(
			name="RE-CE-0002",
			docstatus=1,
			expense_status="Submitted",
			ledger_status="Not Applicable",
			cashier="cashier@example.com",
			has_permission=lambda perm: perm == "write",
			save=lambda ignore_permissions=True: None,
		)
		mock_get_doc.return_value = doc
		result = approve_cashier_expense("RE-CE-0002", remarks="approved")
		self.assertEqual(result["expense_status"], "Pending Ledger")
		self.assertEqual(result["ledger_status"], "Pending Ledger")
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense.frappe.db.set_value")
	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_approve_normalises_stale_submitted_docstatus(self, mock_get_doc, _mock_roles, mock_set_value, mock_log):
		doc = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-0002B",
			docstatus=1,
			expense_status="Draft",
			ledger_status="Not Applicable",
			cashier="cashier@example.com",
			has_permission=lambda perm: perm == "write",
			save=lambda ignore_permissions=True: None,
		)
		mock_get_doc.return_value = doc
		result = approve_cashier_expense("RE-CE-0002B", remarks="ok")
		self.assertEqual(result["expense_status"], "Pending Ledger")
		mock_set_value.assert_called_once_with(
			"RetailEdge Cashier Expense",
			"RE-CE-0002B",
			"expense_status",
			"Submitted",
			update_modified=False,
		)
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_reject_moves_submitted_to_rejected(self, mock_get_doc, _mock_roles, mock_log):
		doc = SimpleNamespace(
			name="RE-CE-0003",
			docstatus=1,
			expense_status="Submitted",
			ledger_status="Not Applicable",
			cashier="cashier@example.com",
			has_permission=lambda perm: perm == "write",
			save=lambda ignore_permissions=True: None,
		)
		mock_get_doc.return_value = doc
		result = reject_cashier_expense("RE-CE-0003", remarks="reject")
		self.assertEqual(result["expense_status"], "Rejected")
		self.assertEqual(result["ledger_status"], "Not Applicable")
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_reopen_moves_rejected_back_to_submitted(self, mock_get_doc, _mock_roles, mock_log):
		doc = SimpleNamespace(
			name="RE-CE-0004",
			docstatus=1,
			expense_status="Rejected",
			ledger_status="Pending Ledger",
			has_permission=lambda perm: perm == "write",
			save=lambda ignore_permissions=True: None,
		)
		mock_get_doc.return_value = doc
		result = reopen_cashier_expense("RE-CE-0004", remarks="retry")
		self.assertEqual(result["expense_status"], "Submitted")
		self.assertEqual(result["ledger_status"], "Not Applicable")
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdgeCashier"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="cashier@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_cashier_only_user_cannot_approve(self, mock_get_doc, _mock_roles):
		doc = SimpleNamespace(name="RE-CE-0100", docstatus=1, expense_status="Submitted", cashier="other@example.com")
		mock_get_doc.return_value = doc
		with self.assertRaises(frappe.PermissionError):
			approve_cashier_expense("RE-CE-0100")

	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_cancelled_expense_cannot_be_approved_rejected_or_reopened(self, mock_get_doc, _mock_roles):
		doc = SimpleNamespace(name="RE-CE-0101", docstatus=2, expense_status="Cancelled", cashier="cashier@example.com")
		mock_get_doc.return_value = doc
		with self.assertRaises(frappe.ValidationError):
			approve_cashier_expense("RE-CE-0101")
		with self.assertRaises(frappe.ValidationError):
			reject_cashier_expense("RE-CE-0101")
		with self.assertRaises(frappe.ValidationError):
			reopen_cashier_expense("RE-CE-0101")

	@patch("retailedge.cashier_expense.frappe.get_roles", return_value=["RetailEdge Auditor"])
	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	def test_reopen_moves_pending_ledger_back_to_submitted(self, mock_get_doc, _mock_roles):
		doc = SimpleNamespace(
			name="RE-CE-0005",
			docstatus=1,
			expense_status="Pending Ledger",
			ledger_status="Pending Ledger",
			has_permission=lambda perm: perm == "write",
			save=lambda ignore_permissions=True: None,
		)
		mock_get_doc.return_value = doc
		with patch("retailedge.cashier_expense.append_cashier_expense_action_log"):
			result = reopen_cashier_expense("RE-CE-0005", remarks="return to submitted")
		self.assertEqual(result["expense_status"], "Submitted")
		self.assertEqual(result["ledger_status"], "Not Applicable")

	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_summary_groups_by_status(self, mock_get_all):
		mock_get_all.return_value = [
			SimpleNamespace(expense_status="Submitted", amount=100),
			SimpleNamespace(expense_status="Submitted", amount=50),
			SimpleNamespace(expense_status="Rejected", amount=25),
		]
		result = get_cashier_expense_summary()
		self.assertEqual(result["Submitted"]["count"], 2)
		self.assertEqual(result["Submitted"]["total_amount"], 150)
		self.assertEqual(result["Rejected"]["count"], 1)

	@patch("retailedge.cashier_expense.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_excludes_cancelled_by_default(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance()
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["!=", "Cancelled"])
		self.assertEqual(filters["docstatus"], ["!=", 2])

	@patch("retailedge.cashier_expense.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_includes_rejected_by_default(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance()
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["!=", "Cancelled"])

	@patch("retailedge.cashier_expense.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_can_exclude_rejected(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance(include_rejected=False)
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["not in", ["Cancelled", "Rejected"]])

	@patch("retailedge.cashier_expense.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_supports_shift_filters(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance(
			{
				"pos_profile": "Testing",
				"linked_pos_opening_shift": "OPEN-1",
				"linked_pos_closing_shift": "CLOSE-1",
			}
		)
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["pos_profile"], "Testing")
		self.assertEqual(filters["linked_pos_opening_shift"], "OPEN-1")
		self.assertEqual(filters["linked_pos_closing_shift"], "CLOSE-1")

	@patch(
		"retailedge.cashier_expense.get_retailedge_settings",
		return_value=_Settings(include_draft_cashier_expenses_in_cash_check=0),
	)
	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_respects_draft_setting(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance()
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["not in", ["Cancelled", "Draft"]])

	@patch(
		"retailedge.cashier_expense.get_retailedge_settings",
		return_value=_Settings(include_cashier_expenses_in_variance_report=0),
	)
	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_respects_variance_toggle(self, mock_get_all, _mock_settings):
		result = get_cashier_expenses_for_variance()
		self.assertEqual(result, [])
		mock_get_all.assert_not_called()

	@patch("retailedge.cashier_expense.frappe.session", SimpleNamespace(user="auditor@example.com"))
	@patch("retailedge.cashier_expense.frappe.get_doc")
	@patch("retailedge.cashier_expense.frappe.db.count", return_value=0)
	def test_append_cashier_expense_action_log_serialises_context(self, mock_count, mock_get_doc):
		parent = SimpleNamespace(name="RE-CE-0200", doctype="RetailEdge Cashier Expense")
		mock_get_doc.return_value = parent
		with patch("retailedge.cashier_expense.frappe.get_doc") as mock_child_get_doc:
			child = SimpleNamespace(db_insert=lambda ignore_permissions=True: None)
			mock_child_get_doc.side_effect = [parent, child]
			append_cashier_expense_action_log(
				"RE-CE-0200",
				action="Approved",
				previous_status="Submitted",
				new_status="Pending Ledger",
				context={"ledger_status": "Pending Ledger"},
			)
		payload = mock_child_get_doc.call_args_list[1].args[0]
		self.assertEqual(payload["parent"], "RE-CE-0200")
		self.assertIn("ledger_status", payload["context"])

	@patch("retailedge.cashier_expense.get_cashier_expenses_for_variance")
	def test_get_cashier_expense_totals_for_variance_groups_by_status_and_category(self, mock_get_rows):
		mock_get_rows.return_value = [
			{"expense_status": "Draft", "expense_category": "Transport", "amount": 100},
			{"expense_status": "Submitted", "expense_category": "Transport", "amount": 50},
			{"expense_status": "Rejected", "expense_category": "Fuel", "amount": 25},
		]
		result = get_cashier_expense_totals_for_variance()
		self.assertEqual(result["count"], 3)
		self.assertEqual(result["total_expense_amount"], 175)
		self.assertEqual(result["by_status"]["Draft"]["count"], 1)
		self.assertEqual(result["by_status"]["Submitted"]["amount"], 50)
		self.assertEqual(result["by_category"]["Transport"]["count"], 2)
		self.assertEqual(result["by_category"]["Fuel"]["amount"], 25)

	@patch("retailedge.cashier_expense.frappe.get_list")
	def test_get_cashier_expense_totals_groups_visible_rows(self, mock_get_list):
		mock_get_list.return_value = [
			{"name": "RE-CE-1", "amount": 100, "expense_status": "Draft", "ledger_status": "Not Applicable", "posting_ready": 1, "docstatus": 0},
			{"name": "RE-CE-2", "amount": 250, "expense_status": "Submitted", "ledger_status": "Pending Ledger", "posting_ready": 0, "docstatus": 1},
		]
		result = get_cashier_expense_totals([["RetailEdge Cashier Expense", "company", "=", "Demo Company"]])
		self.assertEqual(result["count"], 2)
		self.assertEqual(result["total_amount"], 350)
		self.assertEqual(result["by_status"]["Draft"]["count"], 1)
		self.assertEqual(result["by_status"]["Submitted"]["amount"], 250)
		self.assertEqual(result["by_ledger_status"]["Pending Ledger"]["count"], 1)
		self.assertEqual(result["posting_ready_count"], 1)
		self.assertEqual(result["posting_blocked_count"], 1)

	@patch("retailedge.retailedge.report.pos_closing_variance_vs_expenses.pos_closing_variance_vs_expenses.get_shift_cash_snapshot")
	@patch("retailedge.retailedge.report.pos_closing_variance_vs_expenses.pos_closing_variance_vs_expenses.get_cashier_expense_totals_for_variance")
	@patch("retailedge.retailedge.report.pos_closing_variance_vs_expenses.pos_closing_variance_vs_expenses.get_cashier_expenses_for_variance")
	def test_report_context_reuses_shift_snapshot(
		self, mock_get_expenses, mock_get_totals, mock_snapshot
	):
		entry = SimpleNamespace(
			name="POSC-1",
			company="Demo Company",
			pos_profile="Testing",
			pos_opening_shift="OPEN-1",
			user="cashier@example.com",
			posting_date="2026-05-11",
		)
		mock_get_expenses.return_value = [{"name": "RE-CE-1", "amount": 100}]
		mock_get_totals.return_value = {"total_expense_amount": 100, "count": 1, "by_status": {}, "by_category": {}}
		mock_snapshot.return_value = {"opening_cash": 30000, "cash_sales": 1800, "prior_expenses": 100, "available_before": 31700}
		context = get_retailedge_cashier_expense_context(entry)
		self.assertEqual(context["snapshot"]["cash_sales"], 1800)
		self.assertEqual(mock_snapshot.call_args.kwargs["opening_shift"], "OPEN-1")

	def test_retailedge_expense_deduplication_filters_already_used_names(self):
		rows = _deduplicate_retailedge_expenses(
			[
				{"name": "RE-CE-1", "amount": 100},
				{"name": "RE-CE-1", "amount": 100},
				{"name": "RE-CE-2", "amount": 50},
			],
			exclude_expense_names={"RE-CE-2"},
		)
		self.assertEqual([row["name"] for row in rows], ["RE-CE-1"])

	def test_retailedge_expense_totals_are_built_from_deduplicated_rows(self):
		totals = _build_retailedge_expense_totals(
			[
				{"name": "RE-CE-1", "expense_status": "Draft", "expense_category": "Transport", "amount": 100},
				{"name": "RE-CE-2", "expense_status": "Rejected", "expense_category": "Fuel", "amount": 50},
			]
		)
		self.assertEqual(totals["count"], 2)
		self.assertEqual(totals["total_expense_amount"], 150)
		self.assertEqual(totals["by_status"]["Draft"]["amount"], 100)
		self.assertEqual(totals["by_category"]["Fuel"]["amount"], 50)

	@patch(
		"retailedge.cashier_expense_audit.get_retailedge_settings",
		return_value=_Settings(exclude_cancelled_cashier_expenses_from_daily_audit=1),
	)
	def test_cancelled_expenses_excluded_from_daily_audit_by_default(self, _mock_settings):
		decision = should_include_cashier_expense_in_daily_audit(
			SimpleNamespace(docstatus=2, expense_status="Cancelled", include_in_daily_audit=1)
		)
		self.assertFalse(decision["include"])

	@patch(
		"retailedge.cashier_expense_audit.get_retailedge_settings",
		return_value=_Settings(include_rejected_cashier_expenses_in_daily_audit=1),
	)
	def test_rejected_expenses_included_in_daily_audit_by_default(self, _mock_settings):
		decision = should_include_cashier_expense_in_daily_audit(
			SimpleNamespace(docstatus=1, expense_status="Rejected", include_in_daily_audit=1)
		)
		self.assertTrue(decision["include"])

	def test_include_in_daily_audit_zero_excludes_expense(self):
		decision = should_include_cashier_expense_in_daily_audit(
			SimpleNamespace(docstatus=1, expense_status="Submitted", include_in_daily_audit=0),
			settings=get_cashier_expense_daily_audit_settings(),
		)
		self.assertFalse(decision["include"])

	@patch(
		"retailedge.cashier_expense_audit.get_retailedge_settings",
		return_value=_Settings(include_draft_cashier_expenses_in_daily_audit=0),
	)
	def test_draft_expenses_can_be_excluded_from_daily_audit_by_setting(self, _mock_settings):
		decision = should_include_cashier_expense_in_daily_audit(
			SimpleNamespace(docstatus=0, expense_status="Draft", include_in_daily_audit=1),
			settings=get_cashier_expense_daily_audit_settings(),
		)
		self.assertFalse(decision["include"])
		self.assertEqual(decision["status"], "Draft")

	@patch("retailedge.cashier_expense_audit.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_audit.frappe.db.set_value")
	@patch("retailedge.cashier_expense_audit.frappe.get_doc")
	@patch("retailedge.cashier_expense_audit.user_is_reviewer", return_value=True)
	@patch("retailedge.cashier_expense_audit.frappe.session", SimpleNamespace(user="auditor@example.com"))
	def test_mark_included_sets_status_and_review_fields(
		self, _mock_reviewer, mock_get_doc, mock_set_value, mock_log
	):
		doc = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-0301",
			docstatus=1,
			expense_status="Submitted",
			has_permission=lambda perm: perm == "write",
			include_in_daily_audit=1,
			daily_audit_inclusion_status="Included",
			daily_audit_reviewed_by="auditor@example.com",
			daily_audit_reviewed_on="2026-05-14 10:00:00",
		)
		mock_get_doc.side_effect = [doc, doc]
		result = mark_cashier_expense_included_for_daily_audit("RE-CE-0301", note="reviewed")
		values = mock_set_value.call_args.args[2]
		self.assertEqual(values["daily_audit_inclusion_status"], "Included")
		self.assertEqual(values["include_in_daily_audit"], 1)
		self.assertEqual(result["daily_audit_inclusion_status"], "Included")
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense_audit.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_audit.frappe.db.set_value")
	@patch("retailedge.cashier_expense_audit.frappe.get_doc")
	@patch("retailedge.cashier_expense_audit.user_is_reviewer", return_value=True)
	@patch("retailedge.cashier_expense_audit.frappe.session", SimpleNamespace(user="auditor@example.com"))
	def test_mark_excluded_sets_include_zero(
		self, _mock_reviewer, mock_get_doc, mock_set_value, mock_log
	):
		doc = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-0302",
			docstatus=1,
			expense_status="Submitted",
			has_permission=lambda perm: perm == "write",
			include_in_daily_audit=0,
			daily_audit_inclusion_status="Excluded",
			daily_audit_reviewed_by="auditor@example.com",
			daily_audit_reviewed_on="2026-05-14 10:00:00",
		)
		mock_get_doc.side_effect = [doc, doc]
		result = mark_cashier_expense_excluded_from_daily_audit("RE-CE-0302", reason="duplicate")
		values = mock_set_value.call_args.args[2]
		self.assertEqual(values["include_in_daily_audit"], 0)
		self.assertEqual(values["daily_audit_inclusion_status"], "Excluded")
		self.assertEqual(result["include_in_daily_audit"], 0)
		mock_log.assert_called_once()

	def test_mark_excluded_requires_reason(self):
		with self.assertRaises(frappe.ValidationError):
			mark_cashier_expense_excluded_from_daily_audit("RE-CE-0303", reason=None)

	@patch("retailedge.cashier_expense_audit.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_audit.frappe.db.set_value")
	@patch("retailedge.cashier_expense_audit.frappe.get_doc")
	@patch("retailedge.cashier_expense_audit.user_is_reviewer", return_value=True)
	@patch("retailedge.cashier_expense_audit.frappe.session", SimpleNamespace(user="auditor@example.com"))
	def test_needs_clarification_sets_correct_status(
		self, _mock_reviewer, mock_get_doc, mock_set_value, mock_log
	):
		doc = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name="RE-CE-0304",
			docstatus=1,
			expense_status="Submitted",
			has_permission=lambda perm: perm == "write",
			include_in_daily_audit=1,
			daily_audit_inclusion_status="Needs Clarification",
			daily_audit_reviewed_by="auditor@example.com",
			daily_audit_reviewed_on="2026-05-14 10:00:00",
		)
		mock_get_doc.side_effect = [doc, doc]
		result = mark_cashier_expense_needs_clarification("RE-CE-0304", note="check receipt")
		values = mock_set_value.call_args.args[2]
		self.assertEqual(values["daily_audit_inclusion_status"], "Needs Clarification")
		self.assertEqual(result["daily_audit_inclusion_status"], "Needs Clarification")
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense_audit.user_is_reviewer", return_value=False)
	def test_reviewer_role_required_for_daily_audit_actions(self, _mock_reviewer):
		with self.assertRaises(frappe.PermissionError):
			mark_cashier_expense_included_for_daily_audit("RE-CE-0305", note="x")

	@patch("retailedge.cashier_expense_audit.user_is_reviewer", return_value=False)
	def test_cashier_only_user_cannot_perform_daily_audit_actions(self, _mock_reviewer):
		with self.assertRaises(frappe.PermissionError):
			mark_cashier_expense_needs_clarification("RE-CE-0306", note="x")

	@patch("retailedge.cashier_expense_audit.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense_audit.frappe.get_all")
	def test_daily_audit_helpers_do_not_mutate_other_docs(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = [
			{
				"name": "RE-CE-0401",
				"expense_status": "Submitted",
				"ledger_status": "Not Applicable",
				"include_in_daily_audit": 1,
				"daily_audit_inclusion_status": "Pending Review",
				"daily_audit_classification": "Cash Expense",
				"amount": 100,
				"docstatus": 1,
			}
		]
		totals = get_cashier_expense_daily_audit_totals()
		self.assertEqual(totals["count"], 1)
		self.assertEqual(totals["included_count"], 1)

	@patch("retailedge.cashier_expense_audit.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense_audit.frappe.get_all")
	def test_get_cashier_expenses_for_daily_audit_supports_filters(self, mock_get_all, _mock_settings):
		mock_get_all.return_value = []
		get_cashier_expenses_for_daily_audit(
			{
				"company": "Demo Company",
				"pos_profile": "Testing",
				"cashier": "cashier@example.com",
				"daily_audit_inclusion_status": "Included",
				"ledger_status": "Pending Ledger",
				"daily_audit_classification": "Cash Expense",
			}
		)
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "Demo Company")
		self.assertEqual(filters["pos_profile"], "Testing")
		self.assertEqual(filters["cashier"], "cashier@example.com")
		self.assertEqual(filters["daily_audit_inclusion_status"], "Included")
		self.assertEqual(filters["ledger_status"], "Pending Ledger")
		self.assertEqual(filters["daily_audit_classification"], "Cash Expense")

	@patch(
		"retailedge.retailedge.report.retailedge_cashier_expense_review.retailedge_cashier_expense_review.get_cashier_expenses_for_daily_audit"
	)
	def test_cashier_expense_review_report_executes_without_error(self, mock_get_rows):
		mock_get_rows.return_value = [
			{
				"name": "RE-CE-0501",
				"expense_date": "2026-05-14",
				"company": "Demo Company",
				"branch": "Main Branch",
				"pos_profile": "Testing",
				"cashier": "cashier@example.com",
				"linked_pos_opening_shift": "OPEN-1",
				"linked_pos_closing_shift": "CLOSE-1",
				"expense_category": "Transport",
				"amount": 100,
				"expense_status": "Submitted",
				"ledger_status": "Not Applicable",
				"posting_ready": 1,
				"posting_block_reason": None,
				"include_in_daily_audit": 1,
				"daily_audit_inclusion_status": "Pending Review",
				"daily_audit_classification": "Cash Expense",
				"daily_audit_note": None,
				"daily_audit_exclusion_reason": None,
				"payment_account": "Cash - DEMO",
				"expense_account": "Travel Expenses - DEMO",
				"cost_center": "Main - DEMO",
				"description": "test",
			}
		]
		columns, data, _message, chart, summary = execute_cashier_expense_review_report(
			{"company": "Demo Company", "cashier": "cashier@example.com"}
		)
		self.assertTrue(columns)
		self.assertEqual(len(data), 2)
		self.assertEqual(data[0]["name"], "RE-CE-0501")
		self.assertEqual(data[1]["name"], "Totals")
		self.assertEqual(chart["data"]["labels"], ["Submitted"])
		self.assertEqual(summary[0]["value"], 100)
		mock_get_rows.assert_called_once()

	@patch(
		"retailedge.retailedge.report.retailedge_cashier_expense_review.retailedge_cashier_expense_review.get_cashier_expenses_for_daily_audit"
	)
	def test_cashier_expense_review_report_respects_posting_ready_filter(self, mock_get_rows):
		mock_get_rows.return_value = [
			{"name": "RE-CE-1", "expense_status": "Submitted", "posting_ready": 1},
			{"name": "RE-CE-2", "expense_status": "Rejected", "posting_ready": 0},
		]
		_columns, data, _message, _chart, summary = execute_cashier_expense_review_report({"posting_ready": 1})
		self.assertEqual([row["name"] for row in data], ["RE-CE-1", "Totals"])
		self.assertEqual(summary[1]["value"], 1)


class CashierExpensePostingTests(unittest.TestCase):
	def _expense_doc(self, **kwargs):
		return SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name=kwargs.pop("name", "RE-CE-0001"),
			docstatus=kwargs.pop("docstatus", 1),
			expense_status=kwargs.pop("expense_status", "Pending Ledger"),
			ledger_status=kwargs.pop("ledger_status", "Not Applicable"),
			company=kwargs.pop("company", "Demo Company"),
			expense_date=kwargs.pop("expense_date", "2026-05-11"),
			amount=kwargs.pop("amount", 100),
			expense_account=kwargs.pop("expense_account", "Travel Expenses - DEMO"),
			payment_account=kwargs.pop("payment_account", "Cash - DEMO"),
			cost_center=kwargs.pop("cost_center", "Main - DEMO"),
			expense_category=kwargs.pop("expense_category", "Transport"),
			posting_reference=kwargs.pop("posting_reference", None),
		)

	@patch("retailedge.cashier_expense_posting.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense_posting.frappe.get_cached_doc")
	@patch("retailedge.cashier_expense_posting.frappe.db.exists", return_value=True)
	@patch("retailedge.cashier_expense_posting.frappe.get_doc")
	def test_posting_preview_produces_debit_credit_lines(
		self, mock_get_doc, _mock_exists, mock_get_cached_doc, _mock_settings
	):
		mock_get_doc.return_value = self._expense_doc()
		mock_get_cached_doc.side_effect = [
			SimpleNamespace(company="Demo Company", root_type="Expense", is_group=0),
			SimpleNamespace(company="Demo Company", root_type="Asset", is_group=0),
		]
		preview = get_cashier_expense_posting_preview("RE-CE-0001")
		self.assertTrue(preview["posting_ready"])
		self.assertEqual(len(preview["preview_lines"]), 2)
		self.assertEqual(preview["preview_lines"][0]["debit"], 100)
		self.assertEqual(preview["preview_lines"][1]["credit"], 100)

	@patch(
		"retailedge.cashier_expense_posting.get_retailedge_settings",
		return_value=_Settings(require_cashier_expense_approval_before_posting=1),
	)
	@patch("retailedge.cashier_expense_posting.frappe.get_cached_doc")
	@patch("retailedge.cashier_expense_posting.frappe.db.exists", return_value=True)
	@patch("retailedge.cashier_expense_posting.frappe.get_doc")
	def test_posting_preview_blocks_rejected_when_not_allowed(
		self, mock_get_doc, _mock_exists, mock_get_cached_doc, _mock_settings
	):
		mock_get_doc.return_value = self._expense_doc(expense_status="Rejected")
		mock_get_cached_doc.side_effect = [
			SimpleNamespace(company="Demo Company", root_type="Expense", is_group=0),
			SimpleNamespace(company="Demo Company", root_type="Asset", is_group=0),
		]
		preview = get_cashier_expense_posting_preview("RE-CE-0001")
		self.assertFalse(preview["posting_ready"])
		self.assertIn("Rejected cashier expenses are blocked", preview["posting_block_reason"])

	@patch("retailedge.cashier_expense_posting.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_posting.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense_posting.frappe.db.set_value")
	@patch("retailedge.cashier_expense_posting.frappe.get_cached_doc")
	@patch("retailedge.cashier_expense_posting.frappe.db.exists", return_value=True)
	@patch("retailedge.cashier_expense_posting.frappe.get_doc")
	def test_refresh_readiness_updates_posting_fields(
		self, mock_get_doc, _mock_exists, mock_get_cached_doc, mock_set_value, _mock_settings, mock_log
	):
		mock_get_doc.return_value = self._expense_doc()
		mock_get_cached_doc.side_effect = [
			SimpleNamespace(company="Demo Company", root_type="Expense", is_group=0),
			SimpleNamespace(company="Demo Company", root_type="Asset", is_group=0),
		]
		preview = refresh_cashier_expense_posting_readiness("RE-CE-0001")
		values = mock_set_value.call_args.args[2]
		self.assertIn("posting_ready", values)
		self.assertIn("posting_preview", values)
		self.assertIn("last_readiness_refresh_on", values)
		self.assertTrue(preview["posting_ready"])
		mock_log.assert_called_once()

	@patch("retailedge.cashier_expense_posting.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.cashier_expense_posting.frappe.get_doc")
	def test_posting_preview_blocks_cancelled_expense(self, mock_get_doc, _mock_settings):
		mock_get_doc.return_value = self._expense_doc(docstatus=2, expense_status="Cancelled")
		preview = get_cashier_expense_posting_preview("RE-CE-0001")
		self.assertFalse(preview["posting_ready"])
		self.assertIn("Cancelled expenses", preview["posting_block_reason"])


class CashierExpenseDashboardTests(unittest.TestCase):
	@patch("retailedge.cashier_expense_dashboard.frappe.get_all")
	def test_dashboard_summary_counts_statuses_and_daily_audit_states(self, mock_get_all):
		mock_get_all.return_value = [
			{
				"name": "RE-CE-0601",
				"expense_date": "2026-05-14",
				"company": "Demo Company",
				"branch": "HQ",
				"pos_profile": "Testing",
				"cashier": "cashier1@example.com",
				"expense_category": "Transport",
				"amount": 100,
				"expense_status": "Draft",
				"ledger_status": "Not Applicable",
				"posting_ready": 0,
				"daily_audit_inclusion_status": "Pending Review",
				"description": "taxi",
				"docstatus": 0,
			},
			{
				"name": "RE-CE-0602",
				"expense_date": "2026-05-14",
				"company": "Demo Company",
				"branch": "HQ",
				"pos_profile": "Testing",
				"cashier": "cashier2@example.com",
				"expense_category": "Transport",
				"amount": 250,
				"expense_status": "Pending Ledger",
				"ledger_status": "Pending Ledger",
				"posting_ready": 1,
				"daily_audit_inclusion_status": "Included",
				"description": "fuel",
				"docstatus": 1,
			},
			{
				"name": "RE-CE-0603",
				"expense_date": "2026-05-14",
				"company": "Demo Company",
				"branch": "HQ",
				"pos_profile": "Testing",
				"cashier": "cashier1@example.com",
				"expense_category": "Supplies",
				"amount": 50,
				"expense_status": "Rejected",
				"ledger_status": "Not Applicable",
				"posting_ready": 0,
				"daily_audit_inclusion_status": "Needs Clarification",
				"description": "bags",
				"docstatus": 1,
			},
			{
				"name": "RE-CE-0604",
				"expense_date": "2026-05-14",
				"company": "Demo Company",
				"branch": "HQ",
				"pos_profile": "Testing",
				"cashier": "cashier3@example.com",
				"expense_category": "Supplies",
				"amount": 80,
				"expense_status": "Cancelled",
				"ledger_status": "Not Applicable",
				"posting_ready": 1,
				"daily_audit_inclusion_status": "Excluded",
				"description": "void",
				"docstatus": 2,
			},
		]
		summary = get_cashier_expense_dashboard_summary({"company": "Demo Company"})
		self.assertEqual(summary["total_expenses"], 400)
		self.assertEqual(summary["expense_count"], 3)
		self.assertEqual(summary["draft_count"], 1)
		self.assertEqual(summary["pending_ledger_count"], 1)
		self.assertEqual(summary["rejected_count"], 1)
		self.assertEqual(summary["cancelled_count"], 1)
		self.assertEqual(summary["posting_ready_count"], 1)
		self.assertEqual(summary["posting_blocked_count"], 2)
		self.assertEqual(summary["daily_audit_pending_review_count"], 1)
		self.assertEqual(summary["daily_audit_included_count"], 1)
		self.assertEqual(summary["daily_audit_needs_clarification_count"], 1)
		self.assertEqual(summary["daily_audit_excluded_count"], 0)
		self.assertEqual(summary["top_cashiers"][0]["name"], "cashier2@example.com")
		self.assertEqual(summary["top_categories"][0]["name"], "Transport")
		self.assertEqual(len(summary["recent_expenses"]), 4)

	@patch("retailedge.cashier_expense_dashboard.frappe.get_all")
	def test_dashboard_summary_respects_filters(self, mock_get_all):
		mock_get_all.return_value = []
		get_cashier_expense_dashboard_summary(
			{
				"company": "Demo Company",
				"branch": "HQ",
				"pos_profile": "Testing",
				"cashier": "cashier@example.com",
				"from_date": "2026-05-01",
				"to_date": "2026-05-14",
			}
		)
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["company"], "Demo Company")
		self.assertEqual(filters["branch"], "HQ")
		self.assertEqual(filters["pos_profile"], "Testing")
		self.assertEqual(filters["cashier"], "cashier@example.com")
		self.assertEqual(filters["expense_date"], ["between", ["2026-05-01", "2026-05-14"]])

	@patch("retailedge.cashier_expense_dashboard.user_has_any_role", return_value=False)
	def test_dashboard_access_requires_manager_or_reviewer_role(self, _mock_roles):
		with self.assertRaises(frappe.PermissionError):
			assert_can_access_cashier_expense_dashboard()


class DailySalesAuditTests(unittest.TestCase):
	def _make_audit_doc(self, **kwargs):
		doc = _Doc(
			doctype="RetailEdge Daily Sales Audit",
			name=kwargs.pop("name", None),
			docstatus=kwargs.pop("docstatus", 0),
			audit_status=kwargs.pop("audit_status", "Draft"),
			audit_result=kwargs.pop("audit_result", "Not Checked"),
			company=kwargs.pop("company", None),
			audit_date=kwargs.pop("audit_date", None),
			branch=kwargs.pop("branch", None),
			pos_profile=kwargs.pop("pos_profile", None),
			cashier=kwargs.pop("cashier", None),
			pos_opening_shift=kwargs.pop("pos_opening_shift", None),
			pos_closing_shift=kwargs.pop("pos_closing_shift", None),
			invoice_lines=kwargs.pop("invoice_lines", []),
			payment_lines=kwargs.pop("payment_lines", []),
			cashier_expense_lines=kwargs.pop("cashier_expense_lines", []),
			action_logs=kwargs.pop("action_logs", []),
			review_required=kwargs.pop("review_required", 1),
		)

		def _set(field, value):
			setattr(doc, field, value)

		def _append(field, value):
			rows = getattr(doc, field, None)
			if not isinstance(rows, list):
				rows = []
				setattr(doc, field, rows)
			rows.append(value)
			return value

		doc.set = _set
		doc.append = _append
		doc.insert = lambda ignore_permissions=True: None
		doc.save = lambda ignore_permissions=True: None
		return doc

	@patch("retailedge.daily_sales_audit.get_retailedge_settings", return_value=_Settings())
	def test_daily_sales_audit_settings_normalize_safely(self, _mock_settings):
		settings = get_daily_sales_audit_settings()
		self.assertTrue(settings["enabled"])
		self.assertTrue(settings["include_cashier_expenses_preview"])
		self.assertIn("System Manager", settings["reviewer_roles"])

	@patch("retailedge.daily_sales_audit._list_closing_shifts", return_value=[])
	@patch("retailedge.daily_sales_audit._list_opening_shifts", return_value=[])
	@patch("retailedge.daily_sales_audit._list_cashiers", return_value=[])
	@patch("retailedge.daily_sales_audit._list_pos_profiles", return_value=[])
	@patch("retailedge.daily_sales_audit._list_branches", return_value=[])
	@patch("retailedge.daily_sales_audit._list_companies", return_value=[])
	def test_context_options_helper_executes_with_empty_filters(
		self,
		_mock_companies,
		_mock_branches,
		_mock_profiles,
		_mock_cashiers,
		_mock_openings,
		_mock_closings,
	):
		options = get_daily_sales_audit_context_options()
		self.assertIn("defaults", options)
		self.assertEqual(options["companies"], [])
		self.assertEqual(options["opening_shifts"], [])

	@patch("retailedge.daily_sales_audit._list_closing_shifts", return_value=[])
	@patch("retailedge.daily_sales_audit._list_opening_shifts", return_value=[])
	@patch("retailedge.daily_sales_audit._list_cashiers", return_value=[])
	@patch("retailedge.daily_sales_audit._list_pos_profiles", return_value=["Testing"])
	@patch("retailedge.daily_sales_audit._list_branches", return_value=["HQ"])
	@patch("retailedge.daily_sales_audit._list_companies", return_value=["Demo Company"])
	def test_context_options_helper_executes_with_company_filter(
		self,
		_mock_companies,
		_mock_branches,
		_mock_profiles,
		_mock_cashiers,
		_mock_openings,
		_mock_closings,
	):
		options = get_daily_sales_audit_context_options({"company": "Demo Company"})
		self.assertEqual(options["companies"], ["Demo Company"])
		self.assertEqual(options["branches"], ["HQ"])
		self.assertEqual(options["pos_profiles"], ["Testing"])

	@patch("retailedge.daily_sales_audit._list_closing_shifts", return_value=["CLOSE-1"])
	@patch("retailedge.daily_sales_audit._list_opening_shifts", return_value=["OPEN-1"])
	@patch("retailedge.daily_sales_audit._coerce_doc")
	def test_context_resolver_returns_company_profile_cashier_from_opening_shift(
		self, mock_coerce_doc, _mock_openings, _mock_closings
	):
		opening_doc = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			company="Demo Company",
			pos_profile="Testing",
			user="cashier@example.com",
			branch="HQ",
			opening_date="2026-05-15",
		)

		def _coerce(doctype, value):
			if doctype == "POS Opening Shift" and value == "OPEN-1":
				return opening_doc
			return None

		mock_coerce_doc.side_effect = _coerce
		resolved = resolve_daily_sales_audit_context_from_selection({"pos_opening_shift": "OPEN-1"})
		self.assertEqual(resolved["company"], "Demo Company")
		self.assertEqual(resolved["pos_profile"], "Testing")
		self.assertEqual(resolved["cashier"], "cashier@example.com")
		self.assertEqual(resolved["branch"], "HQ")
		self.assertEqual(resolved["pos_closing_shift"], "CLOSE-1")

	@patch("retailedge.daily_sales_audit._coerce_doc")
	def test_context_resolver_returns_opening_shift_from_closing_shift(self, mock_coerce_doc):
		closing_doc = SimpleNamespace(
			doctype="POS Closing Shift",
			name="CLOSE-1",
			company="Demo Company",
			pos_profile="Testing",
			cashier="cashier@example.com",
			linked_pos_opening_shift="OPEN-1",
			closing_date="2026-05-15",
		)

		def _coerce(doctype, value):
			if doctype == "POS Closing Shift" and value == "CLOSE-1":
				return closing_doc
			return None

		mock_coerce_doc.side_effect = _coerce
		resolved = resolve_daily_sales_audit_context_from_selection({"pos_closing_shift": "CLOSE-1"})
		self.assertEqual(resolved["pos_opening_shift"], "OPEN-1")
		self.assertEqual(resolved["company"], "Demo Company")
		self.assertEqual(resolved["pos_profile"], "Testing")

	@patch("retailedge.daily_sales_audit._coerce_doc")
	def test_missing_branch_field_does_not_crash_resolver(self, mock_coerce_doc):
		opening_doc = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			company="Demo Company",
			pos_profile="Testing",
			user="cashier@example.com",
			opening_date="2026-05-15",
		)

		def _coerce(doctype, value):
			if doctype == "POS Opening Shift" and value == "OPEN-1":
				return opening_doc
			return None

		mock_coerce_doc.side_effect = _coerce
		resolved = resolve_daily_sales_audit_context_from_selection({"pos_opening_shift": "OPEN-1"})
		self.assertEqual(resolved["company"], "Demo Company")
		self.assertEqual(resolved["pos_profile"], "Testing")

	@patch("retailedge.daily_sales_audit.frappe.get_all")
	@patch("retailedge.daily_sales_audit.frappe.get_doc")
	@patch("retailedge.daily_sales_audit.resolve_cash_payment_account")
	@patch("retailedge.daily_sales_audit.get_cashier_expenses_for_daily_audit")
	@patch("retailedge.daily_sales_audit.get_shift_cash_snapshot")
	@patch("retailedge.daily_sales_audit.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.daily_sales_audit._has_doctype", return_value=True)
	def test_daily_sales_audit_context_executes_without_mutating_source_docs(
		self,
		_mock_has_doctype,
		_mock_settings,
		mock_shift_snapshot,
		mock_expenses,
		mock_payment_account,
		mock_get_doc,
		mock_get_all,
	):
		mock_shift_snapshot.return_value = {"opening_cash": 1000, "cash_sales": 300}
		mock_expenses.return_value = [
			{
				"name": "RE-CE-1",
				"expense_date": "2026-05-14",
				"expense_category": "Transport",
				"amount": 200,
				"expense_status": "Submitted",
				"daily_audit_inclusion_status": "Included",
				"daily_audit_should_include": 1,
				"daily_audit_classification": "Cash Expense",
			}
		]
		mock_payment_account.return_value = {"payment_account": "Cash - DEMO"}
		mock_get_all.return_value = [
			{
				"name": "SINV-1",
				"posting_date": "2026-05-14",
				"customer": "Customer 1",
				"grand_total": 500,
				"outstanding_amount": 0,
				"paid_amount": 500,
			}
		]
		mock_get_doc.return_value = SimpleNamespace(
			payments=[_Row(mode_of_payment="Cash", account="Cash - DEMO", amount=500, base_amount=500)]
		)
		context = get_daily_sales_audit_context(
			{
				"company": "Demo Company",
				"audit_date": "2026-05-14",
				"pos_profile": "Testing",
				"pos_opening_shift": "OPEN-1",
			}
		)
		self.assertEqual(context["opening_cash_amount"], 1000)
		self.assertEqual(context["cash_sales_amount"], 300)
		self.assertEqual(context["cashier_expense_amount"], 200)
		self.assertEqual(context["expected_cash_amount"], 1100)
		self.assertEqual(len(context["invoice_lines"]), 1)
		self.assertEqual(len(context["payment_lines"]), 1)
		self.assertEqual(len(context["cashier_expense_lines"]), 1)

	@patch("retailedge.daily_sales_audit.append_daily_sales_audit_action_log")
	@patch("retailedge.daily_sales_audit.frappe.new_doc")
	@patch("retailedge.daily_sales_audit.get_daily_sales_audit_context")
	@patch("retailedge.daily_sales_audit.user_is_daily_sales_audit_reviewer", return_value=True)
	@patch("retailedge.daily_sales_audit.get_retailedge_settings", return_value=_Settings())
	@patch("retailedge.daily_sales_audit.frappe.db.get_value", return_value=None)
	def test_draft_creation_creates_only_daily_sales_audit(
		self,
		_mock_existing,
		_mock_settings,
		_mock_reviewer,
		mock_context,
		mock_new_doc,
		mock_log,
	):
		mock_context.return_value = {
			"company": "Demo Company",
			"audit_date": "2026-05-14",
			"branch": "HQ",
			"pos_profile": "Testing",
			"cashier": "cashier@example.com",
			"pos_opening_shift": "OPEN-1",
			"pos_closing_shift": None,
			"opening_cash_amount": 1000,
			"cash_sales_amount": 300,
			"cashier_expense_amount": 200,
			"expected_cash_amount": 1100,
			"actual_closing_cash_amount": 0,
			"cash_variance_amount": -1100,
			"total_sales_amount": 500,
			"total_cash_payment_amount": 500,
			"total_bank_transfer_amount": 0,
			"total_card_pos_amount": 0,
			"total_mobile_money_amount": 0,
			"total_other_payment_amount": 0,
			"invoice_count": 1,
			"paid_invoice_count": 1,
			"unpaid_invoice_count": 0,
			"partially_paid_invoice_count": 0,
			"exception_count": 1,
			"invoice_lines": [{"sales_invoice": "SINV-1"}],
			"payment_lines": [{"source_document": "SINV-1"}],
			"cashier_expense_lines": [{"cashier_expense": "RE-CE-1"}],
		}
		doc = self._make_audit_doc(name="RE-DSA-2026-0001")
		mock_new_doc.return_value = doc
		name = create_daily_sales_audit_draft({"company": "Demo Company", "audit_date": "2026-05-14"})
		self.assertEqual(name, "RE-DSA-2026-0001")
		self.assertEqual(doc.company, "Demo Company")
		self.assertEqual(doc.expected_cash_amount, 1100)
		self.assertEqual(len(doc.invoice_lines), 1)
		self.assertEqual(len(doc.payment_lines), 1)
		self.assertEqual(len(doc.cashier_expense_lines), 1)
		mock_log.assert_called_once()

	@patch("retailedge.daily_sales_audit.append_daily_sales_audit_action_log")
	@patch("retailedge.daily_sales_audit.get_daily_sales_audit_context")
	@patch("retailedge.daily_sales_audit.frappe.get_doc")
	@patch("retailedge.daily_sales_audit.user_is_daily_sales_audit_reviewer", return_value=True)
	def test_refresh_preview_updates_only_daily_sales_audit_draft(
		self, _mock_reviewer, mock_get_doc, mock_context, mock_log
	):
		mock_context.return_value = {
			"company": "Demo Company",
			"audit_date": "2026-05-14",
			"branch": "HQ",
			"pos_profile": "Testing",
			"cashier": "cashier@example.com",
			"pos_opening_shift": "OPEN-1",
			"pos_closing_shift": None,
			"opening_cash_amount": 1000,
			"cash_sales_amount": 300,
			"cashier_expense_amount": 200,
			"expected_cash_amount": 1100,
			"actual_closing_cash_amount": 0,
			"cash_variance_amount": -1100,
			"total_sales_amount": 500,
			"total_cash_payment_amount": 500,
			"total_bank_transfer_amount": 0,
			"total_card_pos_amount": 0,
			"total_mobile_money_amount": 0,
			"total_other_payment_amount": 0,
			"invoice_count": 1,
			"paid_invoice_count": 1,
			"unpaid_invoice_count": 0,
			"partially_paid_invoice_count": 0,
			"exception_count": 1,
			"invoice_lines": [],
			"payment_lines": [],
			"cashier_expense_lines": [],
		}
		doc = self._make_audit_doc(
			name="RE-DSA-2026-0002",
			docstatus=0,
			audit_status="Draft",
			company="Demo Company",
			audit_date="2026-05-14",
			branch="HQ",
			pos_profile="Testing",
			cashier="cashier@example.com",
			pos_opening_shift="OPEN-1",
			pos_closing_shift=None,
		)
		mock_get_doc.return_value = doc
		name = refresh_daily_sales_audit_preview("RE-DSA-2026-0002")
		self.assertEqual(name, "RE-DSA-2026-0002")
		self.assertEqual(doc.expected_cash_amount, 1100)
		mock_log.assert_called_once()

	@patch("retailedge.retailedge.doctype.retailedge_daily_sales_audit.retailedge_daily_sales_audit.append_daily_sales_audit_action_log")
	def test_daily_sales_audit_cancel_sets_status_cancelled(self, mock_log):
		doc = self._make_audit_doc(audit_status="Draft")
		doc.before_submit = RetailEdgeDailySalesAudit.before_submit.__get__(doc, _Doc)
		doc.on_submit = RetailEdgeDailySalesAudit.on_submit.__get__(doc, _Doc)
		doc.before_cancel = RetailEdgeDailySalesAudit.before_cancel.__get__(doc, _Doc)
		doc.on_cancel = RetailEdgeDailySalesAudit.on_cancel.__get__(doc, _Doc)
		doc.before_cancel()
		doc.on_cancel()
		self.assertEqual(doc.audit_status, "Cancelled")
		mock_log.assert_called_once()

	@patch("retailedge.retailedge.report.retailedge_daily_sales_audit_register.retailedge_daily_sales_audit_register.frappe.get_all")
	def test_daily_sales_audit_register_report_executes(self, mock_get_all):
		mock_get_all.return_value = [
			{
				"name": "RE-DSA-2026-0001",
				"audit_date": "2026-05-14",
				"company": "Demo Company",
				"branch": "HQ",
				"pos_profile": "Testing",
				"cashier": "cashier@example.com",
				"pos_opening_shift": "OPEN-1",
				"pos_closing_shift": "CLOSE-1",
				"opening_cash_amount": 1000,
				"cash_sales_amount": 300,
				"cashier_expense_amount": 200,
				"expected_cash_amount": 1100,
				"actual_closing_cash_amount": 1100,
				"cash_variance_amount": 0,
				"audit_status": "Draft",
				"audit_result": "Balanced",
				"review_required": 1,
			}
		]
		columns, data = execute_daily_sales_audit_register_report({"company": "Demo Company"})
		self.assertTrue(columns)
		self.assertEqual(len(data), 1)
		self.assertEqual(data[0]["name"], "RE-DSA-2026-0001")


class BranchContextTests(unittest.TestCase):
	@patch("retailedge.branch_context.has_doctype", return_value=False)
	def test_has_field_safely_returns_false_for_missing_field(self, _mock_doctype):
		self.assertFalse(branch_context_has_field("Missing DocType", "branch"))

	def test_resolver_returns_explicit_branch_when_provided(self):
		result = resolve_retailedge_branch_context(branch="HQ", company="Demo Company")
		self.assertEqual(result["branch"], "HQ")
		self.assertTrue(result["access"]["allowed"])

	@patch("retailedge.branch_context.get_coreedge_status", return_value={"branch_context_enabled": False})
	def test_resolver_does_not_crash_when_coreedge_unavailable(self, _mock_status):
		result = resolve_retailedge_branch_context(company="Demo Company")
		self.assertIn("messages", result)

	@patch("retailedge.branch_context._coerce_doc")
	@patch("retailedge.branch_context.get_first_existing_field")
	def test_resolver_reads_pos_profile_branch_when_field_exists(self, mock_first_field, mock_doc):
		mock_doc.return_value = _Doc(doctype="POS Profile", name="POS-1", branch="HQ", company="Demo Company")
		mock_first_field.side_effect = lambda doctype, fields: "branch" if "branch" in fields else "company"
		result = resolve_branch_from_pos_profile("POS-1")
		self.assertEqual(result["branch"], "HQ")
		self.assertEqual(result["source"], "POS Profile.branch")

	@patch("retailedge.branch_context.has_doctype", return_value=False)
	@patch("retailedge.branch_context._get_coreedge_allowed_branches", return_value=[])
	@patch("retailedge.branch_context.frappe.defaults.get_user_default", return_value=None)
	def test_get_user_allowed_branches_returns_safe_structure(
		self, _mock_default_branch, _mock_coreedge_allowed, _mock_has_doctype
	):
		result = get_branch_context_allowed_branches(user="cashier@example.com")
		self.assertIn("branches", result)
		self.assertIsInstance(result["branches"], list)

	@patch("retailedge.branch_context.frappe.get_roles", return_value=["System Manager"])
	def test_validate_user_branch_access_allows_system_manager(self, _mock_roles):
		self.assertTrue(user_has_global_branch_access(user="manager@example.com"))
		result = validate_user_branch_access("HQ", user="manager@example.com", throw=False)
		self.assertTrue(result["allowed"])

	@patch("retailedge.branch_context.validate_user_branch_access", return_value={"allowed": True, "reason": "allowed_branch"})
	@patch("retailedge.branch_context.resolve_retailedge_branch_context")
	def test_apply_branch_context_to_doc_sets_branch_when_empty(self, mock_resolve, _mock_access):
		mock_resolve.return_value = {
			"branch": "HQ",
			"source": "POS Opening Shift.branch",
			"source_map": {"branch": "POS Opening Shift.branch"},
			"messages": [],
		}
		doc = _Doc(doctype="RetailEdge Daily Sales Audit", branch=None, company="Demo Company", cashier="cashier@example.com")
		result = apply_branch_context_to_doc(doc, overwrite=False, validate_access=True)
		self.assertEqual(doc.branch, "HQ")
		self.assertEqual(result["branch"], "HQ")

	@patch("retailedge.branch_context.user_has_global_branch_access", return_value=True)
	def test_get_branch_query_filters_returns_no_restriction_for_global_role(self, _mock_global):
		result = get_branch_query_filters("RetailEdge Cashier Expense", user="Administrator")
		self.assertEqual(result["filters"], {})

	def test_get_branch_query_filters_returns_explicit_branch_filter(self):
		result = get_branch_query_filters("RetailEdge Cashier Expense", branch="HQ")
		self.assertEqual(result["filters"], {"branch": "HQ"})

	@patch("retailedge.branch_context.resolve_retailedge_branch_context", return_value={"branch": "HQ", "source": "POS Opening Shift.branch", "messages": []})
	@patch("retailedge.branch_context.frappe.db.set_value")
	@patch("retailedge.branch_context.frappe.get_all")
	@patch("retailedge.branch_context.has_field", return_value=True)
	@patch("retailedge.branch_context.has_doctype", return_value=True)
	def test_backfill_dry_run_does_not_update_records(
		self,
		_mock_doctype,
		_mock_has_field,
		mock_get_all,
		mock_set_value,
		_mock_resolve,
	):
		mock_get_all.return_value = [{"name": "RE-CE-1", "company": "Demo Company", "branch": None}]
		result = backfill_retailedge_branch_context(doctype="RetailEdge Cashier Expense", dry_run=True, limit=10)
		self.assertTrue(result["dry_run"])
		self.assertEqual(result["updated"], 0)
		mock_set_value.assert_not_called()

	@patch("retailedge.branch_context.resolve_branch_from_branch_profile")
	def test_branch_context_can_use_branch_profile_fallback(self, mock_profile):
		mock_profile.return_value = {
			"branch": "HQ",
			"company": "Demo Company",
			"pos_profile": "Testing",
			"source": "RetailEdge Branch Profile",
			"messages": [],
			"defaults": {"default_pos_profile": "Testing"},
		}
		result = resolve_retailedge_branch_context(company="Demo Company", user="cashier@example.com")
		self.assertEqual(result["branch"], "HQ")

	@patch("retailedge.branch_context.resolve_branch_from_branch_profile")
	def test_operational_defaults_return_branch_profile_defaults(self, mock_profile):
		mock_profile.return_value = {
			"branch": "HQ",
			"company": "Demo Company",
			"pos_profile": "Testing",
			"source": "RetailEdge Branch Profile",
			"messages": [],
			"defaults": {"default_pos_profile": "Testing", "default_cost_center": "Main - PED"},
		}
		result = resolve_retailedge_operational_defaults(company="Demo Company", branch="HQ")
		self.assertEqual(result["default_pos_profile"], "Testing")
		self.assertEqual(result["branch"], "HQ")


class BranchProfileTests(unittest.TestCase):
	def test_branch_profile_doctype_exists(self):
		self.assertTrue(branch_context_has_doctype("RetailEdge Branch Profile"))

	def test_branch_profile_user_child_doctype_exists(self):
		self.assertTrue(branch_context_has_doctype("RetailEdge Branch Profile User"))

	@patch("retailedge.branch_profile.frappe.db.exists", return_value=False)
	def test_optional_defaults_are_not_mandatory(self, _mock_exists):
		doc = _Doc(doctype="RetailEdge Branch Profile", name="HQ Default", company="Demo Company", branch="HQ", enabled=1, is_default_for_company=0)
		self.assertIsNone(validate_branch_profile(doc))

	@patch("retailedge.branch_profile.frappe.db.exists")
	def test_duplicate_enabled_company_branch_profile_is_blocked(self, mock_exists):
		mock_exists.side_effect = [True]
		doc = _Doc(doctype="RetailEdge Branch Profile", name="HQ Default", company="Demo Company", branch="HQ", enabled=1, is_default_for_company=0)
		with self.assertRaises(frappe.ValidationError):
			validate_branch_profile(doc)

	@patch("retailedge.branch_profile.frappe.db.exists")
	def test_only_one_default_profile_per_company_is_allowed(self, mock_exists):
		mock_exists.side_effect = [False, True]
		doc = _Doc(doctype="RetailEdge Branch Profile", name="HQ Default", company="Demo Company", branch="HQ", enabled=1, is_default_for_company=1)
		with self.assertRaises(frappe.ValidationError):
			validate_branch_profile(doc)

	@patch("retailedge.branch_profile._get_profile_by_filters")
	def test_get_branch_profile_works(self, mock_get_profile):
		mock_get_profile.return_value = _Doc(
			doctype="RetailEdge Branch Profile",
			name="HQ Default",
			company="Demo Company",
			branch="HQ",
			default_pos_profile="Testing",
			default_cashiers=[],
			default_managers=[],
			default_auditors=[],
		)
		profile = get_branch_profile(company="Demo Company", branch="HQ")
		self.assertEqual(profile.branch, "HQ")

	@patch("retailedge.branch_profile.get_branch_profile")
	def test_get_branch_profile_defaults_works(self, mock_get_profile):
		mock_get_profile.return_value = _Doc(
			doctype="RetailEdge Branch Profile",
			name="HQ Default",
			default_pos_profile="Testing",
			default_cost_center="Main - PED",
			enable_daily_sales_audit=1,
		)
		defaults = get_branch_profile_defaults(company="Demo Company", branch="HQ")
		self.assertEqual(defaults["default_pos_profile"], "Testing")
		self.assertEqual(defaults["default_cost_center"], "Main - PED")

	@patch("retailedge.branch_profile.frappe.get_all")
	@patch("retailedge.branch_profile._has_doctype", return_value=True)
	def test_get_user_branch_profiles_and_default_branch_for_user(self, _mock_has_doctype, mock_get_all):
		mock_get_all.side_effect = [
			[{"parent": "HQ Default", "role_type": "Cashier", "is_default": 1}],
			[{"name": "HQ Default", "profile_name": "HQ Default", "company": "Demo Company", "branch": "HQ", "enabled": 1, "is_default_for_company": 1, "default_pos_profile": "Testing"}],
			[{"parent": "HQ Default", "role_type": "Cashier", "is_default": 1}],
			[{"name": "HQ Default", "profile_name": "HQ Default", "company": "Demo Company", "branch": "HQ", "enabled": 1, "is_default_for_company": 1, "default_pos_profile": "Testing"}],
		]
		profiles = get_user_branch_profiles(user="cashier@example.com", company="Demo Company")
		self.assertEqual(len(profiles), 1)
		self.assertEqual(get_default_branch_for_user(user="cashier@example.com", company="Demo Company"), "HQ")

	def test_workspace_json_contains_required_order_and_labels(self):
		import json
		from pathlib import Path

		path = Path("/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/workspace/retailedge/retailedge.json")
		data = json.loads(path.read_text())
		link_labels = [row.get("label") for row in data.get("links", []) if row.get("type") == "Card Break"]
		self.assertEqual(link_labels, ["Operations", "Reports & Review", "Setup / Configuration"])
		shortcut_labels = [row.get("label") for row in data.get("shortcuts", [])]
		self.assertIn("Cashier Expense", shortcut_labels)
		self.assertIn("Daily Sales Audit", shortcut_labels)
		self.assertIn("Settings", shortcut_labels)
		self.assertIn("Branch Profile", shortcut_labels)
		self.assertNotIn("RetailEdge Cashier Expense", shortcut_labels)

	def test_workspace_sidebar_sync_uses_grouped_sections(self):
		from retailedge.patches.sync_retailedge_workspace import _sync_workspace_sidebar

		workspace = _Doc(
			doctype="Workspace",
			name="RetailEdge",
			module="RetailEdge",
			icon="setting-gear",
			links=[
				_Doc(type="Card Break", label="Operations"),
				_Doc(type="Link", label="Cashier Expense", link_to="RetailEdge Cashier Expense", link_type="DocType"),
				_Doc(type="Card Break", label="Reports & Review"),
				_Doc(type="Link", label="Cashier Expense Review", link_to="RetailEdge Cashier Expense Review", link_type="Report"),
				_Doc(type="Card Break", label="Setup / Configuration"),
				_Doc(type="Link", label="Settings", link_to="RetailEdge Settings", link_type="DocType"),
			],
		)
		with patch("retailedge.patches.sync_retailedge_workspace._get_or_create_workspace_sidebar") as mock_sidebar:
			sidebar = _Doc(doctype="Workspace Sidebar", name="RetailEdge", items=[])
			sidebar.save = Mock()
			mock_sidebar.return_value = sidebar
			_sync_workspace_sidebar(workspace)

		self.assertEqual(
			[(item.type, item.label, item.child) for item in sidebar.items],
			[
				("Link", "Home", 0),
				("Section Break", "Operations", 0),
				("Link", "Cashier Expense", 1),
				("Section Break", "Reports & Review", 0),
				("Link", "Cashier Expense Review", 1),
				("Section Break", "Setup / Configuration", 0),
				("Link", "Settings", 1),
			],
		)

	def test_standard_workspace_sidebar_json_exists_and_is_grouped(self):
		import json
		from pathlib import Path

		paths = [
			Path("/home/olayemigod/frappe-bench/apps/retailedge/retailedge/workspace_sidebar/retailedge.json"),
			Path("/home/olayemigod/frappe-bench/apps/retailedge/retailedge/retailedge/workspace_sidebar/retailedge/retailedge.json"),
		]
		for path in paths:
			self.assertTrue(path.exists(), f"Missing standard sidebar fixture: {path}")
		data = json.loads(paths[0].read_text())
		self.assertEqual(data.get("doctype"), "Workspace Sidebar")
		self.assertEqual(data.get("app"), "retailedge")
		self.assertEqual(data.get("standard"), 1)
		self.assertEqual(
			[(row.get("type"), row.get("label"), row.get("child", 0)) for row in data.get("items", [])],
			[
				("Link", "Home", 0),
				("Section Break", "Operations", 0),
				("Link", "Cashier Expense", 1),
				("Link", "Daily Sales Audit", 1),
				("Section Break", "Reports & Review", 0),
				("Link", "Cashier Expense Review", 1),
				("Link", "Daily Sales Audit Register", 1),
				("Link", "POS Closing Variance vs Expenses", 1),
				("Section Break", "Setup / Configuration", 0),
				("Link", "Settings", 1),
				("Link", "Branch Profile", 1),
				("Link", "Expense Category", 1),
			],
		)
