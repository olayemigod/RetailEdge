from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, date_diff, flt, getdate, today

MAX_ADVANCE_ROWS = 200
MAX_STATEMENT_ROWS = 500
MAX_STATEMENT_DAYS = 366
DEFAULT_STATEMENT_DAYS = 90


def _portal_customers() -> list[str]:
	# Local import avoids a customer_portal <-> financial import cycle.
	from retailedge.customer_portal import _assert_customer_portal_user

	return _assert_customer_portal_user()


def get_customer_financial_companies(customers: list[str]) -> list[str]:
	"""Return Companies represented in native customer receivable ledger entries."""
	customers = [str(name) for name in customers if name]
	if not customers or not frappe.db.exists("DocType", "Payment Ledger Entry"):
		return []
	rows = frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"account_type": "Receivable",
			"party_type": "Customer",
			"party": ["in", customers],
			"delinked": 0,
		},
		fields=["company"],
		group_by="company",
		order_by="company asc",
		limit_page_length=100,
	)
	return [str(row.company) for row in rows if row.company]


def get_customer_advance_summary(customers: list[str]) -> dict[str, Any]:
	"""Return unallocated incoming Payment Entry value without inventing a wallet."""
	customers = [str(name) for name in customers if name]
	if not customers or not frappe.db.exists("DocType", "Payment Entry"):
		return {
			"count": 0,
			"balance_count": 0,
			"balances": [],
			"source_of_truth": "Payment Entry",
			"read_only": True,
		}

	rows = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"party_type": "Customer",
			"party": ["in", customers],
			"unallocated_amount": [">", 0],
		},
		fields=[
			"name",
			"posting_date",
			"company",
			"party",
			"unallocated_amount",
			"paid_from_account_currency",
			"mode_of_payment",
			"reference_no",
		],
		order_by="posting_date desc, name desc",
		limit_page_length=MAX_ADVANCE_ROWS + 1,
	)
	if len(rows) > MAX_ADVANCE_ROWS:
		frappe.throw(
			_("More than {0} available advance payments are linked to this customer account.").format(
				MAX_ADVANCE_ROWS
			)
		)

	balances: dict[tuple[str, str], dict[str, Any]] = {}
	for row in rows:
		company = str(row.company or "")
		currency = str(row.paid_from_account_currency or "")
		key = (company, currency)
		balance = balances.setdefault(
			key,
			{
				"company": company,
				"currency": currency,
				"available_advance": 0.0,
				"count": 0,
				"recent": [],
			},
		)
		balance["available_advance"] += flt(row.unallocated_amount)
		balance["count"] += 1
		if len(balance["recent"]) < 3:
			balance["recent"].append(
				{
					"payment_entry": row.name,
					"posting_date": row.posting_date,
					"customer": row.party,
					"amount": flt(row.unallocated_amount),
					"currency": currency,
					"mode_of_payment": row.mode_of_payment or "",
					"reference_no": row.reference_no or "",
				}
			)

	ordered = sorted(balances.values(), key=lambda item: (item["company"], item["currency"]))
	return {
		"count": len(rows),
		"balance_count": len(ordered),
		"balances": ordered,
		"source_of_truth": "Payment Entry.unallocated_amount",
		"read_only": True,
		"scope_note": _(
			"Available advances are submitted incoming customer payments that ERPNext still shows as "
			"unallocated. Amounts are grouped by Company and account currency and are not a wallet balance."
		),
	}


def get_customer_account_statement(
	*,
	company: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
) -> dict[str, Any]:
	customers = _portal_customers()
	companies = get_customer_financial_companies(customers)
	if not companies:
		return _empty_statement(customers)

	company = str(company or "").strip() or companies[0]
	if company not in companies:
		frappe.throw(_("This Company is not linked to your customer account."), frappe.PermissionError)

	resolved_to = getdate(to_date or today())
	resolved_from = getdate(from_date or add_days(resolved_to, -(DEFAULT_STATEMENT_DAYS - 1)))
	if resolved_from > resolved_to:
		frappe.throw(_("From Date cannot be after To Date."), frappe.ValidationError)
	if date_diff(resolved_to, resolved_from) >= MAX_STATEMENT_DAYS:
		frappe.throw(
			_("Account Statement date range cannot exceed {0} days.").format(MAX_STATEMENT_DAYS),
			frappe.ValidationError,
		)

	base_filters: dict[str, Any] = {
		"company": company,
		"account_type": "Receivable",
		"party_type": "Customer",
		"party": ["in", customers],
		"delinked": 0,
	}
	ple = frappe.qb.DocType("Payment Ledger Entry")
	opening_rows = (
		frappe.qb.from_(ple)
		.select(Sum(ple.amount).as_("balance"))
		.where(ple.company == company)
		.where(ple.account_type == "Receivable")
		.where(ple.party_type == "Customer")
		.where(ple.party.isin(customers))
		.where(ple.delinked == 0)
		.where(ple.posting_date < resolved_from)
	).run(as_dict=True)
	opening_balance = flt(opening_rows[0].balance) if opening_rows else 0.0

	ledger_rows = frappe.get_all(
		"Payment Ledger Entry",
		filters={**base_filters, "posting_date": ["between", [resolved_from, resolved_to]]},
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
	debits = 0.0
	credits = 0.0
	for row in ledger_rows:
		amount = flt(row.amount)
		debit = amount if amount > 0 else 0.0
		credit = abs(amount) if amount < 0 else 0.0
		debits += debit
		credits += credit
		running_balance += amount
		rows.append(
			{
				"posting_date": row.posting_date,
				"customer": row.party,
				"voucher_type": row.voucher_type or "",
				"voucher_no": row.voucher_no or "",
				"against_voucher_type": row.against_voucher_type or "",
				"against_voucher_no": row.against_voucher_no or "",
				"remarks": row.remarks or "",
				"debit": debit,
				"credit": credit,
				"balance": running_balance,
			}
		)

	return {
		"customer_names": customers,
		"companies": companies,
		"company": company,
		"currency": currency,
		"from_date": str(resolved_from),
		"to_date": str(resolved_to),
		"opening_balance": opening_balance,
		"total_debit": debits,
		"total_credit": credits,
		"closing_balance": running_balance,
		"rows": rows,
		"row_count": len(rows),
		"row_limit": MAX_STATEMENT_ROWS,
		"source_of_truth": "Payment Ledger Entry",
		"balance_basis": "ERPNext receivable payment ledger signed amounts",
		"read_only": True,
	}


def _empty_statement(customers: list[str]) -> dict[str, Any]:
	resolved_to = getdate(today())
	resolved_from = getdate(add_days(resolved_to, -(DEFAULT_STATEMENT_DAYS - 1)))
	return {
		"customer_names": customers,
		"companies": [],
		"company": "",
		"currency": "",
		"from_date": str(resolved_from),
		"to_date": str(resolved_to),
		"opening_balance": 0.0,
		"total_debit": 0.0,
		"total_credit": 0.0,
		"closing_balance": 0.0,
		"rows": [],
		"row_count": 0,
		"row_limit": MAX_STATEMENT_ROWS,
		"source_of_truth": "Payment Ledger Entry",
		"balance_basis": "ERPNext receivable payment ledger signed amounts",
		"read_only": True,
	}
