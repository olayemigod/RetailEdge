from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, date_diff, flt, getdate, today

MAX_PAYABLE_ROWS = 200
MAX_STATEMENT_ROWS = 500
MAX_STATEMENT_DAYS = 366
DEFAULT_STATEMENT_DAYS = 90


def _portal_suppliers() -> list[str]:
	from retailedge.supplier_portal import _assert_supplier_portal_user

	return _assert_supplier_portal_user()


def get_supplier_financial_companies(suppliers: list[str]) -> list[str]:
	suppliers = [str(name) for name in suppliers if name]
	if not suppliers or not frappe.db.exists("DocType", "Payment Ledger Entry"):
		return []
	rows = frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"account_type": "Payable",
			"party_type": "Supplier",
			"party": ["in", suppliers],
			"delinked": 0,
		},
		fields=["company"],
		group_by="company",
		order_by="company asc",
		limit_page_length=100,
	)
	return [str(row.company) for row in rows if row.company]


def get_supplier_payables_summary(suppliers: list[str]) -> dict[str, Any]:
	suppliers = [str(name) for name in suppliers if name]
	if not suppliers:
		return {
			"invoice_count": 0,
			"balance_count": 0,
			"balances": [],
			"recent_payments": [],
			"source_of_truth": "Purchase Invoice / Payment Entry",
			"read_only": True,
		}

	invoices = []
	if frappe.db.exists("DocType", "Purchase Invoice"):
		invoices = frappe.get_all(
			"Purchase Invoice",
			filters={
				"docstatus": 1,
				"is_return": 0,
				"supplier": ["in", suppliers],
				"outstanding_amount": [">", 0],
			},
			fields=[
				"name",
				"posting_date",
				"due_date",
				"company",
				"supplier",
				"currency",
				"grand_total",
				"outstanding_amount",
				"status",
			],
			order_by="due_date asc, posting_date asc, name asc",
			limit_page_length=MAX_PAYABLE_ROWS + 1,
		)
	if len(invoices) > MAX_PAYABLE_ROWS:
		frappe.throw(
			_("More than {0} open supplier invoices are linked to this account.").format(MAX_PAYABLE_ROWS)
		)

	balances: dict[tuple[str, str], dict[str, Any]] = {}
	today_date = getdate(today())
	for row in invoices:
		company = str(row.company or "")
		currency = str(row.currency or "")
		key = (company, currency)
		balance = balances.setdefault(
			key,
			{
				"company": company,
				"currency": currency,
				"outstanding": 0.0,
				"overdue": 0.0,
				"invoice_count": 0,
				"overdue_count": 0,
				"recent": [],
			},
		)
		amount = flt(row.outstanding_amount)
		due_date = getdate(row.due_date) if row.due_date else None
		overdue = bool(due_date and due_date < today_date and amount > 0)
		balance["outstanding"] += amount
		balance["invoice_count"] += 1
		if overdue:
			balance["overdue"] += amount
			balance["overdue_count"] += 1
		if len(balance["recent"]) < 5:
			balance["recent"].append(
				{
					"purchase_invoice": row.name,
					"posting_date": row.posting_date,
					"due_date": row.due_date,
					"supplier": row.supplier,
					"status": row.status or "",
					"outstanding": amount,
					"currency": currency,
					"overdue": overdue,
				}
			)

	recent_payments = []
	if frappe.db.exists("DocType", "Payment Entry"):
		payment_rows = frappe.get_all(
			"Payment Entry",
			filters={
				"docstatus": 1,
				"payment_type": "Pay",
				"party_type": "Supplier",
				"party": ["in", suppliers],
			},
			fields=[
				"name",
				"posting_date",
				"company",
				"party",
				"received_amount",
				"paid_to_account_currency",
				"mode_of_payment",
				"reference_no",
			],
			order_by="posting_date desc, name desc",
			limit_page_length=5,
		)
		recent_payments = [
			{
				"payment_entry": row.name,
				"posting_date": row.posting_date,
				"company": row.company or "",
				"supplier": row.party or "",
				"amount": flt(row.received_amount),
				"currency": row.paid_to_account_currency or "",
				"mode_of_payment": row.mode_of_payment or "",
				"reference_no": row.reference_no or "",
			}
			for row in payment_rows
		]

	ordered = sorted(balances.values(), key=lambda item: (item["company"], item["currency"]))
	return {
		"invoice_count": len(invoices),
		"balance_count": len(ordered),
		"balances": ordered,
		"recent_payments": recent_payments,
		"source_of_truth": "Submitted Purchase Invoice outstanding_amount and submitted Payment Entry",
		"read_only": True,
		"scope_note": _(
			"Supplier balances are read-only ERPNext Purchase Invoice outstanding amounts. "
			"Recent payments are submitted outgoing Payment Entries and are not a separate wallet or ledger."
		),
	}


def get_supplier_account_statement(
	*,
	company: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
) -> dict[str, Any]:
	suppliers = _portal_suppliers()
	companies = get_supplier_financial_companies(suppliers)
	if not companies:
		return _empty_statement(suppliers)

	company = str(company or "").strip() or companies[0]
	if company not in companies:
		frappe.throw(_("This Company is not linked to your supplier account."), frappe.PermissionError)

	resolved_to = getdate(to_date or today())
	resolved_from = getdate(from_date or add_days(resolved_to, -(DEFAULT_STATEMENT_DAYS - 1)))
	if resolved_from > resolved_to:
		frappe.throw(_("From Date cannot be after To Date."), frappe.ValidationError)
	if date_diff(resolved_to, resolved_from) >= MAX_STATEMENT_DAYS:
		frappe.throw(
			_("Account Statement date range cannot exceed {0} days.").format(MAX_STATEMENT_DAYS),
			frappe.ValidationError,
		)

	ple = frappe.qb.DocType("Payment Ledger Entry")
	opening_rows = (
		frappe.qb.from_(ple)
		.select(Sum(ple.amount).as_("balance"))
		.where(ple.company == company)
		.where(ple.account_type == "Payable")
		.where(ple.party_type == "Supplier")
		.where(ple.party.isin(suppliers))
		.where(ple.delinked == 0)
		.where(ple.posting_date < resolved_from)
	).run(as_dict=True)
	opening_balance = flt(opening_rows[0].balance) if opening_rows else 0.0

	ledger_rows = frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"company": company,
			"account_type": "Payable",
			"party_type": "Supplier",
			"party": ["in", suppliers],
			"delinked": 0,
			"posting_date": ["between", [resolved_from, resolved_to]],
		},
		fields=[
			"name",
			"creation",
			"posting_date",
			"party",
			"voucher_type",
			"voucher_no",
			"against_voucher_type",
			"against_voucher_no",
			"amount",
			"remarks",
		],
		order_by="posting_date asc, creation asc, name asc",
		limit_page_length=MAX_STATEMENT_ROWS + 1,
	)
	if len(ledger_rows) > MAX_STATEMENT_ROWS:
		frappe.throw(
			_("More than {0} ledger entries match this statement period. Narrow the date range.").format(
				MAX_STATEMENT_ROWS
			)
		)

	currency = str(frappe.get_cached_value("Company", company, "default_currency") or "")
	running_balance = opening_balance
	rows: list[dict[str, Any]] = []
	increases = 0.0
	settlements = 0.0
	for row in ledger_rows:
		amount = flt(row.amount)
		increase = amount if amount > 0 else 0.0
		settlement = abs(amount) if amount < 0 else 0.0
		increases += increase
		settlements += settlement
		running_balance += amount
		rows.append(
			{
				"posting_date": row.posting_date,
				"supplier": row.party,
				"voucher_type": row.voucher_type or "",
				"voucher_no": row.voucher_no or "",
				"against_voucher_type": row.against_voucher_type or "",
				"against_voucher_no": row.against_voucher_no or "",
				"remarks": row.remarks or "",
				"increase": increase,
				"settlement": settlement,
				"balance": running_balance,
			}
		)

	return {
		"supplier_names": suppliers,
		"companies": companies,
		"company": company,
		"currency": currency,
		"from_date": str(resolved_from),
		"to_date": str(resolved_to),
		"opening_balance": opening_balance,
		"total_increase": increases,
		"total_settlement": settlements,
		"closing_balance": running_balance,
		"rows": rows,
		"row_count": len(rows),
		"row_limit": MAX_STATEMENT_ROWS,
		"source_of_truth": "Payment Ledger Entry",
		"balance_basis": "ERPNext payable payment ledger signed amounts",
		"read_only": True,
	}


def _empty_statement(suppliers: list[str]) -> dict[str, Any]:
	resolved_to = getdate(today())
	resolved_from = getdate(add_days(resolved_to, -(DEFAULT_STATEMENT_DAYS - 1)))
	return {
		"supplier_names": suppliers,
		"companies": [],
		"company": "",
		"currency": "",
		"from_date": str(resolved_from),
		"to_date": str(resolved_to),
		"opening_balance": 0.0,
		"total_increase": 0.0,
		"total_settlement": 0.0,
		"closing_balance": 0.0,
		"rows": [],
		"row_count": 0,
		"row_limit": MAX_STATEMENT_ROWS,
		"source_of_truth": "Payment Ledger Entry",
		"balance_basis": "ERPNext payable payment ledger signed amounts",
		"read_only": True,
	}
