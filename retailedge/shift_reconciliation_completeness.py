from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.cash_deposit_audit import get_submitted_deposit_totals
from retailedge.cashier_context import get_shift_cash_snapshot, resolve_branch
from retailedge.cashier_expense_audit import get_cashier_expenses_for_daily_audit
from retailedge.cash_shift_verification_read_scope import resolve_cash_shift_verification_read_scope
from retailedge.daily_sales_audit import (
	BRANCH_FIELD_CANDIDATES,
	CASHIER_FIELD_CANDIDATES,
	NON_CANCELLED_AUDIT_STATUSES,
	OPENING_SHIFT_LINK_CANDIDATES,
	POS_PROFILE_FIELD_CANDIDATES,
	_build_query_filters,
	_filter_cashier_expense_lines,
	_find_date_field_for_doctype,
	_find_existing_field,
	_get_actual_closing_cash_amount,
	get_daily_sales_audit_settings,
)
from retailedge.retailedge.report.retailedge_cash_shift_verification.retailedge_cash_shift_verification import (
	get_cash_status,
)


MAX_COMPLETENESS_SHIFTS = 1000
AUDIT_REQUIRED_STATUS = "Audit Required"


def augment_shift_reconciliation_rows(
	rows: list[dict[str, Any]],
	filters: dict[str, Any] | frappe._dict | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
	"""Add submitted closing shifts that have no active Daily Sales Audit.

	Cash Shift Verification is intentionally audit-backed. Shift Reconciliation must not
	silently omit a submitted POS Closing Shift merely because its Daily Sales Audit was
	never created. This helper performs a permission/Branch-scoped completeness scan and
	adds read-only `Audit Required` rows using the same cash components as Daily Sales
	Audit. It does not create or mutate audit/accounting documents.
	"""
	filters = frappe._dict(filters or {})
	if not filters.get("company") or not filters.get("from_date") or not filters.get("to_date"):
		return list(rows or []), {
			"closing_shift_count": 0,
			"missing_audit_total": 0,
			"missing_audit_visible": 0,
		}

	# This is the same access gate used by Cash Shift Verification. Calling it here
	# prevents the direct closing-shift completeness scan from becoming a permission
	# bypass around the audit-backed report.
	resolve_cash_shift_verification_read_scope(_business_scope_filters(filters))
	closing_shifts = _get_scoped_closing_shifts(filters)
	if len(closing_shifts) > MAX_COMPLETENESS_SHIFTS:
		frappe.throw(
			_("More than {0} closed shifts match these filters. Narrow the date range or business scope before reconciling shifts.").format(
				MAX_COMPLETENESS_SHIFTS
			)
		)

	if not closing_shifts:
		return list(rows or []), {
			"closing_shift_count": 0,
			"missing_audit_total": 0,
			"missing_audit_visible": 0,
		}

	coverage = _get_active_audit_coverage(closing_shifts, filters)
	missing = [
		shift
		for shift in closing_shifts
		if shift.get("name") not in coverage["closing_shifts"]
		and shift.get("opening_shift") not in coverage["opening_shifts"]
	]
	deposit_totals = get_submitted_deposit_totals(
		[shift.get("opening_shift") for shift in missing if shift.get("opening_shift")],
		company=filters.get("company"),
	)

	missing_rows: list[dict[str, Any]] = []
	for shift in missing:
		row = _build_missing_audit_row(shift, deposit_totals=deposit_totals)
		if filters.get("cash_status") and row.get("cash_status") != filters.get("cash_status"):
			continue
		if filters.get("review_status") and filters.get("review_status") != AUDIT_REQUIRED_STATUS:
			continue
		missing_rows.append(row)

	combined = [*list(rows or []), *missing_rows]
	combined.sort(
		key=lambda row: (
			str(row.get("shift_date") or ""),
			str(row.get("closing_shift") or ""),
		),
		reverse=True,
	)
	return combined, {
		"closing_shift_count": len(closing_shifts),
		"missing_audit_total": len(missing),
		"missing_audit_visible": len(missing_rows),
	}


def _business_scope_filters(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	return {
		key: filters.get(key)
		for key in ("company", "branch", "pos_profile", "cashier")
		if filters.get(key)
	}


def _get_scoped_closing_shifts(filters: frappe._dict) -> list[dict[str, Any]]:
	selection = _business_scope_filters(filters)
	query_filters = _build_query_filters("POS Closing Shift", selection)
	if query_filters is None:
		return []

	date_field = _find_date_field_for_doctype("POS Closing Shift")
	opening_field = _find_existing_field("POS Closing Shift", OPENING_SHIFT_LINK_CANDIDATES)
	company_field = _find_existing_field("POS Closing Shift", ["company"])
	branch_field = _find_existing_field("POS Closing Shift", BRANCH_FIELD_CANDIDATES)
	pos_profile_field = _find_existing_field("POS Closing Shift", POS_PROFILE_FIELD_CANDIDATES)
	cashier_field = _find_existing_field("POS Closing Shift", CASHIER_FIELD_CANDIDATES)
	if not date_field:
		return []

	from_date = str(filters.get("from_date") or "").strip()
	to_date = str(filters.get("to_date") or "").strip()
	if from_date and to_date:
		if getdate(from_date) > getdate(to_date):
			frappe.throw(_("From Date cannot be after To Date."))
		query_filters[date_field] = ["between", [from_date, to_date]]
	elif from_date:
		query_filters[date_field] = [">=", from_date]
	elif to_date:
		query_filters[date_field] = ["<=", to_date]

	fields = ["name", date_field]
	for fieldname in (opening_field, company_field, branch_field, pos_profile_field, cashier_field):
		if fieldname and fieldname not in fields:
			fields.append(fieldname)
	rows = frappe.get_all(
		"POS Closing Shift",
		filters=query_filters,
		fields=fields,
		order_by=f"{date_field} desc, creation desc",
		limit_page_length=MAX_COMPLETENESS_SHIFTS + 1,
	)

	opening_context = _get_opening_shift_context(
		[row.get(opening_field) for row in rows if opening_field and row.get(opening_field)]
	)
	result = []
	for row in rows:
		opening_shift = row.get(opening_field) if opening_field else None
		opening = opening_context.get(opening_shift) or {}
		company = row.get(company_field) if company_field else None
		company = company or opening.get("company") or filters.get("company")
		pos_profile = row.get(pos_profile_field) if pos_profile_field else None
		pos_profile = pos_profile or opening.get("pos_profile")
		cashier = row.get(cashier_field) if cashier_field else None
		cashier = cashier or opening.get("cashier")
		branch = row.get(branch_field) if branch_field else None
		branch = branch or opening.get("branch")
		if not branch:
			branch = (
				resolve_branch(
					company=company,
					pos_profile=pos_profile,
					opening_shift=opening_shift,
					user=cashier,
				).get("branch")
				or ""
			)

		# `_build_query_filters` applies the authoritative Branch scope where the
		# current schema exposes a Branch/POS Profile field. These final checks also
		# protect older schemas where context had to be resolved through Opening Shift.
		if filters.get("branch") and branch != filters.get("branch"):
			continue
		if filters.get("pos_profile") and pos_profile != filters.get("pos_profile"):
			continue
		if filters.get("cashier") and cashier != filters.get("cashier"):
			continue

		result.append(
			{
				"name": row.get("name"),
				"shift_date": str(getdate(row.get(date_field))) if row.get(date_field) else "",
				"company": company,
				"branch": branch,
				"pos_profile": pos_profile,
				"cashier": cashier,
				"opening_shift": opening_shift,
			}
		)
	return result


def _get_opening_shift_context(opening_shift_names: list[str]) -> dict[str, dict[str, Any]]:
	names = list(dict.fromkeys(name for name in opening_shift_names if name))
	if not names or not frappe.db.exists("DocType", "POS Opening Shift"):
		return {}
	company_field = _find_existing_field("POS Opening Shift", ["company"])
	branch_field = _find_existing_field("POS Opening Shift", BRANCH_FIELD_CANDIDATES)
	pos_profile_field = _find_existing_field("POS Opening Shift", POS_PROFILE_FIELD_CANDIDATES)
	cashier_field = _find_existing_field("POS Opening Shift", CASHIER_FIELD_CANDIDATES)
	fields = ["name"]
	for fieldname in (company_field, branch_field, pos_profile_field, cashier_field):
		if fieldname and fieldname not in fields:
			fields.append(fieldname)
	rows = frappe.get_all(
		"POS Opening Shift",
		filters={"name": ["in", names]},
		fields=fields,
		limit_page_length=0,
	)
	return {
		row.get("name"): {
			"company": row.get(company_field) if company_field else None,
			"branch": row.get(branch_field) if branch_field else None,
			"pos_profile": row.get(pos_profile_field) if pos_profile_field else None,
			"cashier": row.get(cashier_field) if cashier_field else None,
		}
		for row in rows
	}


def _get_active_audit_coverage(
	closing_shifts: list[dict[str, Any]],
	filters: frappe._dict,
) -> dict[str, set[str]]:
	closing_names = [shift.get("name") for shift in closing_shifts if shift.get("name")]
	opening_names = [shift.get("opening_shift") for shift in closing_shifts if shift.get("opening_shift")]
	base_filters = resolve_cash_shift_verification_read_scope(_business_scope_filters(filters))
	active_statuses = list(NON_CANCELLED_AUDIT_STATUSES)
	covered_closing: set[str] = set()
	covered_opening: set[str] = set()

	if closing_names:
		query_filters = {
			**base_filters,
			"pos_closing_shift": ["in", closing_names],
			"audit_status": ["in", active_statuses],
			"docstatus": ["!=", 2],
		}
		for row in frappe.get_list(
			"RetailEdge Daily Sales Audit",
			filters=query_filters,
			fields=["pos_closing_shift", "pos_opening_shift"],
			limit_page_length=0,
		):
			if row.get("pos_closing_shift"):
				covered_closing.add(row.get("pos_closing_shift"))
			if row.get("pos_opening_shift"):
				covered_opening.add(row.get("pos_opening_shift"))

	if opening_names:
		query_filters = {
			**base_filters,
			"pos_opening_shift": ["in", opening_names],
			"audit_status": ["in", active_statuses],
			"docstatus": ["!=", 2],
		}
		for row in frappe.get_list(
			"RetailEdge Daily Sales Audit",
			filters=query_filters,
			fields=["pos_closing_shift", "pos_opening_shift"],
			limit_page_length=0,
		):
			if row.get("pos_closing_shift"):
				covered_closing.add(row.get("pos_closing_shift"))
			if row.get("pos_opening_shift"):
				covered_opening.add(row.get("pos_opening_shift"))

	return {"closing_shifts": covered_closing, "opening_shifts": covered_opening}


def _build_missing_audit_row(
	shift: dict[str, Any],
	*,
	deposit_totals: dict[str, float],
) -> dict[str, Any]:
	opening_shift = shift.get("opening_shift")
	company = shift.get("company")
	branch = shift.get("branch")
	pos_profile = shift.get("pos_profile")
	cashier = shift.get("cashier")
	closing_shift = shift.get("name")

	snapshot = get_shift_cash_snapshot(
		opening_shift=opening_shift,
		company=company,
		pos_profile=pos_profile,
		user=cashier,
	)
	opening_cash = flt(snapshot.get("opening_cash"))
	cash_sales = flt(snapshot.get("cash_sales"))

	expense_filters = {
		"company": company,
		"branch": branch,
		"pos_profile": pos_profile,
		"cashier": cashier,
		"linked_pos_opening_shift": opening_shift,
		"linked_pos_closing_shift": closing_shift,
	}
	expense_rows = get_cashier_expenses_for_daily_audit(
		filters={key: value for key, value in expense_filters.items() if value}
	)
	audit_settings = get_daily_sales_audit_settings()
	expense_lines = _filter_cashier_expense_lines(
		expense_rows,
		include_rejected=audit_settings["include_rejected_cashier_expenses_preview"],
	)
	till_expenses = sum(
		flt(row.get("amount"))
		for row in expense_lines
		if row.get("include_in_expected_cash")
	)
	cash_deposits = flt(deposit_totals.get(opening_shift))
	actual_closing = flt(
		_get_actual_closing_cash_amount(
			pos_closing_shift=closing_shift,
			pos_opening_shift=opening_shift,
			company=company,
			pos_profile=pos_profile,
		).get("amount")
	)
	expected_cash = opening_cash + cash_sales - till_expenses - cash_deposits
	cash_variance = actual_closing - expected_cash
	row = {
		"row_id": f"audit-required::{closing_shift}",
		"company": company,
		"branch": branch,
		"pos_profile": pos_profile,
		"cashier": cashier,
		"opening_shift": opening_shift,
		"closing_shift": closing_shift,
		"shift_date": shift.get("shift_date"),
		"opening_cash": opening_cash,
		"cash_sales": cash_sales,
		"included_cashier_expenses": till_expenses,
		"cash_deposits": cash_deposits,
		"expected_cash": expected_cash,
		"actual_closing_cash": actual_closing,
		"cash_variance": cash_variance,
		"daily_sales_audit": None,
		"review_status": AUDIT_REQUIRED_STATUS,
		"audit_required": 1,
		"eligible_cash_invoices": 0,
		"synced_cash_invoices": 0,
	}
	row["cash_status"] = get_cash_status(row)
	return row
