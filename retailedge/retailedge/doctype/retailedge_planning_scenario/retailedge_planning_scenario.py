from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, today

from retailedge.branch_context import validate_user_branch_access
from retailedge.forecasting import MAX_FORECAST_HORIZON


class RetailEdgePlanningScenario(Document):
	def validate(self):
		self.scenario_name = str(self.scenario_name or "").strip()
		if not self.scenario_name:
			frappe.throw(_("Scenario Name is required."))
		if not self.company:
			frappe.throw(_("Company is required."))
		if not frappe.has_permission("Company", "read", doc=self.company):
			frappe.throw(_("You do not have permission to use Company {0}.").format(self.company), frappe.PermissionError)
		if self.branch:
			validate_user_branch_access(self.branch, user=frappe.session.user, company=self.company, throw=True)

		self.as_of_date = getdate(self.as_of_date or today())
		if self.as_of_date > getdate(today()):
			frappe.throw(_("As of Date cannot be in the future."))
		self.history_months = cint(self.history_months or 6)
		self.horizon_months = cint(self.horizon_months or 3)
		if self.history_months < 3 or self.history_months > 24:
			frappe.throw(_("History Months must be between 3 and 24."))
		if self.horizon_months < 1 or self.horizon_months > MAX_FORECAST_HORIZON:
			frappe.throw(_("Forecast Horizon must be between 1 and {0} months.").format(MAX_FORECAST_HORIZON))

		for fieldname, label, minimum, maximum in (
			("sales_adjustment_percent", _("Sales Plan Adjustment"), -100, 1000),
			("expense_adjustment_percent", _("Expense Plan Adjustment"), -100, 1000),
			("cash_adjustment_percent", _("Cash Movement Adjustment"), -100, 1000),
			("inventory_safety_percent", _("Inventory Safety Allowance"), 0, 500),
		):
			value = flt(self.get(fieldname))
			if value < minimum or value > maximum:
				frappe.throw(_("{0} must be between {1}% and {2}%.").format(label, minimum, maximum))
			self.set(fieldname, value)
