from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class RetailEdgeExpenseCategory(Document):
	def before_validate(self):
		self._infer_company_from_accounting_defaults()

	def validate(self):
		self._validate_expense_account()
		self._validate_default_cost_center()

	def _infer_company_from_accounting_defaults(self):
		if self.company:
			return

		account = self._get_expense_account_context()
		cost_center = self._get_cost_center_context()
		self.company = (account or {}).get("company") or (cost_center or {}).get("company") or None

	def _validate_expense_account(self):
		if not self.expense_account:
			return

		account = self._get_expense_account_context()
		if not account:
			frappe.throw(_("Expense Account {0} does not exist.").format(self.expense_account))
		if cint(account.get("is_group")):
			frappe.throw(_("Expense Account {0} must be a ledger account, not a group.").format(self.expense_account))
		if cint(account.get("disabled")):
			frappe.throw(_("Expense Account {0} is disabled.").format(self.expense_account))
		if account.get("root_type") and account.get("root_type") != "Expense":
			frappe.throw(_("Expense Account {0} must belong to the Expense root type.").format(self.expense_account))
		if self.company and account.get("company") and account.get("company") != self.company:
			frappe.throw(
				_("Expense Account {0} belongs to Company {1}, not Company {2}.").format(
					self.expense_account,
					account.get("company"),
					self.company,
				)
			)

	def _validate_default_cost_center(self):
		if not self.default_cost_center:
			return

		cost_center = self._get_cost_center_context()
		if not cost_center:
			frappe.throw(_("Default Cost Center {0} does not exist.").format(self.default_cost_center))
		if cint(cost_center.get("is_group")):
			frappe.throw(
				_("Default Cost Center {0} must be a leaf cost center, not a group.").format(
					self.default_cost_center
				)
			)
		if self.company and cost_center.get("company") and cost_center.get("company") != self.company:
			frappe.throw(
				_("Default Cost Center {0} belongs to Company {1}, not Company {2}.").format(
					self.default_cost_center,
					cost_center.get("company"),
					self.company,
				)
			)

	def _get_expense_account_context(self):
		if not self.expense_account:
			return None
		if getattr(self, "_expense_account_context_name", None) == self.expense_account:
			return getattr(self, "_expense_account_context", None)

		context = frappe.db.get_value(
			"Account",
			self.expense_account,
			["company", "root_type", "is_group", "disabled"],
			as_dict=True,
		)
		self._expense_account_context_name = self.expense_account
		self._expense_account_context = context
		return context

	def _get_cost_center_context(self):
		if not self.default_cost_center:
			return None
		if getattr(self, "_cost_center_context_name", None) == self.default_cost_center:
			return getattr(self, "_cost_center_context", None)

		context = frappe.db.get_value(
			"Cost Center",
			self.default_cost_center,
			["company", "is_group"],
			as_dict=True,
		)
		self._cost_center_context_name = self.default_cost_center
		self._cost_center_context = context
		return context
