from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
	get_cashier_roles,
	get_cashier_expenses_for_variance,
	get_cashier_expense_totals_for_variance,
	get_cashier_expense_summary,
	get_reviewer_roles,
	reject_cashier_expense,
	reopen_cashier_expense,
	submit_cashier_expense,
	user_has_any_role,
	user_is_reviewer,
)
from retailedge.cashier_expense_posting import (
	get_cashier_expense_posting_preview,
	refresh_cashier_expense_posting_readiness,
)
from retailedge.events.pos_closing_shift import update_cashier_expenses_with_closing_shift
from retailedge.retailedge.report.pos_closing_variance_vs_expenses.pos_closing_variance_vs_expenses import (
	get_retailedge_cashier_expense_context,
)
from retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense import (
	RetailEdgeCashierExpense,
)


class _Settings(SimpleNamespace):
	require_open_shift_for_cashier_expense = 1
	allow_cashier_expense_date_edit = 0
	include_draft_cashier_expenses_in_cash_check = 1
	include_rejected_cashier_expenses_in_cash_check = 1
	allow_cashier_expense_without_cash_account = 0
	enable_cashier_expense_accounting_posting = 0
	cashier_expense_posting_document_type = "Journal Entry"
	default_cashier_expense_payable_account = None
	require_cashier_expense_approval_before_posting = 1
	allow_rejected_cashier_expense_posting = 0
	cashier_expense_posting_remark_template = "RetailEdge Cashier Expense {expense_name} - {expense_category}"


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
		doc.on_submit = RetailEdgeCashierExpense.on_submit.__get__(doc, _Doc)
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
	def test_on_submit_sets_submitted_status(self, mock_log):
		doc = self._make_doc(expense_status="Draft", ledger_status=None)
		doc.on_submit()
		self.assertEqual(doc.expense_status, "Submitted")
		self.assertEqual(doc.ledger_status, "Not Applicable")
		mock_log.assert_called_once()

	@patch("retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.append_cashier_expense_action_log")
	def test_on_cancel_sets_cancelled_status(self, mock_log):
		doc = self._make_doc(expense_status="Submitted")
		doc.on_cancel()
		self.assertEqual(doc.expense_status, "Cancelled")
		mock_log.assert_called_once()

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

	@patch("retailedge.cashier_context._coerce_doc")
	def test_resolve_branch_uses_user_default_when_profile_and_shift_lack_branch(self, mock_coerce_doc):
		mock_coerce_doc.return_value = SimpleNamespace(doctype="POS Profile")
		with patch("retailedge.cashier_context._get_coreedge_branch_value", return_value=None):
			with patch.object(frappe.defaults, "get_user_default", return_value="Main Branch"):
				result = resolve_branch(company="Demo Company", pos_profile="PROFILE-1", opening_shift=None, user="cashier@example.com")
		self.assertEqual(result["branch"], "Main Branch")
		self.assertEqual(result["source"], "user_default")

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

	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_excludes_cancelled_by_default(self, mock_get_all):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance()
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["!=", "Cancelled"])
		self.assertEqual(filters["docstatus"], ["!=", 2])

	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_includes_rejected_by_default(self, mock_get_all):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance()
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["!=", "Cancelled"])

	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_can_exclude_rejected(self, mock_get_all):
		mock_get_all.return_value = []
		get_cashier_expenses_for_variance(include_rejected=False)
		filters = mock_get_all.call_args.kwargs["filters"]
		self.assertEqual(filters["expense_status"], ["not in", ["Cancelled", "Rejected"]])

	@patch("retailedge.cashier_expense.frappe.get_all")
	def test_get_cashier_expenses_for_variance_supports_shift_filters(self, mock_get_all):
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
