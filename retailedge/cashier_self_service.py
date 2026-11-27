from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from retailedge.cash_custody import get_cash_custody_snapshot
from retailedge.cashier_context import get_current_cashier_context
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
		"company",
		"debit_to",
		"conversion_rate",
		"party_account_currency",
		"change_amount",
		"base_change_amount",
		"account_for_change_amount",
		"rounding_adjustment",
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


def _invoice_rate(row: dict[str, Any]) -> float:
	return flt(row.get("conversion_rate")) or 1.0


def _outstanding_in_company_currency(row: dict[str, Any]) -> float:
	# ERPNext stores outstanding in the receivable account currency. Its
	# native payment schedule converts it only when that equals invoice currency.
	outstanding = flt(row.get("outstanding_amount"))
	if not row.get("party_account_currency") or row.get("party_account_currency") == row.get("currency"):
		outstanding *= _invoice_rate(row)
	return outstanding


def _outstanding_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
	balances = [
		_outstanding_in_company_currency(row)
		for row in rows
		if not row.get("is_return") and not row.get("return_against")
	]
	return {
		"outstanding_total": sum(amount for amount in balances if amount > 0),
		"outstanding_count": sum(1 for amount in balances if amount > 0),
	}


def _shift_outstanding(*, user: str, company: str, branch: str, opening_shift: str) -> dict[str, Any]:
	# Do not substitute a day or POS Profile for the exact opening-shift link.
	shift_field = next((
		field for field in ("posa_pos_opening_shift", "pos_opening_shift", "opening_shift")
		if _has_field("Sales Invoice", field)
	), None)
	branch_field = next((
		field for field in ("retailedge_branch", "branch") if _has_field("Sales Invoice", field)
	), None)
	if not (shift_field and branch_field and company and branch and opening_shift):
		return {"outstanding_total": None, "outstanding_count": None}
	rows = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "owner": user, "company": company,
				 branch_field: branch, shift_field: opening_shift},
		fields=["name", "outstanding_amount", "currency", "party_account_currency",
				"conversion_rate", "is_return", "return_against"],
		limit_page_length=0,
	)
	return _outstanding_summary(rows)


def _payment_breakdown(
	invoice_rows: list[dict[str, Any]],
) -> tuple[float, list[dict[str, Any]], dict[str, float]]:
	"""Aggregate net tender and native Payment Entry allocations on scoped invoices.

	Only invoice identifiers already selected by the signed-in cashier's work
	provider enter this query. Never expose Payment Entry or ledger records.
	Payment allocations are not evidence that money entered the current till.
	All displayed amounts use company currency at the invoice conversion rate
	for allocations denominated in the invoice currency.
	"""
	invoices = {row["name"]: row for row in invoice_rows if row.get("name")}
	if not invoices:
		return 0.0, [], {}
	names = list(invoices)
	by_mode: dict[str, float] = defaultdict(float)
	by_invoice: dict[str, float] = dict.fromkeys(names, 0.0)
	change_modes: dict[str, str] = {}

	def add(name, mode, amount):
		by_invoice[name] += amount
		by_mode[mode] += amount

	rows = frappe.get_all(
		"Sales Invoice Payment",
		filters={"parenttype": "Sales Invoice", "parent": ["in", names]},
		fields=["parent", "mode_of_payment", "amount", "base_amount", "account"],
		order_by="parent asc, idx asc",
		limit_page_length=0,
	)
	for row in rows:
		name = row.get("parent")
		if name not in invoices:
			continue
		invoice = invoices[name]
		mode = str(row.get("mode_of_payment") or _("Other payment"))
		amount = row.get("base_amount")
		if amount is None:
			amount = flt(row.get("amount")) * _invoice_rate(invoice)
		add(name, mode, flt(amount))
		if row.get("account") and row.get("account") == invoice.get("account_for_change_amount"):
			change_modes.setdefault(name, mode)
	for name, invoice in invoices.items():
		change = invoice.get("base_change_amount")
		if change is None:
			change = flt(invoice.get("change_amount")) * _invoice_rate(invoice)
		if flt(change):
			add(name, change_modes.get(name) or _("Change returned"), -flt(change))

	# The invoice's own POS tender is already counted above. Only live Payment
	# Entry allocations are added from the receivable ledger, not invoice
	# creation, credit notes, write-offs or unrelated/unallocated receipts.
	ledger = frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"against_voucher_type": "Sales Invoice",
			"against_voucher_no": ["in", names],
			"voucher_type": "Payment Entry",
			"account_type": "Receivable",
			"party_type": "Customer",
			"delinked": 0,
		},
		fields=["voucher_no", "against_voucher_no", "company", "party", "account",
				"amount", "account_currency", "amount_in_account_currency"],
		limit_page_length=0,
	)
	payment_names = sorted({row["voucher_no"] for row in ledger if row.get("voucher_no")})
	payments = {
		row["name"]: row for row in frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", payment_names], "docstatus": 1,
					 "party_type": "Customer", "payment_type": ["in", ["Receive", "Pay"]]},
			fields=["name", "company", "party", "mode_of_payment"],
			limit_page_length=0,
		)
	} if payment_names else {}
	for row in ledger:
		name = row.get("against_voucher_no")
		invoice = invoices.get(name)
		payment = payments.get(row.get("voucher_no"))
		if not invoice or not payment:
			continue
		if not (
			invoice.get("company") == row.get("company") == payment.get("company")
			and invoice.get("customer") == row.get("party") == payment.get("party")
			and invoice.get("debit_to") == row.get("account")
		):
			continue
		amount = flt(row.get("amount"))
		if row.get("account_currency") == invoice.get("currency"):
			amount = flt(row.get("amount_in_account_currency")) * _invoice_rate(invoice)
		add(name, str(payment.get("mode_of_payment") or _("Other payment")), -amount)

	return sum(by_invoice.values()), [
		{"mode_of_payment": mode, "amount": amount}
		for mode, amount in sorted(by_mode.items(), key=lambda item: item[0].lower())
	], by_invoice


def _normalize_activity(
	rows: list[dict[str, Any]], payments_by_invoice: dict[str, float] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
	sales_count = 0
	returns_count = 0
	gross_sales = 0.0
	returns_total = 0.0
	net_sales = 0.0
	activity: list[dict[str, Any]] = []

	for row in rows:
		grand_total = flt(row.get("grand_total"))
		if (row.get("rounding_adjustment") or not grand_total) and row.get("rounded_total") not in (None, ""):
			grand_total = flt(row.get("rounded_total"))
		grand_total *= _invoice_rate(row)
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
				"paid_amount": (
					payments_by_invoice.get(row.get("name"), 0.0)
					if payments_by_invoice is not None
					else (flt(row.get("paid_amount")) - flt(row.get("change_amount"))) * _invoice_rate(row)
				),
				"outstanding_amount": _outstanding_in_company_currency(row),
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
			**_outstanding_summary(rows),
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
		"cash_deposits": 0.0,
		"available_cash": 0.0,
		"message": cashier_context.get("message"),
	}
	if not cashier_context.get("linked_pos_opening_shift"):
		return shift

	snapshot = get_cash_custody_snapshot(
		opening_shift=cashier_context.get("linked_pos_opening_shift"),
		company=company or None,
		pos_profile=cashier_context.get("pos_profile"),
		cashier=user,
	)
	shift.update(
		{
			"open": True,
			"opening_cash": flt(snapshot.get("opening_cash")),
			"cash_sales": flt(snapshot.get("cash_sales")),
			"prior_expenses": flt(snapshot.get("cashier_expenses")),
			"cash_deposits": flt(snapshot.get("submitted_deposits")),
			"available_cash": flt(snapshot.get("available_cash")),
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

	if not company or not branch:
		frappe.throw(_("Choose your working company and branch before viewing your activity."), frappe.PermissionError)

	rows = _invoices_for_date(
		user=user,
		work_date=selected_date,
		company=company,
		branch=branch,
	)
	payments_total, payment_breakdown, payments_by_invoice = _payment_breakdown(rows)
	summary, all_activity = _normalize_activity(rows, payments_by_invoice)
	summary["payments_total"] = payments_total

	if is_today:
		shift = _current_shift_payload(cashier_context=cashier_context, company=company, user=user)
		if shift.get("open"):
			shift.update(_shift_outstanding(
				user=user, company=company, branch=branch, opening_shift=shift["opening_shift"],
			))
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
			"cash_deposits": 0.0,
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
		"currency": frappe.get_cached_value("Company", company, "default_currency") or "",
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
