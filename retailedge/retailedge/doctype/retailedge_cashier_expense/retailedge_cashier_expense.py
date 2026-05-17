from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

from retailedge.branch_context import apply_branch_context_to_doc
from retailedge.cashier_context import get_current_cashier_context, get_shift_cash_snapshot
from retailedge.cashier_expense import append_cashier_expense_action_log
from retailedge.cashier_expense_posting import (
	build_cashier_expense_posting_preview,
	refresh_cashier_expense_posting_readiness,
)
from retailedge.utils.settings import get_retailedge_settings


class RetailEdgeCashierExpense(Document):
	def before_validate(self):
		self.set_cashier_defaults()
		apply_branch_context_to_doc(self, overwrite=False, validate_access=False)
		self.apply_expense_category()
		self.apply_shift_cash_snapshot()

	def validate(self):
		apply_branch_context_to_doc(self, overwrite=False, validate_access=True)
		self.validate_open_shift_requirement()
		self.validate_cash_account_requirement()
		self.validate_required_values()
		self.validate_cash_availability()
		self.set_posting_readiness_preview()

	def after_insert(self):
		refresh_cashier_expense_posting_readiness(self.name)

	def before_submit(self):
		self._status_before_submit = self.expense_status or "Draft"
		if not self.expense_status or self.expense_status == "Draft":
			self.expense_status = "Submitted"
		if not self.ledger_status:
			self.ledger_status = "Not Applicable"
		self.set_posting_readiness_preview()

	def on_submit(self):
		previous_status = getattr(self, "_status_before_submit", None) or "Draft"
		self.set_posting_readiness_preview()
		append_cashier_expense_action_log(
			self,
			action="Submitted",
			previous_status=previous_status,
			new_status=self.expense_status,
			context={"ledger_status": self.ledger_status},
		)

	def before_cancel(self):
		self._status_before_cancel = self.expense_status
		self.expense_status = "Cancelled"
		self.set_posting_readiness_preview()

	def on_cancel(self):
		previous_status = getattr(self, "_status_before_cancel", None) or self.expense_status
		self.set_posting_readiness_preview()
		append_cashier_expense_action_log(
			self,
			action="Cancelled",
			previous_status=previous_status,
			new_status=self.expense_status,
			context={"ledger_status": self.ledger_status},
		)

	def set_cashier_defaults(self):
		settings = get_retailedge_settings()
		if not self.expense_status:
			self.expense_status = "Draft"
		if not self.ledger_status:
			self.ledger_status = "Not Applicable"
		if self.include_in_daily_audit in (None, ""):
			self.include_in_daily_audit = 1
		if not self.daily_audit_inclusion_status:
			self.daily_audit_inclusion_status = "Pending Review"
		if not self.daily_audit_classification:
			self.daily_audit_classification = "Cash Expense"
		if not self.cashier:
			self.cashier = frappe.session.user

		today_value = today()
		if not self.expense_date:
			self.expense_date = today_value
		elif self.is_new() and not getattr(settings, "allow_cashier_expense_date_edit", 0):
			self.expense_date = today_value

		context = get_current_cashier_context(user=self.cashier, company=self.company)
		self._cashier_context = context
		if not self.company and context.get("company"):
			self.company = context["company"]
		if not self.branch and context.get("branch"):
			self.branch = context["branch"]
		if not self.pos_profile and context.get("pos_profile"):
			self.pos_profile = context["pos_profile"]
		if not self.linked_pos_opening_shift and context.get("linked_pos_opening_shift"):
			self.linked_pos_opening_shift = context["linked_pos_opening_shift"]
		if not self.payment_account and context.get("payment_account"):
			self.payment_account = context["payment_account"]
		if not self.cost_center and context.get("cost_center"):
			self.cost_center = context["cost_center"]
		if context.get("message"):
			self.cash_control_message = context["message"]

	def apply_expense_category(self):
		if not self.expense_category:
			return

		category = frappe.db.get_value(
			"RetailEdge Expense Category",
			self.expense_category,
			["company", "expense_account", "default_cost_center"],
			as_dict=True,
		)
		if not category:
			return

		if not self.company and category.get("company"):
			self.company = category["company"]
		self.expense_account = category.get("expense_account")
		if category.get("default_cost_center") and self._should_use_category_cost_center(category.get("default_cost_center")):
			self.cost_center = category["default_cost_center"]

	def apply_shift_cash_snapshot(self):
		settings = get_retailedge_settings()
		if not self.linked_pos_opening_shift:
			self.shift_opening_cash_amount = 0
			self.shift_cash_sales_amount = 0
			self.prior_shift_expense_amount = 0
			self.available_shift_cash_before_expense = 0
			self.available_shift_cash_after_expense = 0
			self.cash_balance_source = None
			if getattr(settings, "require_open_shift_for_cashier_expense", 1):
				self.cash_control_message = (
					"No open POS Opening Shift found for your user. Please open a POS shift before recording cashier expenses."
				)
			return

		snapshot = get_shift_cash_snapshot(
			opening_shift=self.linked_pos_opening_shift,
			company=self.company,
			pos_profile=self.pos_profile,
			user=self.cashier,
			expense_name=None if self.is_new() else self.name,
		)
		self.shift_opening_cash_amount = snapshot.get("opening_cash", 0)
		self.shift_cash_sales_amount = snapshot.get("cash_sales", 0)
		self.prior_shift_expense_amount = snapshot.get("prior_expenses", 0)
		self.available_shift_cash_before_expense = snapshot.get("available_before", 0)
		self.available_shift_cash_after_expense = flt(snapshot.get("available_before", 0)) - flt(self.amount)
		self.cash_balance_source = snapshot.get("source")
		if snapshot.get("message"):
			self.cash_control_message = snapshot["message"]

	def validate_open_shift_requirement(self):
		settings = get_retailedge_settings()
		if getattr(settings, "require_open_shift_for_cashier_expense", 1) and not self.linked_pos_opening_shift:
			frappe.throw(
				"No open POS Opening Shift found for your user. Please open a POS shift before recording cashier expenses."
			)

	def validate_cash_account_requirement(self):
		settings = get_retailedge_settings()
		if not getattr(settings, "allow_cashier_expense_without_cash_account", 0) and not self.payment_account:
			frappe.throw(
				"RetailEdge could not resolve the cash payment account for your current shift/POS profile. Please configure the cash mode of payment/account before recording cashier expenses."
			)

	def validate_required_values(self):
		settings = get_retailedge_settings()
		if not self.expense_category:
			frappe.throw("Expense Category is required.")
		if not self.amount or flt(self.amount) <= 0:
			frappe.throw("Amount must be greater than zero.")
		if not self.company:
			frappe.throw("Company is required.")
		if not self.cashier:
			frappe.throw("Cashier is required.")
		if not self.expense_date:
			frappe.throw("Expense Date is required.")
		if self.is_new() and not getattr(settings, "allow_cashier_expense_date_edit", 0):
			self.expense_date = today()
		if not self.expense_account:
			frappe.throw("Expense Account could not be resolved from the selected Expense Category.")

	def validate_cash_availability(self):
		if not self.linked_pos_opening_shift:
			return

		available = flt(self.available_shift_cash_before_expense)
		amount = flt(self.amount)
		if amount > available:
			frappe.throw(
				f"Insufficient shift cash. Available cash for this shift is {available}. Expense amount is {amount}."
			)

	def set_posting_readiness_preview(self):
		preview = build_cashier_expense_posting_preview(self)
		self.posting_ready = 1 if preview.get("posting_ready") else 0
		self.posting_block_reason = preview.get("posting_block_reason")
		self.resolved_debit_account = preview.get("debit_account")
		self.resolved_credit_account = preview.get("credit_account")
		self.resolved_posting_cost_center = preview.get("cost_center")
		self.posting_preview = preview.get("posting_preview") or None
		self.review_required = 1 if self.docstatus == 1 and self.expense_status in {"Submitted", "Rejected", "Pending Ledger"} else 0
		if self.expense_status == "Pending Ledger":
			self.user_message = (
				"This expense is approved for future ledger posting, but actual posting is not enabled in this phase."
			)
		elif self.posting_block_reason:
			self.user_message = self.posting_block_reason
		else:
			self.user_message = None

	def _should_use_category_cost_center(self, category_cost_center):
		if not category_cost_center:
			return False
		if not self.cost_center:
			return True
		if not self._is_valid_cost_center_for_company(self.cost_center, self.company):
			return True
		context_source = (getattr(self, "_cashier_context", {}) or {}).get("cost_center_source")
		return context_source in {"company", "single_company_cost_center", "main_cost_center", "not_found"}

	def _is_valid_cost_center_for_company(self, cost_center, company):
		if not cost_center:
			return False
		try:
			if not frappe.db.exists("Cost Center", cost_center):
				return False
		except Exception:
			return False
		try:
			meta = frappe.get_meta("Cost Center")
		except Exception:
			return True
		if meta.has_field("company"):
			try:
				cost_center_company = frappe.db.get_value("Cost Center", cost_center, "company")
			except Exception:
				return False
			if company and cost_center_company and cost_center_company != company:
				return False
		if meta.has_field("is_group"):
			try:
				if frappe.db.get_value("Cost Center", cost_center, "is_group"):
					return False
			except Exception:
				return False
		return True
