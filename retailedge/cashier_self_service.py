from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from retailedge.cashier_context import get_current_cashier_context, get_shift_cash_snapshot
from retailedge.operating_context import get_operating_context
from retailedge.setup_roles import user_has_retailedge_role


RECENT_ACTIVITY_LIMIT = 50


def _assert_cashier_self_service_access() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in to view your work activity."), frappe.PermissionError)
	if not user_has_retailedge_role("RetailEdgeCashier", user=user):
		frappe.throw(_("This page is available to RetailEdge cashiers."), frappe.PermissionError)
	return user


def _has_field(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _field_if_present(doctype: str, fieldname: str, fields: list[str]) -> None:
	if _has_field(doctype, fieldname):
		fields.append(fieldname)


def _safe_operating_context() -> dict[str, Any]:
	try:
		return get_operating_context() or {}
	except Exception:
		return {}


def _resolve_work_date(work_date: str = "") -> str:
	"""Resolve a cashier-selected business day without permitting future activity."""
	today = getdate(nowdate())
	try:
		selected = getdate(work_date) if str(work_date or "").strip() else today
	except Exception:
		frappe.throw(_("Choose a valid work date."), frappe.ValidationError)
		return str(today)
	if selected > today:
		frappe.throw(_("Work date cannot be in the future."), frappe.ValidationError)
	return str(selected)


def _invoices_for_date(
	*,
	user: str,
	work_date: str,
	company: str = "",
	branch: str = "",
) -> list[dict[str, Any]]:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return []

	filters: dict[str, Any] = {
		"docstatus": 1,
		"owner": user,
		"posting_date": work_date,
	}
	if company and _has_field("Sales Invoice", "company"):
		filters["company"] = company
	branch_field = "retailedge_branch" if _has_field("Sales Invoice", "retailedge_branch") else ""
	if not branch_field and _has_field("Sales Invoice", "branch"):
		branch_field = "branch"
	if branch and branch_field:
		filters[branch_field] = branch

	fields = ["name", "posting_date", "creation", "owner", "docstatus"]
	for fieldname in (
		"posting_time",
		"customer",
		"customer_name",
		"grand_total",
		"rounded_total",
		"paid_amount",
		"outstanding_amount",
		"status",
		"is_return",
		"return_against",
		"currency",
		"pos_profile",
	):
		_field_if_present("Sales Invoice", fieldname, fields)
	if branch_field and branch_field not in fields:
		fields.append(branch_field)

	# A single cashier business day is deliberately loaded completely so the KPI
	# totals are authoritative. Only the presentation list is capped afterwards.
	return frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=list(dict.fromkeys(fields)),
		order_by="creation desc",
		limit_page_length=0,
	)


def _payment_breakdown(invoice_names: list[str]) -> tuple[float, list[dict[str, Any]]]:
	if not invoice_names or not frappe.db.exists("DocType", "Sales Invoice Payment"):
		return 0.0, []

	fields = ["parent", "mode_of_payment", "amount"]
	if _has_field("Sales Invoice Payment", "account"):
		fields.append("account")
	try:
		rows = frappe.get_all(
			"Sales Invoice Payment",
			filters={
				"parenttype": "Sales Invoice",
				"parent": ["in", invoice_names],
			},
			fields=fields,
			limit_page_length=0,
		)
	except Exception:
		return 0.0, []

	by_mode: dict[str, float] = defaultdict(float)
	total = 0.0
	for row in rows:
		amount = flt(row.get("amount"))
		mode = str(row.get("mode_of_payment") or "Other")
		by_mode[mode] += amount
		total += amount
	return total, [
		{"mode_of_payment": mode, "amount": amount}
		for mode, amount in sorted(by_mode.items(), key=lambda item: item[0].lower())
	]


def _normalize_activity(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
	sales_count = 0
	returns_count = 0
	gross_sales = 0.0
	returns_total = 0.0
	net_sales = 0.0
	activity: list[dict[str, Any]] = []

	for row in rows:
		grand_total = flt(row.get("grand_total"))
		if not grand_total and row.get("rounded_total") not in (None, ""):
			grand_total = flt(row.get("rounded_total"))
		is_return = bool(row.get("is_return")) or bool(row.get("return_against")) or grand_total < 0
		if is_return:
			returns_count += 1
			returns_total += abs(grand_total)
		else:
			sales_count += 1
			gross_sales += grand_total
		net_sales += grand_total
		activity.append(
			{
				"reference": row.get("name"),
				"type": "Return" if is_return else "Sale",
				"posting_date": row.get("posting_date"),
				"posting_time": row.get("posting_time"),
				"customer": row.get("customer_name") or row.get("customer") or "",
				"total": grand_total,
				"paid_amount": flt(row.get("paid_amount")),
				"outstanding_amount": flt(row.get("outstanding_amount")),
				"status": row.get("status") or "Submitted",
				"currency": row.get("currency") or "",
			}
		)

	return (
		{
			"transaction_count": len(rows),
			"sales_count": sales_count,
			"gross_sales": gross_sales,
			"returns_count": returns_count,
			"returns_total": returns_total,
			"net_sales": net_sales,
		},
		activity,
	)


def _current_shift_payload(*, cashier_context: dict[str, Any], company: str, user: str) -> dict[str, Any]:
	shift: dict[str, Any] = {
		"available": True,
		"open": False,
		"opening_shift": cashier_context.get("linked_pos_opening_shift"),
		"status": cashier_context.get("opening_shift_status"),
		"pos_profile": cashier_context.get("pos_profile"),
		"opening_cash": 0.0,
		"cash_sales": 0.0,
		"prior_expenses": 0.0,
		"available_cash": 0.0,
		"message": cashier_context.get("message"),
	}
	if not cashier_context.get("linked_pos_opening_shift"):
		return shift

	snapshot = get_shift_cash_snapshot(
		opening_shift=cashier_context.get("linked_pos_opening_shift"),
		company=company or None,
		pos_profile=cashier_context.get("pos_profile"),
		user=user,
	)
	shift.update(
		{
			"open": True,
			"opening_cash": flt(snapshot.get("opening_cash")),
			"cash_sales": flt(snapshot.get("cash_sales")),
			"prior_expenses": flt(snapshot.get("prior_expenses")),
			"available_cash": flt(snapshot.get("available_before")),
			"message": snapshot.get("message") or shift.get("message"),
		}
	)
	return shift


@frappe.whitelist()
def get_my_cashier_activity(work_date: str = "") -> dict[str, Any]:
	"""Return the signed-in cashier's own operational activity for one selected day.

	The provider deliberately does not grant Sales Invoice or Payment Entry read access.
	It returns a bounded presentation of submitted invoices owned by the current session
	user while calculating the selected day's totals from the complete matching set.
	Current-shift cash position is intentionally shown only for today; a historical date
	must never be labelled with the user's present open-shift values.
	"""
	user = _assert_cashier_self_service_access()
	selected_date = _resolve_work_date(work_date)
	today = str(getdate(nowdate()))
	is_today = selected_date == today

	operating_context = _safe_operating_context()
	company = str(operating_context.get("company") or "").strip()
	cashier_context = get_current_cashier_context(user=user, company=company or None)
	company = str(cashier_context.get("company") or company or "").strip()
	branch = str(cashier_context.get("branch") or operating_context.get("branch") or "").strip()

	rows = _invoices_for_date(
		user=user,
		work_date=selected_date,
		company=company,
		branch=branch,
	)
	summary, all_activity = _normalize_activity(rows)
	payments_total, payment_breakdown = _payment_breakdown(
		[str(row.get("name")) for row in rows if row.get("name")]
	)
	summary["payments_total"] = payments_total

	if is_today:
		shift = _current_shift_payload(cashier_context=cashier_context, company=company, user=user)
	else:
		shift = {
			"available": False,
			"open": False,
			"opening_shift": "",
			"status": "",
			"pos_profile": "",
			"opening_cash": 0.0,
			"cash_sales": 0.0,
			"prior_expenses": 0.0,
			"available_cash": 0.0,
			"message": _("Shift position is available for today only."),
		}

	recent_activity = all_activity[:RECENT_ACTIVITY_LIMIT]
	return {
		"date": selected_date,
		"today": today,
		"is_today": is_today,
		"user": user,
		"company": company,
		"branch": branch,
		"currency": next((item.get("currency") for item in all_activity if item.get("currency")), ""),
		"summary": summary,
		"shift": shift,
		"payment_breakdown": payment_breakdown,
		"recent_activity": recent_activity,
		"activity_total": len(all_activity),
		"activity_limit": RECENT_ACTIVITY_LIMIT,
		"activity_truncated": len(all_activity) > RECENT_ACTIVITY_LIMIT,
		"empty": not bool(all_activity),
		"empty_message": _("No sales or returns were recorded by you on this day.") if not all_activity else "",
	}
