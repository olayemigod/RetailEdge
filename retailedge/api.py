import frappe

from retailedge.branch_context import (
	backfill_retailedge_branch_context as _backfill_retailedge_branch_context,
	get_branch_query_filters as _get_branch_query_filters,
	get_user_allowed_branches as _get_branch_context_allowed_branches,
	resolve_retailedge_branch_context as _resolve_retailedge_branch_context,
	resolve_retailedge_operational_defaults as _resolve_retailedge_operational_defaults,
)
from retailedge.branch_profile import (
	get_branch_profile as _get_branch_profile,
	get_branch_profile_defaults as _get_branch_profile_defaults,
	get_default_branch_for_user as _get_default_branch_for_user,
	get_user_branch_profiles as _get_user_branch_profiles,
)
from retailedge.branch_defaults_application import (
	assert_can_preview_branch_defaults as _assert_can_preview_branch_defaults,
	preview_branch_defaults_for_doc as _preview_branch_defaults_for_doc,
)
from retailedge.transaction_branch_attribution import (
	get_branch_attribution_target_doctypes as _get_branch_attribution_target_doctypes,
	preview_transaction_branch_backfill as _preview_transaction_branch_backfill,
	refresh_transaction_branch_attribution as _refresh_transaction_branch_attribution,
	resolve_transaction_branch as _resolve_transaction_branch,
	run_transaction_branch_backfill as _run_transaction_branch_backfill,
)
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
	approve_daily_sales_audit as _approve_daily_sales_audit,
	cancel_daily_sales_audit_review as _cancel_daily_sales_audit_review,
	create_daily_sales_audit_draft as _create_daily_sales_audit_draft,
	get_daily_sales_audit_context as _get_daily_sales_audit_context,
	get_daily_sales_audit_context_options as _get_daily_sales_audit_context_options,
	mark_daily_sales_audit_balanced as _mark_daily_sales_audit_balanced,
	mark_daily_sales_audit_variance_found as _mark_daily_sales_audit_variance_found,
	refresh_daily_sales_audit_preview as _refresh_daily_sales_audit_preview,
	reject_daily_sales_audit as _reject_daily_sales_audit,
	reopen_daily_sales_audit as _reopen_daily_sales_audit,
	request_daily_sales_audit_clarification as _request_daily_sales_audit_clarification,
	resolve_daily_sales_audit_context_from_selection as _resolve_daily_sales_audit_context_from_selection,
	resolve_daily_sales_audit_clarification as _resolve_daily_sales_audit_clarification,
	start_daily_sales_audit_review as _start_daily_sales_audit_review,
	submit_daily_sales_audit_for_review as _submit_daily_sales_audit_for_review,
	update_daily_sales_audit_expense_line_status as _update_daily_sales_audit_expense_line_status,
	update_daily_sales_audit_invoice_line_status as _update_daily_sales_audit_invoice_line_status,
	update_daily_sales_audit_payment_line_status as _update_daily_sales_audit_payment_line_status,
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
from retailedge.integrations.coreedge import get_coreedge_status as _get_coreedge_status
from retailedge.integrations.payments import (
	create_payment_request_for_sales_invoice as _create_payment_request_for_sales_invoice,
)
from retailedge.posting_date_control import get_posting_date_context as _get_posting_date_context


TRANSACTION_BRANCH_ATTRIBUTION_MANAGER_ROLES = (
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
)


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
def get_user_allowed_branches(user=None, company=None):
	return _get_branch_context_allowed_branches(user=user, company=company)


@frappe.whitelist()
def resolve_retailedge_branch_context(**kwargs):
	return _resolve_retailedge_branch_context(**kwargs)


@frappe.whitelist()
def get_branch_query_filters(doctype, user=None, company=None, branch=None, strict=False):
	return _get_branch_query_filters(
		doctype=doctype,
		user=user,
		company=company,
		branch=branch,
		strict=bool(int(strict)) if isinstance(strict, str) else bool(strict),
	)


@frappe.whitelist()
def backfill_retailedge_branch_context(doctype=None, dry_run=True, limit=500):
	return _backfill_retailedge_branch_context(
		doctype=doctype,
		dry_run=bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run),
		limit=int(limit or 500),
	)


@frappe.whitelist()
def get_branch_profile(company=None, branch=None, user=None, pos_profile=None, warehouse=None, active_only=True):
	profile = _get_branch_profile(
		company=company,
		branch=branch,
		user=user,
		pos_profile=pos_profile,
		warehouse=warehouse,
		active_only=bool(int(active_only)) if isinstance(active_only, str) else bool(active_only),
	)
	return profile.as_dict() if hasattr(profile, "as_dict") else profile


@frappe.whitelist()
def get_branch_profile_defaults(company=None, branch=None, user=None, pos_profile=None, warehouse=None):
	return _get_branch_profile_defaults(
		company=company,
		branch=branch,
		user=user,
		pos_profile=pos_profile,
		warehouse=warehouse,
	)


@frappe.whitelist()
def get_user_branch_profiles(user=None, company=None):
	return _get_user_branch_profiles(user=user, company=company)


@frappe.whitelist()
def get_default_branch_for_user(user=None, company=None):
	return _get_default_branch_for_user(user=user, company=company)


@frappe.whitelist()
def resolve_retailedge_operational_defaults(company=None, branch=None, user=None, pos_profile=None, warehouse=None):
	return _resolve_retailedge_operational_defaults(
		company=company,
		branch=branch,
		user=user,
		pos_profile=pos_profile,
		warehouse=warehouse,
	)


@frappe.whitelist()
def get_branch_attribution_target_doctypes():
	return _get_branch_attribution_target_doctypes()


@frappe.whitelist()
def resolve_transaction_branch(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission("read"):
		frappe.throw("You do not have permission to read this document.", frappe.PermissionError)
	return _resolve_transaction_branch(doc)


@frappe.whitelist()
def refresh_transaction_branch_attribution(doctype, name, overwrite=False):
	_assert_transaction_branch_attribution_manager()
	return _refresh_transaction_branch_attribution(
		doctype,
		name,
		overwrite=bool(int(overwrite)) if isinstance(overwrite, str) else bool(overwrite),
	)


@frappe.whitelist()
def preview_transaction_branch_backfill(doctype=None, filters=None, limit=500):
	_assert_transaction_branch_attribution_manager()
	return _preview_transaction_branch_backfill(doctype=doctype, filters=filters, limit=int(limit or 500))


@frappe.whitelist()
def run_transaction_branch_backfill(doctype=None, filters=None, limit=500, overwrite=False, dry_run=True):
	_assert_transaction_branch_attribution_manager()
	dry_run_flag = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)
	overwrite_flag = bool(int(overwrite)) if isinstance(overwrite, str) else bool(overwrite)
	return _run_transaction_branch_backfill(
		doctype=doctype,
		filters=filters,
		limit=int(limit or 500),
		overwrite=overwrite_flag,
		dry_run=dry_run_flag,
	)


@frappe.whitelist()
def preview_branch_defaults_for_doc(doctype, name=None, values=None):
	_assert_can_preview_branch_defaults()
	return _preview_branch_defaults_for_doc(doctype=doctype, name=name, values=values)


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
def submit_daily_sales_audit_for_review(audit_name, remarks=None):
	return _submit_daily_sales_audit_for_review(audit_name, remarks=remarks)


@frappe.whitelist()
def start_daily_sales_audit_review(audit_name, remarks=None):
	return _start_daily_sales_audit_review(audit_name, remarks=remarks)


@frappe.whitelist()
def mark_daily_sales_audit_balanced(audit_name, remarks=None):
	return _mark_daily_sales_audit_balanced(audit_name, remarks=remarks)


@frappe.whitelist()
def mark_daily_sales_audit_variance_found(audit_name, reason=None, remarks=None):
	return _mark_daily_sales_audit_variance_found(audit_name, reason=reason, remarks=remarks)


@frappe.whitelist()
def request_daily_sales_audit_clarification(audit_name, note=None):
	return _request_daily_sales_audit_clarification(audit_name, note=note)


@frappe.whitelist()
def resolve_daily_sales_audit_clarification(audit_name, remarks=None):
	return _resolve_daily_sales_audit_clarification(audit_name, remarks=remarks)


@frappe.whitelist()
def approve_daily_sales_audit(audit_name, remarks=None):
	return _approve_daily_sales_audit(audit_name, remarks=remarks)


@frappe.whitelist()
def reject_daily_sales_audit(audit_name, remarks=None):
	return _reject_daily_sales_audit(audit_name, remarks=remarks)


@frappe.whitelist()
def reopen_daily_sales_audit(audit_name, remarks=None):
	return _reopen_daily_sales_audit(audit_name, remarks=remarks)


@frappe.whitelist()
def cancel_daily_sales_audit_review(audit_name, remarks=None):
	return _cancel_daily_sales_audit_review(audit_name, remarks=remarks)


@frappe.whitelist()
def update_daily_sales_audit_invoice_line_status(audit_name, row_name, review_status, remarks=None):
	return _update_daily_sales_audit_invoice_line_status(
		audit_name, row_name, review_status, remarks=remarks
	)


@frappe.whitelist()
def update_daily_sales_audit_payment_line_status(audit_name, row_name, review_status, remarks=None):
	return _update_daily_sales_audit_payment_line_status(
		audit_name, row_name, review_status, remarks=remarks
	)


@frappe.whitelist()
def update_daily_sales_audit_expense_line_status(audit_name, row_name, review_status, remarks=None):
	return _update_daily_sales_audit_expense_line_status(
		audit_name, row_name, review_status, remarks=remarks
	)


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


def _assert_transaction_branch_attribution_manager():
	user_roles = set(frappe.get_roles(frappe.session.user))
	if user_roles.intersection(TRANSACTION_BRANCH_ATTRIBUTION_MANAGER_ROLES):
		return
	frappe.throw(
		"You do not have permission to manage RetailEdge transaction branch attribution.",
		frappe.PermissionError,
	)
