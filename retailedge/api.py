import frappe

from retailedge.cashier_expense import (
	approve_cashier_expense as _approve_cashier_expense,
	get_cashier_expenses_for_variance as _get_cashier_expenses_for_variance,
	get_cashier_expense_totals_for_variance as _get_cashier_expense_totals_for_variance,
	get_cashier_expense_summary as _get_cashier_expense_summary,
	get_cashier_expense_totals as _get_cashier_expense_totals,
	reject_cashier_expense as _reject_cashier_expense,
	reopen_cashier_expense as _reopen_cashier_expense,
	submit_cashier_expense as _submit_cashier_expense,
)
from retailedge.cashier_expense_audit import (
	get_cashier_expense_review_summary as _get_cashier_expense_review_summary,
	get_cashier_expense_daily_audit_totals as _get_cashier_expense_daily_audit_totals,
	get_cashier_expenses_for_daily_audit as _get_cashier_expenses_for_daily_audit,
	mark_cashier_expense_excluded_from_daily_audit as _mark_cashier_expense_excluded_from_daily_audit,
	mark_cashier_expense_included_for_daily_audit as _mark_cashier_expense_included_for_daily_audit,
	mark_cashier_expense_needs_clarification as _mark_cashier_expense_needs_clarification,
)
from retailedge.cashier_expense_dashboard import (
	assert_can_access_cashier_expense_dashboard as _assert_can_access_cashier_expense_dashboard,
	get_cashier_expense_dashboard_summary as _get_cashier_expense_dashboard_summary,
)
from retailedge.cashier_expense_posting import (
	assert_can_refresh_posting_readiness as _assert_can_refresh_posting_readiness,
	get_cashier_expense_posting_preview as _get_cashier_expense_posting_preview,
	refresh_cashier_expense_posting_readiness as _refresh_cashier_expense_posting_readiness,
	refresh_pending_cashier_expense_posting_readiness as _refresh_pending_cashier_expense_posting_readiness,
)
from retailedge.daily_sales_audit import (
	create_daily_sales_audit_draft as _create_daily_sales_audit_draft,
	get_daily_sales_audit_context as _get_daily_sales_audit_context,
	get_daily_sales_audit_context_options as _get_daily_sales_audit_context_options,
	refresh_daily_sales_audit_preview as _refresh_daily_sales_audit_preview,
	resolve_daily_sales_audit_context_from_selection as _resolve_daily_sales_audit_context_from_selection,
	user_is_daily_sales_audit_reviewer as _user_is_daily_sales_audit_reviewer,
)
from retailedge.cashier_context import (
	get_cashier_expense_entry_context as _get_cashier_expense_entry_context,
	get_current_cashier_context as _get_current_cashier_context,
	get_shift_cash_sales as _get_shift_cash_sales,
	get_shift_cash_snapshot as _get_shift_cash_snapshot,
)
from retailedge.cost_fields import COST_FIELDNAMES, COST_FIELD_LABEL_KEYWORDS
from retailedge.cost_visibility import get_cost_price_visibility_context as _get_cost_price_visibility_context
from retailedge.cost_visibility import should_hide_cost_price as _should_hide_cost_price
from retailedge.integrations.branch_context import get_active_branch as _get_active_branch
from retailedge.integrations.branch_context import get_user_allowed_branches as _get_user_allowed_branches
from retailedge.integrations.coreedge import get_coreedge_status as _get_coreedge_status
from retailedge.integrations.payments import (
	create_payment_request_for_sales_invoice as _create_payment_request_for_sales_invoice,
)
from retailedge.posting_date_control import get_posting_date_context as _get_posting_date_context


@frappe.whitelist()
def get_cost_price_visibility_context():
	return _get_cost_price_visibility_context()


@frappe.whitelist()
def get_coreedge_status():
	return _get_coreedge_status()


@frappe.whitelist()
def create_payment_request_for_sales_invoice(sales_invoice, method=None):
	return _create_payment_request_for_sales_invoice(sales_invoice=sales_invoice, method=method)


@frappe.whitelist()
def get_active_branch():
	return _get_active_branch()


@frappe.whitelist()
def get_user_allowed_branches():
	return _get_user_allowed_branches()


@frappe.whitelist()
def get_posting_date_context():
	return _get_posting_date_context()


@frappe.whitelist()
def get_current_cashier_context(company=None):
	return _get_current_cashier_context(company=company)


@frappe.whitelist()
def get_cashier_expense_entry_context(company=None):
	return _get_cashier_expense_entry_context(company=company)


@frappe.whitelist()
def get_shift_cash_snapshot(opening_shift=None, company=None, pos_profile=None):
	return _get_shift_cash_snapshot(
		opening_shift=opening_shift,
		company=company,
		pos_profile=pos_profile,
	)


@frappe.whitelist()
def get_shift_cash_sales(opening_shift=None, company=None, pos_profile=None):
	return _get_shift_cash_sales(
		opening_shift=opening_shift,
		company=company,
		pos_profile=pos_profile,
	)


@frappe.whitelist()
def submit_cashier_expense(expense_name):
	return _submit_cashier_expense(expense_name)


@frappe.whitelist()
def approve_cashier_expense(expense_name, remarks=None):
	return _approve_cashier_expense(expense_name, remarks=remarks)


@frappe.whitelist()
def reject_cashier_expense(expense_name, remarks=None):
	return _reject_cashier_expense(expense_name, remarks=remarks)


@frappe.whitelist()
def reopen_cashier_expense(expense_name, remarks=None):
	return _reopen_cashier_expense(expense_name, remarks=remarks)


@frappe.whitelist()
def get_cashier_expense_summary(filters=None):
	return _get_cashier_expense_summary(filters=filters)


@frappe.whitelist()
def get_cashier_expense_totals(filters=None):
	return _get_cashier_expense_totals(filters=filters)


@frappe.whitelist()
def get_cashier_expenses_for_variance(filters=None):
	return _get_cashier_expenses_for_variance(filters=filters)


@frappe.whitelist()
def get_cashier_expense_totals_for_variance(filters=None):
	return _get_cashier_expense_totals_for_variance(filters=filters)


@frappe.whitelist()
def get_cashier_expenses_for_daily_audit(filters=None):
	return _get_cashier_expenses_for_daily_audit(filters=filters)


@frappe.whitelist()
def get_cashier_expense_daily_audit_totals(filters=None):
	return _get_cashier_expense_daily_audit_totals(filters=filters)


@frappe.whitelist()
def get_cashier_expense_review_summary(filters=None):
	return _get_cashier_expense_review_summary(filters=filters)


@frappe.whitelist()
def get_cashier_expense_dashboard_summary(filters=None):
	_assert_can_access_cashier_expense_dashboard()
	return _get_cashier_expense_dashboard_summary(filters=filters)


@frappe.whitelist()
def get_daily_sales_audit_context(filters=None):
	_assert_can_access_cashier_expense_dashboard()
	return _get_daily_sales_audit_context(filters=filters)


@frappe.whitelist()
def get_daily_sales_audit_context_options(filters=None):
	_assert_can_access_cashier_expense_dashboard()
	return _get_daily_sales_audit_context_options(filters=filters)


@frappe.whitelist()
def resolve_daily_sales_audit_context_from_selection(filters=None):
	_assert_can_access_cashier_expense_dashboard()
	return _resolve_daily_sales_audit_context_from_selection(filters=filters)


@frappe.whitelist()
def create_daily_sales_audit_draft(filters=None):
	if not _user_is_daily_sales_audit_reviewer():
		frappe.throw("You do not have permission to create RetailEdge Daily Sales Audit.", frappe.PermissionError)
	return _create_daily_sales_audit_draft(filters=filters)


@frappe.whitelist()
def refresh_daily_sales_audit_preview(audit_name):
	if not _user_is_daily_sales_audit_reviewer():
		frappe.throw("You do not have permission to refresh RetailEdge Daily Sales Audit.", frappe.PermissionError)
	return _refresh_daily_sales_audit_preview(audit_name)


@frappe.whitelist()
def mark_cashier_expense_included_for_daily_audit(expense_name, note=None):
	return _mark_cashier_expense_included_for_daily_audit(expense_name, note=note)


@frappe.whitelist()
def mark_cashier_expense_excluded_from_daily_audit(expense_name, reason=None):
	return _mark_cashier_expense_excluded_from_daily_audit(expense_name, reason=reason)


@frappe.whitelist()
def mark_cashier_expense_needs_clarification(expense_name, note=None):
	return _mark_cashier_expense_needs_clarification(expense_name, note=note)


@frappe.whitelist()
def get_cashier_expense_posting_preview(expense_name):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	if not doc.has_permission("read"):
		frappe.throw("You do not have permission to view this cashier expense posting preview.", frappe.PermissionError)
	return _get_cashier_expense_posting_preview(expense_name)


@frappe.whitelist()
def refresh_cashier_expense_posting_readiness(expense_name):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	if not doc.has_permission("read"):
		frappe.throw("You do not have permission to refresh this cashier expense posting readiness.", frappe.PermissionError)
	_assert_can_refresh_posting_readiness()
	return _refresh_cashier_expense_posting_readiness(expense_name)


@frappe.whitelist()
def refresh_pending_cashier_expense_posting_readiness(filters=None):
	_assert_can_refresh_posting_readiness()
	return _refresh_pending_cashier_expense_posting_readiness(filters=filters)


@frappe.whitelist()
def get_cost_visibility_rules():
	if not _should_hide_cost_price():
		return {
			"hide_cost_price": 0,
			"fieldnames": [],
			"label_keywords": [],
		}

	return {
		"hide_cost_price": 1,
		"fieldnames": sorted(COST_FIELDNAMES),
		"label_keywords": COST_FIELD_LABEL_KEYWORDS[:],
	}
