from __future__ import annotations

import json
from types import SimpleNamespace

import frappe
from frappe.utils import flt, getdate, now_datetime

from retailedge.branch_context import get_branch_query_filters, has_field, resolve_retailedge_branch_context
from retailedge.cashier_context import (
	_coerce_doc,
	_get_doc_value,
	get_shift_cash_snapshot,
	resolve_branch,
	resolve_cash_payment_account,
)
from retailedge.cashier_expense import user_has_any_role
from retailedge.cashier_expense_audit import get_cashier_expenses_for_daily_audit
from retailedge.utils.settings import get_retailedge_settings


DEFAULT_DAILY_SALES_AUDIT_REVIEWER_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
SYSTEM_MANAGER_ROLE = "System Manager"
FINAL_REVIEW_STATUSES = {"Approved", "Rejected", "Balanced", "Variance Found", "Cancelled"}
LINE_REVIEW_STATUSES = (
	"Pending Review",
	"Matched",
	"Variance Found",
	"Requires Clarification",
	"Excluded",
	"Verified for Audit",
)

BRANCH_FIELD_CANDIDATES = ["branch", "set_branch", "service_branch", "retail_branch", "default_branch"]
POS_PROFILE_FIELD_CANDIDATES = ["pos_profile"]
CASHIER_FIELD_CANDIDATES = ["cashier", "user", "owner"]
OPENING_SHIFT_LINK_CANDIDATES = ["pos_opening_shift", "opening_shift", "linked_pos_opening_shift"]
OPENING_SHIFT_DATE_CANDIDATES = ["period_start_date", "opening_date", "posting_date", "creation"]
CLOSING_SHIFT_DATE_CANDIDATES = ["period_end_date", "closing_date", "posting_date", "creation"]


def get_daily_sales_audit_context_options(filters=None):
	filters = _coerce_filters(filters)
	resolved = resolve_daily_sales_audit_context_from_selection(filters)
	effective = {**filters, **{key: value for key, value in resolved.items() if key in _context_keys() and value}}
	messages = list(resolved.get("messages") or [])
	for doctype in ("Branch", "POS Profile", "POS Opening Shift", "POS Closing Shift"):
		if not _has_doctype(doctype):
			messages.append(f"{doctype} is not available on this site, so related Daily Sales Audit filters are limited.")

	options = {
		"companies": _list_companies(effective),
		"branches": _list_branches(effective),
		"pos_profiles": _list_pos_profiles(effective),
		"cashiers": _list_cashiers(effective),
		# Shift links now query live submitted records by cashier/context instead of
		# preloading large name lists into client-side filters.
		"opening_shifts": [],
		"closing_shifts": [],
		"defaults": {key: resolved.get(key) for key in _context_keys()},
		"messages": messages,
	}

	if not options["defaults"].get("pos_profile") and len(options["pos_profiles"]) == 1:
		options["defaults"]["pos_profile"] = options["pos_profiles"][0]
	if not options["defaults"].get("cashier") and len(options["cashiers"]) == 1:
		options["defaults"]["cashier"] = options["cashiers"][0]
	if not options["defaults"].get("branch") and options["defaults"].get("pos_profile"):
		branch_value = _get_doctype_value(
			"POS Profile",
			options["defaults"]["pos_profile"],
			_find_first_field("POS Profile", BRANCH_FIELD_CANDIDATES),
		)
		if branch_value:
			options["defaults"]["branch"] = branch_value

	return options


def resolve_daily_sales_audit_context_from_selection(filters=None):
	filters = _coerce_filters(filters)
	branch_context = resolve_retailedge_branch_context(
		company=filters.get("company"),
		branch=filters.get("branch"),
		pos_profile=filters.get("pos_profile"),
		cashier=filters.get("cashier"),
		pos_opening_shift=filters.get("pos_opening_shift"),
		pos_closing_shift=filters.get("pos_closing_shift"),
		user=filters.get("cashier"),
	)
	result = {key: filters.get(key) for key in _context_keys()}
	result["source_map"] = dict(branch_context.get("source_map") or {})
	result["messages"] = list(branch_context.get("messages") or [])
	for fieldname in ("branch", "company", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"):
		if branch_context.get(fieldname) and not result.get(fieldname):
			result[fieldname] = branch_context.get(fieldname)

	closing_doc = _coerce_doc("POS Closing Shift", filters.get("pos_closing_shift"))
	if closing_doc:
		_apply_context_from_pos_closing_shift(result, closing_doc)

	opening_doc = _coerce_doc("POS Opening Shift", result.get("pos_opening_shift") or filters.get("pos_opening_shift"))
	if opening_doc:
		_apply_context_from_pos_opening_shift(result, opening_doc, overwrite=not closing_doc)

	profile_doc = _coerce_doc("POS Profile", result.get("pos_profile") or filters.get("pos_profile"))
	if profile_doc:
		_apply_context_from_pos_profile(result, profile_doc, overwrite=not (closing_doc or opening_doc))

	if not result.get("pos_profile"):
		candidate_profiles = _list_pos_profiles(
			{
				"company": result.get("company") or filters.get("company"),
				"branch": result.get("branch") or filters.get("branch"),
			}
		)
		if len(candidate_profiles) == 1:
			result["pos_profile"] = candidate_profiles[0]
			result["source_map"]["pos_profile"] = "Branch Profile Match"
			profile_doc = _coerce_doc("POS Profile", candidate_profiles[0])
			if profile_doc:
				_apply_context_from_pos_profile(result, profile_doc, overwrite=False)

	if filters.get("cashier") and not result.get("cashier"):
		result["cashier"] = filters.get("cashier")
		result["source_map"]["cashier"] = "Selected Cashier"

	if filters.get("branch") and not result.get("branch"):
		result["branch"] = filters.get("branch")
		result["source_map"]["branch"] = "Selected Branch"

	if filters.get("company") and not result.get("company"):
		result["company"] = filters.get("company")
		result["source_map"]["company"] = "Selected Company"

	if filters.get("audit_date") and not result.get("audit_date"):
		result["audit_date"] = filters.get("audit_date")
		result["source_map"]["audit_date"] = "Selected Audit Date"

	if not result.get("pos_opening_shift") and filters.get("cashier"):
		candidate_openings = _list_opening_shifts(
			{
				"company": result.get("company") or filters.get("company"),
				"branch": result.get("branch") or filters.get("branch"),
				"pos_profile": result.get("pos_profile") or filters.get("pos_profile"),
				"cashier": filters.get("cashier"),
				"audit_date": result.get("audit_date") or filters.get("audit_date"),
			}
		)
		if len(candidate_openings) == 1:
			result["pos_opening_shift"] = candidate_openings[0]
			result["source_map"]["pos_opening_shift"] = "Cashier Shift Match"
			opening_doc = _coerce_doc("POS Opening Shift", candidate_openings[0])
			if opening_doc:
				_apply_context_from_pos_opening_shift(result, opening_doc, overwrite=False)

	if result.get("pos_opening_shift") and not result.get("pos_closing_shift"):
		closing_candidates = _list_closing_shifts({"pos_opening_shift": result.get("pos_opening_shift")})
		if len(closing_candidates) == 1:
			result["pos_closing_shift"] = closing_candidates[0]
			result["source_map"]["pos_closing_shift"] = "Opening Shift Match"

	if not result.get("branch"):
		branch_resolution = resolve_branch(
			company=result.get("company"),
			pos_profile=result.get("pos_profile"),
			opening_shift=result.get("pos_opening_shift"),
			user=result.get("cashier"),
		)
		if branch_resolution.get("branch"):
			result["branch"] = branch_resolution.get("branch")
			result["source_map"]["branch"] = {
				"opening_shift": "POS Opening Shift",
				"pos_profile": "POS Profile",
				"coreedge": "CoreEdge Branch Context",
				"user_default": "User Default",
			}.get(branch_resolution.get("source"), "Branch Resolver")

	if not result.get("audit_date"):
		result["audit_date"] = filters.get("audit_date")

	return result


def get_daily_sales_audit_settings():
	settings = _safe_settings()
	reviewer_roles = get_daily_sales_audit_reviewer_roles()
	return {
		"enabled": bool(getattr(settings, "enable_daily_sales_audit", 0)),
		"require_pos_closing_shift": bool(
			getattr(settings, "require_pos_closing_shift_for_daily_audit", 0)
		),
		"include_cashier_expenses_preview": bool(
			getattr(settings, "include_cashier_expenses_in_daily_sales_audit_preview", 1)
		),
		"include_rejected_cashier_expenses_preview": bool(
			getattr(settings, "include_rejected_cashier_expenses_in_daily_sales_audit_preview", 1)
		),
		"variance_tolerance": flt(getattr(settings, "daily_sales_audit_variance_tolerance", 0)),
		"reviewer_roles": sorted(reviewer_roles),
		"allow_self_review": bool(getattr(settings, "allow_self_review_daily_sales_audit", 0)),
	}


def get_daily_sales_audit_reviewer_roles():
	settings = _safe_settings()
	roles = set(DEFAULT_DAILY_SALES_AUDIT_REVIEWER_ROLES)
	for row in getattr(settings, "daily_sales_audit_reviewer_roles", []) or []:
		role = getattr(row, "role", None) or (row.get("role") if isinstance(row, dict) else None)
		if role:
			roles.add(role)
	return roles


def user_is_daily_sales_audit_reviewer(user: str | None = None):
	return user_has_any_role(user=user, roles=get_daily_sales_audit_reviewer_roles())


def assert_daily_sales_audit_reviewer(user: str | None = None):
	user = user or frappe.session.user
	if not user_is_daily_sales_audit_reviewer(user=user):
		frappe.throw(
			"You do not have permission to manage RetailEdge Daily Sales Audit.",
			frappe.PermissionError,
		)


def get_daily_sales_audit_context(filters=None):
	filters = _coerce_filters(filters)
	resolved_filters = resolve_daily_sales_audit_context_from_selection(filters)
	if (
		(filters.get("pos_opening_shift") or filters.get("pos_closing_shift"))
		and resolved_filters.get("source_map", {}).get("branch") == "Explicit Branch"
	):
		shift_priority_filters = dict(filters)
		shift_priority_filters.pop("branch", None)
		shift_priority_resolved = resolve_daily_sales_audit_context_from_selection(shift_priority_filters)
		if shift_priority_resolved.get("branch"):
			resolved_filters["branch"] = shift_priority_resolved.get("branch")
			resolved_filters.setdefault("source_map", {})["branch"] = shift_priority_resolved.get("source_map", {}).get(
				"branch", "Shift Context"
			)
	for key in _context_keys():
		if resolved_filters.get(key):
			filters[key] = resolved_filters.get(key)
	branch_context = resolve_retailedge_branch_context(
		company=filters.get("company"),
		branch=filters.get("branch"),
		pos_profile=filters.get("pos_profile"),
		cashier=filters.get("cashier"),
		pos_opening_shift=filters.get("pos_opening_shift"),
		pos_closing_shift=filters.get("pos_closing_shift"),
		user=filters.get("cashier"),
	)
	for key in ("company", "branch", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"):
		if branch_context.get(key) and not filters.get(key):
			filters[key] = branch_context.get(key)
	settings = get_daily_sales_audit_settings()
	context = {
		"company": filters.get("company"),
		"branch": filters.get("branch"),
		"pos_profile": filters.get("pos_profile"),
		"cashier": filters.get("cashier"),
		"audit_date": filters.get("audit_date"),
		"pos_opening_shift": filters.get("pos_opening_shift"),
		"pos_closing_shift": filters.get("pos_closing_shift"),
		"opening_cash_amount": 0.0,
		"cash_sales_amount": 0.0,
		"cashier_expense_amount": 0.0,
		"expected_cash_amount": 0.0,
		"actual_closing_cash_amount": 0.0,
		"cash_variance_amount": 0.0,
		"total_sales_amount": 0.0,
		"total_cash_payment_amount": 0.0,
		"total_bank_transfer_amount": 0.0,
		"total_card_pos_amount": 0.0,
		"total_mobile_money_amount": 0.0,
		"total_other_payment_amount": 0.0,
		"invoice_count": 0,
		"paid_invoice_count": 0,
		"unpaid_invoice_count": 0,
		"partially_paid_invoice_count": 0,
		"exception_count": 0,
		"invoice_lines": [],
		"payment_lines": [],
		"cashier_expense_lines": [],
		"variance_tolerance": settings["variance_tolerance"],
	}

	shift_snapshot = get_shift_cash_snapshot(
		opening_shift=filters.get("pos_opening_shift"),
		company=filters.get("company"),
		pos_profile=filters.get("pos_profile"),
		user=filters.get("cashier"),
	)
	context["opening_cash_amount"] = flt(shift_snapshot.get("opening_cash"))
	context["cash_sales_amount"] = flt(shift_snapshot.get("cash_sales"))

	closing_cash_result = _get_actual_closing_cash_amount(
		pos_closing_shift=filters.get("pos_closing_shift"),
		pos_opening_shift=filters.get("pos_opening_shift"),
		company=filters.get("company"),
		pos_profile=filters.get("pos_profile"),
	)
	context["actual_closing_cash_amount"] = flt(closing_cash_result.get("amount"))
	if not context["pos_closing_shift"] and closing_cash_result.get("pos_closing_shift"):
		context["pos_closing_shift"] = closing_cash_result.get("pos_closing_shift")

	invoices, payment_lines, payment_summary = _get_invoice_and_payment_context(filters)
	context["invoice_lines"] = invoices
	context["payment_lines"] = payment_lines
	context["invoice_count"] = len(invoices)
	context["total_sales_amount"] = payment_summary["total_sales_amount"]
	context["total_cash_payment_amount"] = payment_summary["total_cash_payment_amount"]
	context["total_bank_transfer_amount"] = payment_summary["total_bank_transfer_amount"]
	context["total_card_pos_amount"] = payment_summary["total_card_pos_amount"]
	context["total_mobile_money_amount"] = payment_summary["total_mobile_money_amount"]
	context["total_other_payment_amount"] = payment_summary["total_other_payment_amount"]
	context["paid_invoice_count"] = payment_summary["paid_invoice_count"]
	context["unpaid_invoice_count"] = payment_summary["unpaid_invoice_count"]
	context["partially_paid_invoice_count"] = payment_summary["partially_paid_invoice_count"]

	expense_filters = {
		"company": filters.get("company"),
		"branch": filters.get("branch"),
		"pos_profile": filters.get("pos_profile"),
		"cashier": filters.get("cashier"),
		"linked_pos_opening_shift": filters.get("pos_opening_shift"),
		"linked_pos_closing_shift": filters.get("pos_closing_shift"),
	}
	# When a specific shift is selected, the linked shift is the strongest
	# expense scope and should not be narrowed away by an exact audit date.
	if not (filters.get("pos_opening_shift") or filters.get("pos_closing_shift")):
		expense_filters["from_date"] = filters.get("audit_date")
		expense_filters["to_date"] = filters.get("audit_date")
	if not settings["include_rejected_cashier_expenses_preview"]:
		expense_filters["include_rejected"] = 0
	expense_rows = get_cashier_expenses_for_daily_audit(filters=expense_filters)
	context["cashier_expense_lines"] = _filter_cashier_expense_lines(
		expense_rows,
		include_rejected=settings["include_rejected_cashier_expenses_preview"],
	)
	context["cashier_expense_amount"] = sum(
		flt(row.get("amount"))
		for row in context["cashier_expense_lines"]
		if cint_int(row.get("include_in_expected_cash"))
	)

	context["expected_cash_amount"] = (
		flt(context["opening_cash_amount"])
		+ flt(context["cash_sales_amount"])
		- flt(context["cashier_expense_amount"])
	)
	context["cash_variance_amount"] = flt(context["actual_closing_cash_amount"]) - flt(
		context["expected_cash_amount"]
	)
	context["exception_count"] = _count_exceptions(context)
	return context


def create_daily_sales_audit_draft(filters=None):
	settings = get_daily_sales_audit_settings()
	if not settings["enabled"]:
		frappe.throw("RetailEdge Daily Sales Audit is not enabled in RetailEdge Settings.")
	_assert_daily_sales_audit_reviewer()

	filters = _coerce_filters(filters)
	context = get_daily_sales_audit_context(filters)
	_assert_daily_sales_audit_context(context, settings)

	existing_name = _find_existing_daily_sales_audit_draft(context)
	if existing_name:
		return existing_name

	doc = frappe.new_doc("RetailEdge Daily Sales Audit")
	doc.naming_series = "RE-DSA-.YYYY.-.####"
	_apply_context_to_audit_doc(doc, context)
	doc.insert(ignore_permissions=True)
	append_daily_sales_audit_action_log(
		doc,
		action="Draft Created",
		old_status=None,
		new_status=doc.audit_status,
		details=_log_context_from_audit_doc(doc),
	)
	_save_audit_doc(doc)
	return doc.name


def refresh_daily_sales_audit_preview(audit_name):
	assert_daily_sales_audit_reviewer()
	doc = frappe.get_doc("RetailEdge Daily Sales Audit", audit_name)
	if doc.audit_status == "Cancelled":
		frappe.throw("Cancelled Daily Sales Audit documents cannot be refreshed.")

	context = get_daily_sales_audit_context(_filters_from_audit_doc(doc))
	previous_status = doc.audit_status
	_apply_context_to_audit_doc(doc, context)
	refresh_daily_sales_audit_review_summary(doc)
	append_daily_sales_audit_action_log(
		doc,
		action="Preview Refreshed",
		old_status=previous_status,
		new_status=doc.audit_status,
		details=_log_context_from_audit_doc(doc),
	)
	_save_audit_doc(doc)
	return doc.name


def append_daily_sales_audit_action_log(
	doc_or_name,
	action,
	old_status=None,
	new_status=None,
	remarks=None,
	details=None,
	previous_status=None,
	context=None,
):
	doc = doc_or_name
	if getattr(doc_or_name, "doctype", None) != "RetailEdge Daily Sales Audit":
		doc = frappe.get_doc("RetailEdge Daily Sales Audit", doc_or_name)

	if old_status is None:
		old_status = previous_status
	if details is None:
		details = context
	context_text = _serialise_context(context)
	details_text = _serialise_context(details)
	row = doc.append(
		"action_logs",
		{
			"action": action,
			"action_by": frappe.session.user,
			"action_on": now_datetime(),
			"old_status": old_status,
			"previous_status": old_status,
			"new_status": new_status,
			"remarks": remarks,
			"details_json": details_text,
			"context": context_text,
		},
	)
	return row


def calculate_daily_sales_audit_variance(doc):
	settings = get_daily_sales_audit_settings()
	included_expenses = 0.0
	has_expense_basis = False
	line_statuses = []
	for row in getattr(doc, "cashier_expense_lines", []) or []:
		included = _row_value(row, "included_in_audit")
		if included in (None, ""):
			included = _row_value(row, "include_in_expected_cash", 1)
		raw_amount = _row_value(row, "amount")
		amount_is_defined = raw_amount not in (None, "")
		amount = flt(raw_amount) if amount_is_defined else 0.0
		if cint_int(included) and amount_is_defined:
			included_expenses += amount
			has_expense_basis = True
		elif amount_is_defined and amount:
			has_expense_basis = True
		status = _row_value(row, "review_status") or _row_value(row, "audit_line_status")
		if status:
			line_statuses.append(status)

	for table_field in ("invoice_lines", "payment_lines"):
		for row in getattr(doc, table_field, []) or []:
			status = _row_value(row, "review_status") or _row_value(row, "audit_line_status")
			if status:
				line_statuses.append(status)

	doc.cashier_expense_amount = flt(included_expenses) if has_expense_basis else flt(getattr(doc, "cashier_expense_amount", 0))
	doc.expected_cash_amount = flt(doc.opening_cash_amount) + flt(doc.cash_sales_amount) - flt(doc.cashier_expense_amount)
	doc.cash_variance_amount = flt(doc.actual_closing_cash_amount) - flt(doc.expected_cash_amount)
	doc.net_variance_amount = flt(doc.cash_variance_amount)
	doc.shortage_amount = abs(flt(doc.cash_variance_amount)) if flt(doc.cash_variance_amount) < 0 else 0.0
	doc.overage_amount = flt(doc.cash_variance_amount) if flt(doc.cash_variance_amount) > 0 else 0.0
	doc.variance_tolerance_used = flt(settings.get("variance_tolerance"))
	doc.variance_within_tolerance = 1 if abs(flt(doc.cash_variance_amount)) <= flt(doc.variance_tolerance_used) else 0
	doc.clarification_required = 1 if "Requires Clarification" in line_statuses else cint_int(getattr(doc, "clarification_required", 0))

	if doc.clarification_required:
		doc.audit_result = "Requires Clarification"
		doc.variance_classification = "Clarification Required"
	elif "Variance Found" in line_statuses and ("Matched" in line_statuses or "Verified for Audit" in line_statuses):
		doc.audit_result = "Mixed Variance"
		doc.variance_classification = "Mixed Variance"
	elif flt(doc.cash_variance_amount) == 0:
		doc.audit_result = "Balanced"
		doc.variance_classification = "Balanced"
	elif flt(doc.cash_variance_amount) < 0:
		doc.audit_result = "Shortage"
		doc.variance_classification = "Within Tolerance Shortage" if cint_int(doc.variance_within_tolerance) else "Shortage"
	else:
		doc.audit_result = "Overage"
		doc.variance_classification = "Within Tolerance Overage" if cint_int(doc.variance_within_tolerance) else "Overage"
	return {
		"expected_cash_amount": flt(doc.expected_cash_amount),
		"actual_closing_cash_amount": flt(doc.actual_closing_cash_amount),
		"net_variance_amount": flt(doc.net_variance_amount),
		"shortage_amount": flt(doc.shortage_amount),
		"overage_amount": flt(doc.overage_amount),
		"variance_tolerance_used": flt(doc.variance_tolerance_used),
		"variance_within_tolerance": cint_int(doc.variance_within_tolerance),
		"audit_result": doc.audit_result,
	}


def refresh_daily_sales_audit_review_summary(doc):
	calculate_daily_sales_audit_variance(doc)
	statuses = []
	for table_field in ("invoice_lines", "payment_lines", "cashier_expense_lines"):
		for row in getattr(doc, table_field, []) or []:
			status = _row_value(row, "review_status") or _row_value(row, "audit_line_status") or "Pending Review"
			statuses.append(status)
	exception_count = 0
	if flt(doc.net_variance_amount) != 0:
		exception_count += 1
	exception_count += sum(1 for status in statuses if status in {"Variance Found", "Requires Clarification"})
	doc.exception_count = exception_count
	doc.review_required = 1 if statuses or flt(doc.net_variance_amount) != 0 else 0
	doc.variance_status = "Variance Found" if flt(doc.net_variance_amount) != 0 or "Variance Found" in statuses else "Balanced"
	if "Requires Clarification" in statuses or cint_int(doc.clarification_required):
		doc.audit_status = "Clarification Required" if doc.audit_status not in {"Approved", "Rejected", "Cancelled"} else doc.audit_status
	return {
		"exception_count": cint_int(doc.exception_count),
		"review_required": cint_int(doc.review_required),
		"variance_status": doc.variance_status,
		"audit_result": doc.audit_result,
	}


def submit_daily_sales_audit_for_review(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	if doc.audit_status not in {"Draft", "Reopened"}:
		frappe.throw("Only Draft or Reopened Daily Sales Audit documents can be submitted for review.")
	refresh_daily_sales_audit_review_summary(doc)
	old_status = doc.audit_status
	doc.audit_status = "Ready for Review"
	doc.submitted_for_review_by = frappe.session.user
	doc.submitted_for_review_on = now_datetime()
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Submitted for Review", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def start_daily_sales_audit_review(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	_assert_not_self_review(doc)
	if doc.audit_status != "Ready for Review":
		frappe.throw("Only Ready for Review Daily Sales Audit documents can be started for review.")
	old_status = doc.audit_status
	doc.audit_status = "In Review"
	doc.review_started_by = frappe.session.user
	doc.review_started_on = now_datetime()
	doc.locked_for_review = 1
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.reviewed_by = frappe.session.user
	doc.reviewed_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Review Started", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def mark_daily_sales_audit_balanced(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	if doc.audit_status not in {"In Review", "Variance Found", "Clarification Required"}:
		frappe.throw("Daily Sales Audit can only be marked balanced from In Review, Variance Found, or Clarification Required.")
	old_status = doc.audit_status
	refresh_daily_sales_audit_review_summary(doc)
	doc.audit_status = "Balanced"
	doc.audit_result = "Balanced"
	doc.review_required = 0
	doc.clarification_required = 0
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Marked Balanced", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def mark_daily_sales_audit_variance_found(audit_name, reason=None, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	if doc.audit_status not in {"In Review", "Ready for Review", "Balanced", "Clarification Required"}:
		frappe.throw("Daily Sales Audit can only be marked as variance found from a review state.")
	old_status = doc.audit_status
	refresh_daily_sales_audit_review_summary(doc)
	doc.audit_status = "Variance Found"
	doc.review_required = 1
	doc.variance_reason = reason or doc.variance_reason
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Variance Found", old_status=old_status, new_status=doc.audit_status, remarks=remarks, details={"reason": reason})
	_save_audit_doc(doc)
	return doc.name


def request_daily_sales_audit_clarification(audit_name, note=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	if doc.audit_status not in {"In Review", "Variance Found", "Ready for Review"}:
		frappe.throw("Clarification can only be requested from Ready for Review, In Review, or Variance Found.")
	old_status = doc.audit_status
	doc.audit_status = "Clarification Required"
	doc.clarification_required = 1
	doc.clarification_note = note
	doc.clarification_requested_by = frappe.session.user
	doc.clarification_requested_on = now_datetime()
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	append_daily_sales_audit_action_log(doc, "Clarification Requested", old_status=old_status, new_status=doc.audit_status, remarks=note)
	_save_audit_doc(doc)
	return doc.name


def resolve_daily_sales_audit_clarification(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	if doc.audit_status != "Clarification Required":
		frappe.throw("Only Clarification Required Daily Sales Audit documents can resolve clarification.")
	if not (user_is_daily_sales_audit_reviewer() or frappe.session.user == doc.owner):
		frappe.throw("You do not have permission to resolve this Daily Sales Audit clarification.", frappe.PermissionError)
	old_status = doc.audit_status
	doc.clarification_required = 0
	doc.clarification_resolved_by = frappe.session.user
	doc.clarification_resolved_on = now_datetime()
	doc.audit_status = "In Review"
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Clarification Resolved", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def approve_daily_sales_audit(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	_assert_not_self_review(doc)
	if doc.audit_status in {"Rejected", "Cancelled"}:
		frappe.throw("Rejected or Cancelled Daily Sales Audit documents cannot be approved.")
	if doc.audit_status not in {"Balanced", "Variance Found", "In Review"}:
		frappe.throw("Daily Sales Audit can only be approved from Balanced, Variance Found, or In Review.")
	old_status = doc.audit_status
	refresh_daily_sales_audit_review_summary(doc)
	doc.audit_status = "Approved"
	doc.approved_by = frappe.session.user
	doc.approved_on = now_datetime()
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	doc.locked_for_review = 1
	append_daily_sales_audit_action_log(doc, "Approved", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def reject_daily_sales_audit(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	if doc.audit_status not in {"Ready for Review", "In Review", "Variance Found", "Clarification Required", "Balanced"}:
		frappe.throw("Daily Sales Audit can only be rejected from an active review state.")
	old_status = doc.audit_status
	doc.audit_status = "Rejected"
	doc.rejected_by = frappe.session.user
	doc.rejected_on = now_datetime()
	doc.review_required = 1
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Rejected", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def reopen_daily_sales_audit(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	if doc.audit_status not in {"Approved", "Rejected", "Balanced", "Variance Found"}:
		frappe.throw("Only Approved, Rejected, Balanced, or Variance Found Daily Sales Audit documents can be reopened.")
	old_status = doc.audit_status
	doc.audit_status = "Reopened"
	doc.reopened_by = frappe.session.user
	doc.reopened_on = now_datetime()
	doc.locked_for_review = 0
	doc.review_required = 1
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Reopened", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def cancel_daily_sales_audit_review(audit_name, remarks=None):
	doc = _get_daily_sales_audit_doc(audit_name)
	assert_daily_sales_audit_reviewer()
	if doc.audit_status == "Cancelled":
		return doc.name
	old_status = doc.audit_status
	doc.audit_status = "Cancelled"
	doc.locked_for_review = 1
	doc.last_review_action_by = frappe.session.user
	doc.last_review_action_on = now_datetime()
	doc.review_remarks = remarks
	append_daily_sales_audit_action_log(doc, "Review Cancelled", old_status=old_status, new_status=doc.audit_status, remarks=remarks)
	_save_audit_doc(doc)
	return doc.name


def update_daily_sales_audit_invoice_line_status(audit_name, row_name, review_status, remarks=None):
	return _update_daily_sales_audit_line_status(audit_name, "invoice_lines", row_name, review_status, remarks)


def update_daily_sales_audit_payment_line_status(audit_name, row_name, review_status, remarks=None):
	return _update_daily_sales_audit_line_status(audit_name, "payment_lines", row_name, review_status, remarks)


def update_daily_sales_audit_expense_line_status(audit_name, row_name, review_status, remarks=None):
	return _update_daily_sales_audit_line_status(audit_name, "cashier_expense_lines", row_name, review_status, remarks)


def _assert_daily_sales_audit_reviewer():
	assert_daily_sales_audit_reviewer()


def _coerce_filters(filters):
	parsed = frappe.parse_json(filters) if filters else {}
	if isinstance(parsed, frappe._dict):
		parsed = dict(parsed)
	return parsed if isinstance(parsed, dict) else {}


def _assert_daily_sales_audit_context(context, settings):
	if not context.get("company"):
		frappe.throw("Company is required for Daily Sales Audit.")
	if not context.get("audit_date"):
		frappe.throw("Audit Date is required for Daily Sales Audit.")
	if settings["require_pos_closing_shift"] and not context.get("pos_closing_shift"):
		frappe.throw("POS Closing Shift is required for Daily Sales Audit by current settings.")


def _context_keys():
	return (
		"company",
		"branch",
		"pos_profile",
		"cashier",
		"audit_date",
		"pos_opening_shift",
		"pos_closing_shift",
	)


def _apply_context_from_pos_opening_shift(result, doc, overwrite=False):
	_set_context_value(result, "pos_opening_shift", getattr(doc, "name", None), "POS Opening Shift", force=True)
	_set_context_value(result, "company", _get_doc_value(doc, ["company"]), "POS Opening Shift", force=overwrite)
	_set_context_value(
		result,
		"pos_profile",
		_get_doc_value(doc, POS_PROFILE_FIELD_CANDIDATES),
		"POS Opening Shift",
		force=overwrite,
	)
	_set_context_value(
		result,
		"cashier",
		_get_doc_value(doc, CASHIER_FIELD_CANDIDATES),
		"POS Opening Shift",
		force=overwrite,
	)
	_set_context_value(
		result,
		"branch",
		_get_doc_value(doc, BRANCH_FIELD_CANDIDATES),
		"POS Opening Shift",
		force=overwrite,
	)
	date_value = _get_doc_value(doc, OPENING_SHIFT_DATE_CANDIDATES)
	if date_value:
		_set_context_value(result, "audit_date", str(getdate(date_value)), "POS Opening Shift", force=overwrite)


def _apply_context_from_pos_closing_shift(result, doc):
	_set_context_value(result, "pos_closing_shift", getattr(doc, "name", None), "POS Closing Shift", force=True)
	_set_context_value(result, "company", _get_doc_value(doc, ["company"]), "POS Closing Shift", force=True)
	_set_context_value(
		result,
		"pos_profile",
		_get_doc_value(doc, POS_PROFILE_FIELD_CANDIDATES),
		"POS Closing Shift",
		force=True,
	)
	_set_context_value(
		result,
		"cashier",
		_get_doc_value(doc, CASHIER_FIELD_CANDIDATES),
		"POS Closing Shift",
		force=True,
	)
	_set_context_value(
		result,
		"branch",
		_get_doc_value(doc, BRANCH_FIELD_CANDIDATES),
		"POS Closing Shift",
		force=True,
	)
	linked_opening = _get_doc_value(doc, OPENING_SHIFT_LINK_CANDIDATES)
	if linked_opening:
		_set_context_value(result, "pos_opening_shift", linked_opening, "POS Closing Shift", force=True)
	date_value = _get_doc_value(doc, CLOSING_SHIFT_DATE_CANDIDATES)
	if date_value:
		_set_context_value(result, "audit_date", str(getdate(date_value)), "POS Closing Shift", force=True)


def _apply_context_from_pos_profile(result, doc, overwrite=False):
	_set_context_value(result, "pos_profile", getattr(doc, "name", None), "POS Profile", force=False)
	_set_context_value(result, "company", _get_doc_value(doc, ["company"]), "POS Profile", force=overwrite)
	_set_context_value(
		result,
		"branch",
		_get_doc_value(doc, BRANCH_FIELD_CANDIDATES),
		"POS Profile",
		force=overwrite,
	)


def _set_context_value(result, fieldname, value, source, force=False):
	if value in (None, ""):
		return
	if force or not result.get(fieldname):
		result[fieldname] = value
		result.setdefault("source_map", {})[fieldname] = source


def _build_query_filters(doctype, filters):
	meta = _get_meta(doctype)
	if not meta:
		return None
	query_filters = {}
	branch_scope = get_branch_query_filters(
		doctype,
		user=filters.get("cashier") or getattr(getattr(frappe, "session", None), "user", "Administrator"),
		company=filters.get("company"),
		branch=filters.get("branch"),
	)
	query_filters.update(branch_scope.get("filters") or {})
	if meta.has_field("docstatus"):
		if doctype in {"POS Opening Shift", "POS Closing Shift"}:
			query_filters["docstatus"] = 1
		else:
			query_filters["docstatus"] = ["!=", 2]

	if filters.get("company") and meta.has_field("company"):
		query_filters["company"] = filters.get("company")
	if filters.get("pos_profile"):
		pos_profile_field = _find_existing_field(doctype, POS_PROFILE_FIELD_CANDIDATES)
		if pos_profile_field:
			query_filters[pos_profile_field] = filters.get("pos_profile")
	if filters.get("branch"):
		branch_field = _find_existing_field(doctype, BRANCH_FIELD_CANDIDATES)
		if branch_field and branch_field not in query_filters:
			query_filters[branch_field] = filters.get("branch")
	if filters.get("cashier"):
		cashier_field = _find_existing_field(doctype, CASHIER_FIELD_CANDIDATES)
		if cashier_field:
			query_filters[cashier_field] = filters.get("cashier")
	if filters.get("pos_opening_shift"):
		link_field = _find_existing_field(doctype, OPENING_SHIFT_LINK_CANDIDATES)
		if link_field:
			query_filters[link_field] = filters.get("pos_opening_shift")
	if filters.get("audit_date"):
		date_field = _find_date_field_for_doctype(doctype)
		if date_field:
			query_filters[date_field] = ["between", [filters.get("audit_date"), filters.get("audit_date")]]

	return query_filters


def _list_companies(filters):
	if not _has_doctype("Company"):
		return []
	if filters.get("company"):
		return [filters.get("company")]
	try:
		return [row.name for row in frappe.get_all("Company", fields=["name"], limit_page_length=0, order_by="name asc")]
	except Exception:
		return []


def _list_branches(filters):
	if not _has_doctype("Branch"):
		return []
	query_filters = {}
	branch_meta = _get_meta("Branch")
	if branch_meta and branch_meta.has_field("company") and filters.get("company"):
		query_filters["company"] = filters.get("company")
	try:
		return [row.name for row in frappe.get_all("Branch", filters=query_filters, fields=["name"], limit_page_length=0, order_by="name asc")]
	except Exception:
		return []


def _list_pos_profiles(filters):
	if not _has_doctype("POS Profile"):
		return []
	if filters.get("branch") and not _find_existing_field("POS Profile", BRANCH_FIELD_CANDIDATES):
		return _list_pos_profiles_from_shift_context(filters)
	query_filters = _build_query_filters("POS Profile", filters) or {}
	try:
		return [
			row.name
			for row in frappe.get_all(
				"POS Profile",
				filters=query_filters,
				fields=["name"],
				limit_page_length=0,
				order_by="name asc",
			)
		]
	except Exception:
		return []


def _list_pos_profiles_from_shift_context(filters):
	profiles = []
	seen = set()
	for doctype in ("POS Opening Shift", "POS Closing Shift"):
		if not _has_doctype(doctype):
			continue
		pos_profile_field = _find_existing_field(doctype, POS_PROFILE_FIELD_CANDIDATES)
		if not pos_profile_field:
			continue
		query_filters = _build_query_filters(doctype, {k: v for k, v in filters.items() if k != "pos_profile"})
		if query_filters is None:
			continue
		try:
			rows = frappe.get_all(
				doctype,
				filters=query_filters,
				fields=[pos_profile_field],
				limit_page_length=0,
				order_by="creation desc",
			)
		except Exception:
			continue
		for row in rows:
			value = row.get(pos_profile_field)
			if value and value not in seen:
				seen.add(value)
				profiles.append(value)
	return profiles


def _list_opening_shifts(filters):
	if not _has_doctype("POS Opening Shift"):
		return []
	query_filters = _build_query_filters("POS Opening Shift", filters)
	if query_filters is None:
		return []
	status_field = _find_existing_field("POS Opening Shift", ["status"])
	if status_field and not filters.get("pos_closing_shift"):
		query_filters.setdefault(status_field, ["not in", ["Draft", "Cancelled"]])
	try:
		return [
			row.name
			for row in frappe.get_all(
				"POS Opening Shift",
				filters=query_filters,
				fields=["name"],
				limit_page_length=0,
				order_by="creation desc",
			)
		]
	except Exception:
		return []


def _list_closing_shifts(filters):
	if not _has_doctype("POS Closing Shift"):
		return []
	query_filters = _build_query_filters("POS Closing Shift", filters)
	if query_filters is None:
		return []
	try:
		return [
			row.name
			for row in frappe.get_all(
				"POS Closing Shift",
				filters=query_filters,
				fields=["name"],
				limit_page_length=0,
				order_by="creation desc",
			)
		]
	except Exception:
		return []


def _list_cashiers(filters):
	profile_users = _list_pos_profile_users(filters.get("pos_profile"))
	if profile_users:
		return profile_users

	cashiers = []
	seen = set()
	for doctype in ("POS Opening Shift", "POS Closing Shift"):
		if not _has_doctype(doctype):
			continue
		query_filters = _build_query_filters(doctype, filters)
		if query_filters is None:
			continue
		cashier_field = _find_existing_field(doctype, CASHIER_FIELD_CANDIDATES)
		if not cashier_field:
			continue
		try:
			rows = frappe.get_all(
				doctype,
				filters=query_filters,
				fields=[cashier_field],
				limit_page_length=0,
				order_by="creation desc",
			)
		except Exception:
			continue
		for row in rows:
			value = row.get(cashier_field)
			if value and value not in seen:
				seen.add(value)
				cashiers.append(value)
	return cashiers


def _list_pos_profile_users(pos_profile):
	if not pos_profile or not _has_doctype("POS Profile User"):
		return []
	try:
		rows = frappe.get_all(
			"POS Profile User",
			filters={"parent": pos_profile},
			fields=["user"],
			limit_page_length=0,
			order_by="idx asc, creation asc",
		)
	except Exception:
		return []
	return [row.user for row in rows if row.get("user")]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_daily_sales_audit_cashiers(doctype, txt, searchfield, start, page_len, filters):
	filters = _coerce_filters(filters)
	users = _list_pos_profile_users(filters.get("pos_profile"))
	if users:
		return _search_named_values(users, txt, start, page_len)

	user_filters = {}
	user_meta = _get_meta("User")
	if user_meta and user_meta.has_field("enabled"):
		user_filters["enabled"] = 1
	if txt:
		user_filters["name"] = ["like", f"%{txt}%"]
	rows = frappe.get_all(
		"User",
		filters=user_filters,
		fields=["name"],
		limit_start=start,
		limit_page_length=page_len,
		order_by="name asc",
	)
	values = [row.name for row in rows if _matches_search(row.name, txt)]
	return [(value,) for value in values[:page_len]]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_daily_sales_audit_opening_shifts(doctype, txt, searchfield, start, page_len, filters):
	return _search_daily_sales_audit_shifts(
		shift_doctype="POS Opening Shift",
		txt=txt,
		start=start,
		page_len=page_len,
		filters=filters,
		exclude_statuses=("Draft", "Cancelled"),
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_daily_sales_audit_closing_shifts(doctype, txt, searchfield, start, page_len, filters):
	return _search_daily_sales_audit_shifts(
		shift_doctype="POS Closing Shift",
		txt=txt,
		start=start,
		page_len=page_len,
		filters=filters,
		exclude_statuses=("Draft", "Cancelled"),
	)


def _search_daily_sales_audit_shifts(shift_doctype, txt, start, page_len, filters, exclude_statuses=()):
	filters = _coerce_filters(filters)
	if not _has_doctype(shift_doctype):
		return []

	query_filters = _build_query_filters(shift_doctype, filters) or {}
	status_field = _find_existing_field(shift_doctype, ["status"])
	if status_field and exclude_statuses:
		query_filters[status_field] = ["not in", list(exclude_statuses)]
	if txt:
		query_filters["name"] = ["like", f"%{txt}%"]

	rows = frappe.get_all(
		shift_doctype,
		filters=query_filters,
		fields=["name"],
		limit_page_length=0,
		order_by="creation desc",
	)
	values = [row.name for row in rows if _matches_search(row.name, txt)]
	return [(value,) for value in values[start : start + page_len]]


def _search_named_values(values, txt, start, page_len):
	matched = [value for value in values if _matches_search(value, txt)]
	return [(value,) for value in matched[start : start + page_len]]


def _matches_search(value, txt):
	if not value:
		return False
	if not txt:
		return True
	return txt.lower() in str(value).lower()


def _find_existing_field(doctype, candidates):
	meta = _get_meta(doctype)
	if not meta:
		return None
	for fieldname in candidates:
		if fieldname == "owner":
			return "owner"
		if meta.has_field(fieldname):
			return fieldname
	return None


def _find_date_field_for_doctype(doctype):
	if doctype == "POS Opening Shift":
		return _find_existing_field(doctype, OPENING_SHIFT_DATE_CANDIDATES)
	if doctype == "POS Closing Shift":
		return _find_existing_field(doctype, CLOSING_SHIFT_DATE_CANDIDATES)
	return _find_existing_field(doctype, ["posting_date", "creation"])


def _get_meta(doctype):
	if not _has_doctype(doctype):
		return None
	try:
		return frappe.get_meta(doctype)
	except Exception:
		return None


def _get_doctype_value(doctype, name, fieldname):
	if not doctype or not name or not fieldname:
		return None
	try:
		return frappe.db.get_value(doctype, name, fieldname)
	except Exception:
		return None


def _find_existing_daily_sales_audit_draft(context):
	filters = {
		"docstatus": 0,
		"company": context.get("company"),
		"audit_date": context.get("audit_date"),
	}
	for fieldname in ("branch", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"):
		value = context.get(fieldname)
		if value:
			filters[fieldname] = value
	return frappe.db.get_value("RetailEdge Daily Sales Audit", filters, "name")


def _apply_context_to_audit_doc(doc, context):
	doc.company = context.get("company")
	doc.audit_date = context.get("audit_date")
	doc.branch = context.get("branch")
	doc.pos_profile = context.get("pos_profile")
	doc.cashier = context.get("cashier")
	doc.pos_opening_shift = context.get("pos_opening_shift")
	doc.pos_closing_shift = context.get("pos_closing_shift")

	doc.opening_cash_amount = flt(context.get("opening_cash_amount"))
	doc.cash_sales_amount = flt(context.get("cash_sales_amount"))
	doc.cashier_expense_amount = flt(context.get("cashier_expense_amount"))
	doc.expected_cash_amount = flt(context.get("expected_cash_amount"))
	doc.actual_closing_cash_amount = flt(context.get("actual_closing_cash_amount"))
	doc.cash_variance_amount = flt(context.get("cash_variance_amount"))

	doc.total_sales_amount = flt(context.get("total_sales_amount"))
	doc.total_cash_payment_amount = flt(context.get("total_cash_payment_amount"))
	doc.total_bank_transfer_amount = flt(context.get("total_bank_transfer_amount"))
	doc.total_card_pos_amount = flt(context.get("total_card_pos_amount"))
	doc.total_mobile_money_amount = flt(context.get("total_mobile_money_amount"))
	doc.total_other_payment_amount = flt(context.get("total_other_payment_amount"))

	doc.invoice_count = cint_int(context.get("invoice_count"))
	doc.paid_invoice_count = cint_int(context.get("paid_invoice_count"))
	doc.unpaid_invoice_count = cint_int(context.get("unpaid_invoice_count"))
	doc.partially_paid_invoice_count = cint_int(context.get("partially_paid_invoice_count"))
	doc.exception_count = cint_int(context.get("exception_count"))

	doc.review_required = 1
	if not doc.audit_status or doc.audit_status == "Cancelled":
		doc.audit_status = "Draft"
	doc.audit_result = _derive_audit_result(context)
	doc.variance_tolerance_used = flt(context.get("variance_tolerance"))

	doc.set("invoice_lines", [])
	for row in context.get("invoice_lines", []):
		doc.append("invoice_lines", row)
	doc.set("payment_lines", [])
	for row in context.get("payment_lines", []):
		doc.append("payment_lines", row)
	doc.set("cashier_expense_lines", [])
	for row in context.get("cashier_expense_lines", []):
		doc.append("cashier_expense_lines", row)
	refresh_daily_sales_audit_review_summary(doc)


def _derive_audit_result(context):
	variance = flt(context.get("cash_variance_amount"))
	if variance == 0:
		return "Balanced"
	if variance < 0:
		return "Shortage"
	if variance > 0:
		return "Overage"
	return "Not Checked"


def _filters_from_audit_doc(doc):
	return {
		"company": doc.company,
		"branch": doc.branch,
		"pos_profile": doc.pos_profile,
		"cashier": doc.cashier,
		"audit_date": str(doc.audit_date) if doc.audit_date else None,
		"pos_opening_shift": doc.pos_opening_shift,
		"pos_closing_shift": doc.pos_closing_shift,
	}


def _filter_cashier_expense_lines(rows, include_rejected=True):
	lines = []
	for row in rows:
		status = row.get("expense_status") or "Draft"
		if status == "Cancelled":
			continue
		if status == "Rejected" and not include_rejected:
			continue
		should_include = 1 if row.get("daily_audit_should_include", 1) else 0
		lines.append(
			{
				"cashier_expense": row.get("name"),
				"expense_date": row.get("expense_date"),
				"expense_category": row.get("expense_category"),
				"amount": flt(row.get("amount")),
				"expense_status": status,
				"daily_audit_inclusion_status": row.get("daily_audit_inclusion_status"),
				"classification": row.get("daily_audit_classification"),
				"include_in_expected_cash": should_include,
				"included_in_audit": should_include,
				"review_status": "Pending Review",
				"variance_impact": flt(row.get("amount")) if should_include else 0,
				"reviewer_note": None,
				"excluded_from_review": 0,
				"reviewed_by": None,
				"reviewed_on": None,
				"remarks": row.get("daily_audit_note") or row.get("daily_audit_exclusion_reason"),
			}
		)
	return lines


def _get_invoice_and_payment_context(filters):
	invoices = []
	payments = []
	summary = {
		"total_sales_amount": 0.0,
		"total_cash_payment_amount": 0.0,
		"total_bank_transfer_amount": 0.0,
		"total_card_pos_amount": 0.0,
		"total_mobile_money_amount": 0.0,
		"total_other_payment_amount": 0.0,
		"paid_invoice_count": 0,
		"unpaid_invoice_count": 0,
		"partially_paid_invoice_count": 0,
	}
	invoice_doctypes = _get_daily_sales_audit_invoice_doctypes()
	if not invoice_doctypes:
		return invoices, payments, summary
	cash_account = None
	if filters.get("company") or filters.get("pos_profile") or filters.get("pos_opening_shift"):
		try:
			cash_account = resolve_cash_payment_account(
				company=filters.get("company"),
				pos_profile=filters.get("pos_profile"),
				opening_shift=filters.get("pos_opening_shift"),
			).get("payment_account")
		except Exception:
			cash_account = None

	invoice_names_by_doctype = {}
	shift_seed_rows = _get_shift_seed_invoice_rows(filters)
	for doctype in invoice_doctypes:
		try:
			meta = frappe.get_meta(doctype)
		except Exception:
			meta = None
		invoice_rows = shift_seed_rows.get(doctype) or frappe.get_all(
			doctype,
			filters=_get_daily_sales_audit_invoice_filters(doctype, meta, filters),
			fields=_get_daily_sales_audit_invoice_fields(meta),
			limit_page_length=0,
			order_by="posting_date asc, creation asc",
		)
		invoice_names_by_doctype[doctype] = set()
		for row in invoice_rows:
			paid_amount = flt(row.get("paid_amount"))
			outstanding = flt(row.get("outstanding_amount"))
			grand_total = flt(row.get("grand_total"))
			if outstanding <= 0 and grand_total > 0:
				payment_status = "Paid"
				summary["paid_invoice_count"] += 1
			elif paid_amount > 0 and outstanding > 0:
				payment_status = "Partially Paid"
				summary["partially_paid_invoice_count"] += 1
			else:
				payment_status = "Unpaid"
				summary["unpaid_invoice_count"] += 1
			invoices.append(
				{
					"sales_invoice": row.get("name"),
					"posting_date": row.get("posting_date"),
					"customer": row.get("customer"),
					"grand_total": grand_total,
					"outstanding_amount": outstanding,
					"paid_amount": grand_total - outstanding if paid_amount == 0 else paid_amount,
					"payment_status": payment_status,
					"audit_line_status": "Pending Review",
					"review_status": "Pending Review",
					"variance_amount": outstanding,
					"variance_reason": None,
					"reviewer_note": None,
					"excluded_from_review": 0,
					"reviewed_by": None,
					"reviewed_on": None,
					"remarks": None if doctype == "Sales Invoice" else doctype,
				}
			)
			invoice_names_by_doctype[doctype].add(row.get("name"))
			summary["total_sales_amount"] += grand_total

			invoice_doc = frappe.get_doc(doctype, row.get("name"))
			for payment_row in getattr(invoice_doc, "payments", []) or []:
				payment = payment_row.as_dict() if hasattr(payment_row, "as_dict") else dict(payment_row)
				amount = flt(payment.get("base_amount") if payment.get("base_amount") is not None else payment.get("amount"))
				if amount <= 0:
					continue
				mode = payment.get("mode_of_payment")
				account = payment.get("account") or payment.get("default_account")
				category = _classify_payment(mode, account, cash_account)
				payments.append(
					{
						"source_doctype": doctype,
						"source_document": row.get("name"),
						"mode_of_payment": mode,
						"account": account,
						"amount": amount,
						"payment_category": category,
						"audit_line_status": "Pending Review",
						"review_status": "Pending Review",
						"expected_amount": amount,
						"actual_amount": amount,
						"variance_amount": 0,
						"variance_reason": None,
						"reviewer_note": None,
						"excluded_from_review": 0,
						"reviewed_by": None,
						"reviewed_on": None,
						"remarks": None,
					}
				)
				_add_payment_category_total(summary, category, amount)

	payments.extend(_get_daily_sales_audit_payment_entries(filters, invoice_names_by_doctype, cash_account, summary))

	return invoices, payments, summary


def _get_shift_seed_invoice_rows(filters):
	rows_by_doctype = {}
	closing_shift = filters.get("pos_closing_shift") or _find_matching_pos_closing_shift(filters.get("pos_opening_shift"))
	if not closing_shift or not _has_doctype("Sales Invoice Reference"):
		return rows_by_doctype
	seed_rows = frappe.get_all(
		"Sales Invoice Reference",
		filters={
			"parent": closing_shift,
			"parenttype": "POS Closing Shift",
			"parentfield": "pos_transactions",
		},
		fields=["sales_invoice", "posting_date", "customer", "grand_total"],
		limit_page_length=0,
		order_by="idx asc",
	)
	if not seed_rows:
		return rows_by_doctype
	names = [row.get("sales_invoice") for row in seed_rows if row.get("sales_invoice")]
	if not names:
		return rows_by_doctype
	invoice_docs = {
		row.get("name"): row
		for row in frappe.get_all(
			"Sales Invoice",
			filters={"name": ["in", names]},
			fields=["name", "posting_date", "customer", "grand_total", "outstanding_amount", "paid_amount", "is_pos", "pos_profile"],
			limit_page_length=0,
		)
	}
	sales_invoice_rows = []
	for seed_row in seed_rows:
		doc_row = invoice_docs.get(seed_row.get("sales_invoice")) or {}
		sales_invoice_rows.append(
			{
				"name": seed_row.get("sales_invoice"),
				"posting_date": doc_row.get("posting_date") or seed_row.get("posting_date"),
				"customer": doc_row.get("customer") or seed_row.get("customer"),
				"grand_total": doc_row.get("grand_total") if doc_row.get("grand_total") is not None else seed_row.get("grand_total"),
				"outstanding_amount": doc_row.get("outstanding_amount") or 0,
				"paid_amount": doc_row.get("paid_amount") or 0,
			}
		)
	if sales_invoice_rows:
		rows_by_doctype["Sales Invoice"] = sales_invoice_rows
	return rows_by_doctype


def _get_daily_sales_audit_invoice_doctypes():
	doctypes = []
	for doctype in ("POS Invoice", "Sales Invoice"):
		if _has_doctype(doctype):
			doctypes.append(doctype)
	return doctypes


def _get_daily_sales_audit_invoice_fields(meta):
	fields = ["name", "posting_date", "customer", "grand_total", "outstanding_amount"]
	if meta and meta.has_field("paid_amount"):
		fields.append("paid_amount")
	return fields


def _get_daily_sales_audit_invoice_filters(doctype, meta, filters):
	query_filters = {"docstatus": 1}
	if meta and meta.has_field("company") and filters.get("company"):
		query_filters["company"] = filters.get("company")
	if doctype == "Sales Invoice" and meta and meta.has_field("is_pos"):
		query_filters["is_pos"] = 1
	if meta and meta.has_field("pos_profile") and filters.get("pos_profile"):
		query_filters["pos_profile"] = filters.get("pos_profile")
	if filters.get("branch"):
		if has_field(doctype, "retailedge_branch"):
			query_filters["retailedge_branch"] = filters.get("branch")
		elif meta and meta.has_field("branch"):
			query_filters["branch"] = filters.get("branch")
	opening_shift_field = _find_first_field(doctype, ["posa_pos_opening_shift", "pos_opening_shift", "opening_shift"])
	if opening_shift_field and filters.get("pos_opening_shift"):
		query_filters[opening_shift_field] = filters.get("pos_opening_shift")
	if filters.get("audit_date") and meta and meta.has_field("posting_date"):
		query_filters["posting_date"] = filters.get("audit_date")
	return query_filters


def _get_daily_sales_audit_payment_entries(filters, invoice_names_by_doctype, cash_account, summary):
	if not _has_doctype("Payment Entry"):
		return []
	if not any(invoice_names_by_doctype.values()):
		return []
	try:
		meta = frappe.get_meta("Payment Entry")
	except Exception:
		meta = None
	query_filters = {"docstatus": 1}
	if meta and meta.has_field("company") and filters.get("company"):
		query_filters["company"] = filters.get("company")
	if filters.get("branch"):
		if has_field("Payment Entry", "retailedge_branch"):
			query_filters["retailedge_branch"] = filters.get("branch")
		elif meta and meta.has_field("branch"):
			query_filters["branch"] = filters.get("branch")
	if filters.get("audit_date") and meta and meta.has_field("posting_date"):
		query_filters["posting_date"] = filters.get("audit_date")
	payment_rows = frappe.get_all(
		"Payment Entry",
		filters=query_filters,
		fields=["name", "posting_date", "mode_of_payment", "paid_amount", "received_amount", "paid_from", "paid_to"],
		limit_page_length=0,
		order_by="posting_date asc, creation asc",
	)
	payments = []
	for row in payment_rows:
		payment_doc = frappe.get_doc("Payment Entry", row.get("name"))
		for reference_row in getattr(payment_doc, "references", []) or []:
			reference = reference_row.as_dict() if hasattr(reference_row, "as_dict") else dict(reference_row)
			reference_doctype = reference.get("reference_doctype")
			reference_name = reference.get("reference_name")
			if reference_doctype not in invoice_names_by_doctype:
				continue
			if reference_name not in invoice_names_by_doctype.get(reference_doctype, set()):
				continue
			amount = flt(reference.get("allocated_amount") or reference.get("total_amount"))
			if amount <= 0:
				amount = flt(row.get("paid_amount") or row.get("received_amount"))
			if amount <= 0:
				continue
			account = row.get("paid_to") or row.get("paid_from")
			category = _classify_payment(row.get("mode_of_payment"), account, cash_account)
			payments.append(
				{
					"source_doctype": "Payment Entry",
					"source_document": row.get("name"),
					"mode_of_payment": row.get("mode_of_payment"),
					"account": account,
					"amount": amount,
					"payment_category": category,
					"audit_line_status": "Pending Review",
					"review_status": "Pending Review",
					"expected_amount": amount,
					"actual_amount": amount,
					"variance_amount": 0,
					"variance_reason": None,
					"reviewer_note": None,
					"excluded_from_review": 0,
					"reviewed_by": None,
					"reviewed_on": None,
					"remarks": f"{reference_doctype} {reference_name}",
				}
			)
			_add_payment_category_total(summary, category, amount)
	return payments


def _get_actual_closing_cash_amount(pos_closing_shift=None, pos_opening_shift=None, company=None, pos_profile=None):
	result = {"amount": 0.0, "pos_closing_shift": pos_closing_shift}
	closing_shift_name = pos_closing_shift or _find_matching_pos_closing_shift(pos_opening_shift)
	if not closing_shift_name or not _has_doctype("POS Closing Shift"):
		return result
	result["pos_closing_shift"] = closing_shift_name
	closing_doc = frappe.get_doc("POS Closing Shift", closing_shift_name)

	for table_field in ("payment_reconciliation", "payment_reconciliation_details", "pos_payments"):
		if not hasattr(closing_doc, table_field):
			continue
		for row in getattr(closing_doc, table_field) or []:
			row_dict = row.as_dict() if hasattr(row, "as_dict") else dict(row)
			if not _is_cash_row(row_dict):
				continue
			for fieldname in ("closing_amount", "amount", "base_amount", "expected_amount"):
				if row_dict.get(fieldname) is not None:
					result["amount"] = flt(row_dict.get(fieldname))
					return result
	return result


def _find_matching_pos_closing_shift(pos_opening_shift):
	if not pos_opening_shift or not _has_doctype("POS Closing Shift"):
		return None
	for fieldname in ("pos_opening_shift", "opening_shift", "linked_pos_opening_shift"):
		try:
			if frappe.db.get_value("DocField", {"parent": "POS Closing Shift", "fieldname": fieldname}, "name"):
				name = frappe.db.get_value("POS Closing Shift", {fieldname: pos_opening_shift, "docstatus": ["!=", 2]}, "name")
				if name:
					return name
		except Exception:
			continue
	return None


def _count_exceptions(context):
	count = 0
	if flt(context.get("cash_variance_amount")) != 0:
		count += 1
	for row in context.get("invoice_lines", []):
		if row.get("payment_status") in {"Unpaid", "Partially Paid"}:
			count += 1
	for row in context.get("cashier_expense_lines", []):
		if row.get("daily_audit_inclusion_status") == "Needs Clarification":
			count += 1
	return count


def _get_daily_sales_audit_doc(audit_name):
	doc = frappe.get_doc("RetailEdge Daily Sales Audit", audit_name)
	if doc.audit_status == "Cancelled":
		frappe.throw("Cancelled Daily Sales Audit documents cannot be reviewed.")
	return doc


def _save_audit_doc(doc):
	if getattr(doc, "docstatus", 0) == 1:
		doc.flags.ignore_validate_update_after_submit = True
	doc.save(ignore_permissions=True)
	return doc


def _assert_not_self_review(doc):
	settings = get_daily_sales_audit_settings()
	if settings.get("allow_self_review"):
		return
	if SYSTEM_MANAGER_ROLE in frappe.get_roles(frappe.session.user):
		return
	reference_users = {
		getattr(doc, "owner", None),
		getattr(doc, "submitted_for_review_by", None),
		getattr(doc, "cashier", None),
	}
	if frappe.session.user in {user for user in reference_users if user}:
		frappe.throw("You cannot approve or start review on your own Daily Sales Audit.", frappe.PermissionError)


def _update_daily_sales_audit_line_status(audit_name, table_field, row_name, review_status, remarks=None):
	assert_daily_sales_audit_reviewer()
	if review_status not in LINE_REVIEW_STATUSES:
		frappe.throw(f"Invalid review status: {review_status}")
	doc = _get_daily_sales_audit_doc(audit_name)
	row = None
	for child in getattr(doc, table_field, []) or []:
		if child.name == row_name:
			row = child
			break
	if not row:
		frappe.throw("Audit review row was not found.")
	old_status = getattr(row, "review_status", None) or getattr(row, "audit_line_status", None) or "Pending Review"
	row.review_status = review_status
	if hasattr(row, "audit_line_status"):
		row.audit_line_status = review_status
	if hasattr(row, "reviewer_note"):
		row.reviewer_note = remarks
	if hasattr(row, "remarks") and remarks:
		row.remarks = remarks
	if hasattr(row, "excluded_from_review"):
		row.excluded_from_review = 1 if review_status == "Excluded" else 0
	if hasattr(row, "reviewed_by"):
		row.reviewed_by = frappe.session.user
	if hasattr(row, "reviewed_on"):
		row.reviewed_on = now_datetime()
	refresh_daily_sales_audit_review_summary(doc)
	append_daily_sales_audit_action_log(
		doc,
		action=f"{table_field} status updated",
		old_status=doc.audit_status,
		new_status=doc.audit_status,
		remarks=remarks,
		details={"row_name": row_name, "from": old_status, "to": review_status},
	)
	_save_audit_doc(doc)
	return doc.name


def _log_context_from_audit_doc(doc):
	return {
		"company": doc.company,
		"audit_date": doc.audit_date,
		"branch": doc.branch,
		"pos_profile": doc.pos_profile,
		"cashier": doc.cashier,
		"pos_opening_shift": doc.pos_opening_shift,
		"pos_closing_shift": doc.pos_closing_shift,
		"expected_cash_amount": doc.expected_cash_amount,
		"actual_closing_cash_amount": doc.actual_closing_cash_amount,
		"cash_variance_amount": doc.cash_variance_amount,
	}


def _classify_payment(mode_of_payment, account, cash_account):
	mode = (mode_of_payment or "").strip().lower()
	account_name = (account or "").strip().lower()
	if cash_account and account == cash_account:
		return "Cash"
	if "cash" in mode or "cash" in account_name:
		return "Cash"
	if "bank" in mode or "transfer" in mode or "bank" in account_name:
		return "Bank Transfer"
	if "card" in mode or "pos" in mode or "terminal" in mode:
		return "Card / POS"
	if "mobile" in mode or "wallet" in mode or "money" in mode:
		return "Mobile Money"
	return "Other"


def _add_payment_category_total(summary, category, amount):
	mapping = {
		"Cash": "total_cash_payment_amount",
		"Bank Transfer": "total_bank_transfer_amount",
		"Card / POS": "total_card_pos_amount",
		"Mobile Money": "total_mobile_money_amount",
		"Other": "total_other_payment_amount",
	}
	fieldname = mapping.get(category, "total_other_payment_amount")
	summary[fieldname] = flt(summary.get(fieldname)) + flt(amount)


def _serialise_context(context):
	if context is None:
		return None
	if isinstance(context, str):
		return context
	try:
		return json.dumps(context, default=str, sort_keys=True)
	except Exception:
		return str(context)


def _row_value(row, fieldname, default=None):
	if isinstance(row, dict):
		return row.get(fieldname, default)
	return getattr(row, fieldname, default)


def _safe_settings():
	try:
		return get_retailedge_settings()
	except Exception:
		return SimpleNamespace()


def _has_doctype(doctype):
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def _find_first_field(doctype, candidates):
	for fieldname in candidates:
		try:
			if frappe.db.get_value("DocField", {"parent": doctype, "fieldname": fieldname}, "name"):
				return fieldname
		except Exception:
			continue
	return None


def _is_cash_row(row):
	mode = (row.get("mode_of_payment") or row.get("payment_method") or "").lower()
	account = (row.get("account") or row.get("default_account") or "").lower()
	return "cash" in mode or "cash" in account


def cint_int(value):
	try:
		return int(value or 0)
	except Exception:
		return 0
