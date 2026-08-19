from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

import frappe
from frappe.utils import flt

from retailedge.branch_context import has_doctype, has_field
from retailedge.cash_custody import CASH_DEPOSIT_TYPE, CUSTODY_FIELD_DEFS, PAYMENT_ENTRY_DOCTYPE


def get_submitted_deposit_totals(opening_shifts: Iterable[str], *, company: str | None = None) -> dict[str, float]:
	"""Return submitted RetailEdge cashier deposits grouped by POS opening shift."""
	shifts = sorted({str(shift or "").strip() for shift in opening_shifts if str(shift or "").strip()})
	if not shifts or not has_doctype(PAYMENT_ENTRY_DOCTYPE):
		return {}
	for fieldname in CUSTODY_FIELD_DEFS:
		if not has_field(PAYMENT_ENTRY_DOCTYPE, fieldname):
			return {}

	filters: dict[str, Any] = {
		"docstatus": 1,
		"payment_type": "Internal Transfer",
		"retailedge_cash_custody_type": CASH_DEPOSIT_TYPE,
		"retailedge_pos_opening_shift": ["in", shifts],
	}
	if company:
		filters["company"] = company

	rows = frappe.get_all(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=["retailedge_pos_opening_shift", "paid_amount"],
		limit_page_length=0,
	)
	totals: dict[str, float] = defaultdict(float)
	for row in rows:
		shift = str(row.get("retailedge_pos_opening_shift") or "").strip()
		if shift:
			totals[shift] += flt(row.get("paid_amount"))
	return dict(totals)


def get_submitted_deposit_total(opening_shift: str | None, *, company: str | None = None) -> float:
	opening_shift = str(opening_shift or "").strip()
	if not opening_shift:
		return 0.0
	return flt(get_submitted_deposit_totals([opening_shift], company=company).get(opening_shift))


def apply_submitted_deposits_to_daily_sales_audit(doc) -> float:
	"""Recalculate saved audit cash expectations after submitted cashier bank deposits.

	The existing Daily Sales Audit engine remains authoritative for opening cash,
	cash sales, included expenses, closing cash, and tolerance. This adapter only
	deducts submitted RetailEdge cashier deposits from expected physical cash.
	"""
	opening_shift = str(getattr(doc, "pos_opening_shift", None) or "").strip()
	company = str(getattr(doc, "company", None) or "").strip()
	deposit_amount = get_submitted_deposit_total(opening_shift, company=company)

	expected = (
		flt(getattr(doc, "opening_cash_amount", 0))
		+ flt(getattr(doc, "cash_sales_amount", 0))
		- flt(getattr(doc, "cashier_expense_amount", 0))
		- deposit_amount
	)
	doc.expected_cash_amount = expected
	doc.cash_variance_amount = flt(getattr(doc, "actual_closing_cash_amount", 0)) - expected
	doc.net_variance_amount = flt(doc.cash_variance_amount)
	doc.shortage_amount = abs(flt(doc.cash_variance_amount)) if flt(doc.cash_variance_amount) < 0 else 0.0
	doc.overage_amount = flt(doc.cash_variance_amount) if flt(doc.cash_variance_amount) > 0 else 0.0

	tolerance = flt(getattr(doc, "variance_tolerance_used", 0))
	doc.variance_within_tolerance = 1 if abs(flt(doc.cash_variance_amount)) <= tolerance else 0
	return deposit_amount
