from __future__ import annotations

import frappe
from frappe.model.document import Document

from retailedge.branch_context import apply_branch_context_to_doc
from retailedge.daily_sales_audit import (
	_assert_opening_shift_not_already_audited,
	append_daily_sales_audit_action_log,
	calculate_daily_sales_audit_variance,
	refresh_daily_sales_audit_review_summary,
	resolve_daily_sales_audit_context_from_selection,
)


class RetailEdgeDailySalesAudit(Document):
	def validate(self):
		if not self.audit_status:
			self.audit_status = "Draft"
		if not self.audit_result:
			self.audit_result = "Not Checked"
		if self.review_required in (None, ""):
			self.review_required = 1
		if not self.company:
			self.company = None
		if not self.audit_date:
			self.audit_date = None
		apply_branch_context_to_doc(self, overwrite=False, validate_access=True)
		_assert_opening_shift_not_already_audited(self.pos_opening_shift, exclude_name=self.name)
		calculate_daily_sales_audit_variance(self)
		refresh_daily_sales_audit_review_summary(self)
		self._validate_context_consistency()

	def before_submit(self):
		self._status_before_submit = self.audit_status or "Draft"
		if self.audit_status in {"", "Draft"}:
			self.audit_status = "Ready for Review"
		refresh_daily_sales_audit_review_summary(self)

	def on_submit(self):
		append_daily_sales_audit_action_log(
			self,
			action="Submitted",
			old_status=getattr(self, "_status_before_submit", None) or "Draft",
			new_status=self.audit_status,
		)

	def before_cancel(self):
		self._status_before_cancel = self.audit_status
		self.audit_status = "Cancelled"

	def on_cancel(self):
		append_daily_sales_audit_action_log(
			self,
			action="Cancelled",
			old_status=getattr(self, "_status_before_cancel", None) or "Draft",
			new_status=self.audit_status,
		)

	def _validate_context_consistency(self):
		if not self.pos_opening_shift and not self.pos_closing_shift:
			return

		resolved = resolve_daily_sales_audit_context_from_selection(
			{
				"company": self.company,
				"branch": self.branch,
				"pos_profile": self.pos_profile,
				"cashier": self.cashier,
				"audit_date": str(self.audit_date) if self.audit_date else None,
				"pos_opening_shift": self.pos_opening_shift,
				"pos_closing_shift": self.pos_closing_shift,
			}
		)

		for fieldname, label in (
			("company", "Company"),
			("pos_profile", "POS Profile"),
			("cashier", "Cashier"),
		):
			current = getattr(self, fieldname, None)
			resolved_value = resolved.get(fieldname)
			if self.pos_opening_shift and current and resolved_value and current != resolved_value:
				frappe.throw(
					f"{label} does not match the selected POS Opening Shift. Expected {resolved_value}."
				)

		if self.pos_closing_shift and self.pos_opening_shift:
			resolved_opening = resolved.get("pos_opening_shift")
			if resolved_opening and resolved_opening != self.pos_opening_shift:
				frappe.throw(
					f"POS Opening Shift does not match the selected POS Closing Shift. Expected {resolved_opening}."
				)
