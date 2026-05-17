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


def get_daily_sales_audit_context(filters=None):
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

	if settings["include_cashier_expenses_preview"]:
		expense_filters = {
			"company": filters.get("company"),
			"branch": filters.get("branch"),
			"pos_profile": filters.get("pos_profile"),
			"cashier": filters.get("cashier"),
			"linked_pos_opening_shift": filters.get("pos_opening_shift"),
			"linked_pos_closing_shift": filters.get("pos_closing_shift"),
			"from_date": filters.get("audit_date"),
			"to_date": filters.get("audit_date"),
		}
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
		previous_status=None,
		new_status=doc.audit_status,
		context=_log_context_from_audit_doc(doc),
	)
	doc.save(ignore_permissions=True)
	return doc.name


def refresh_daily_sales_audit_preview(audit_name):
	_assert_daily_sales_audit_reviewer()
	doc = frappe.get_doc("RetailEdge Daily Sales Audit", audit_name)
	if doc.docstatus != 0:
		frappe.throw("Only draft Daily Sales Audit documents can be refreshed.")

	context = get_daily_sales_audit_context(_filters_from_audit_doc(doc))
	previous_status = doc.audit_status
	_apply_context_to_audit_doc(doc, context)
	append_daily_sales_audit_action_log(
		doc,
		action="Preview Refreshed",
		previous_status=previous_status,
		new_status=doc.audit_status,
		context=_log_context_from_audit_doc(doc),
	)
	doc.save(ignore_permissions=True)
	return doc.name


def append_daily_sales_audit_action_log(
	doc_or_name,
	action,
	previous_status=None,
	new_status=None,
	remarks=None,
	context=None,
):
	doc = doc_or_name
	if getattr(doc_or_name, "doctype", None) != "RetailEdge Daily Sales Audit":
		doc = frappe.get_doc("RetailEdge Daily Sales Audit", doc_or_name)

	context_text = _serialise_context(context)
	row = doc.append(
		"action_logs",
		{
			"action": action,
			"action_by": frappe.session.user,
			"action_on": now_datetime(),
			"previous_status": previous_status,
			"new_status": new_status,
			"remarks": remarks,
			"context": context_text,
		},
	)
	return row


def _assert_daily_sales_audit_reviewer():
	if not user_is_daily_sales_audit_reviewer():
		frappe.throw(
			"You do not have permission to manage RetailEdge Daily Sales Audit.",
			frappe.PermissionError,
		)


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

	doc.set("invoice_lines", [])
	for row in context.get("invoice_lines", []):
		doc.append("invoice_lines", row)
	doc.set("payment_lines", [])
	for row in context.get("payment_lines", []):
		doc.append("payment_lines", row)
	doc.set("cashier_expense_lines", [])
	for row in context.get("cashier_expense_lines", []):
		doc.append("cashier_expense_lines", row)


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
	if not _has_doctype("Sales Invoice"):
		return invoices, payments, summary

	try:
		meta = frappe.get_meta("Sales Invoice")
	except Exception:
		meta = None

	query_filters = {"docstatus": 1}
	if meta and meta.has_field("company") and filters.get("company"):
		query_filters["company"] = filters.get("company")
	if meta and meta.has_field("is_pos"):
		query_filters["is_pos"] = 1
	if meta and meta.has_field("pos_profile") and filters.get("pos_profile"):
		query_filters["pos_profile"] = filters.get("pos_profile")
	if filters.get("branch"):
		if has_field("Sales Invoice", "retailedge_branch"):
			query_filters["retailedge_branch"] = filters.get("branch")
		elif meta and meta.has_field("branch"):
			query_filters["branch"] = filters.get("branch")
	opening_shift_field = _find_first_field("Sales Invoice", ["posa_pos_opening_shift", "pos_opening_shift", "opening_shift"])
	if opening_shift_field and filters.get("pos_opening_shift"):
		query_filters[opening_shift_field] = filters.get("pos_opening_shift")
	if filters.get("audit_date"):
		query_filters["posting_date"] = filters.get("audit_date")

	fields = ["name", "posting_date", "customer", "grand_total", "outstanding_amount"]
	if meta and meta.has_field("paid_amount"):
		fields.append("paid_amount")
	invoice_rows = frappe.get_all(
		"Sales Invoice",
		filters=query_filters,
		fields=fields,
		limit_page_length=0,
		order_by="posting_date asc, creation asc",
	)
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
				"remarks": None,
			}
		)
		summary["total_sales_amount"] += grand_total

		invoice_doc = frappe.get_doc("Sales Invoice", row.get("name"))
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
					"source_doctype": "Sales Invoice",
					"source_document": row.get("name"),
					"mode_of_payment": mode,
					"account": account,
					"amount": amount,
					"payment_category": category,
					"audit_line_status": "Pending Review",
					"remarks": None,
				}
			)
			_add_payment_category_total(summary, category, amount)

	return invoices, payments, summary


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
