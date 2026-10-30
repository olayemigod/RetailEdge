from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, nowdate

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


def _today_invoices(*, user: str, company: str = "", branch: str = "") -> list[dict[str, Any]]:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return []

	filters: dict[str, Any] = {
		"docstatus": 1,
		"owner": user,
		"posting_date": nowdate(),
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

	return frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=list(dict.fromkeys(fields)),
		order_by="creation desc",
		limit_page_length=RECENT_ACTIVITY_LIMIT,
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


@frappe.whitelist()
def get_my_cashier_activity() -> dict[str, Any]:
	"""Return only the signed-in cashier's own operational activity for today.

	The provider deliberately does not grant Sales Invoice or Payment Entry read access.
	It returns a bounded projection of submitted invoices owned by the current session
	user and payment rows belonging to those invoices. Destination document permissions
	remain unchanged.
	"""
	user = _assert_cashier_self_service_access()
	operating_context = _safe_operating_context()
	company = str(operating_context.get("company") or "").strip()
	cashier_context = get_current_cashier_context(user=user, company=company or None)
	company = str(cashier_context.get("company") or company or "").strip()
	branch = str(cashier_context.get("branch") or operating_context.get("branch") or "").strip()

	rows = _today_invoices(user=user, company=company, branch=branch)
	summary, activity = _normalize_activity(rows)
	payments_total, payment_breakdown = _payment_breakdown(
		[str(row.get("name")) for row in rows if row.get("name")]
	)
	summary["payments_total"] = payments_total

	shift: dict[str, Any] = {
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
	if cashier_context.get("linked_pos_opening_shift"):
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

	return {
		"date": nowdate(),
		"user": user,
		"company": company,
		"branch": branch,
		"currency": next((item.get("currency") for item in activity if item.get("currency")), ""),
		"summary": summary,
		"shift": shift,
		"payment_breakdown": payment_breakdown,
		"recent_activity": activity,
		"empty": not bool(activity),
		"empty_message": "No sales or returns have been recorded by you today." if not activity else "",
	}
