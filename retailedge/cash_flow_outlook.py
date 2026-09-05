from __future__ import annotations

from typing import Any

import frappe
from erpnext.accounts.report.accounts_receivable.accounts_receivable import ReceivablePayableReport
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

from retailedge import customer_receivables, purchase_reporting
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch
from retailedge.reporting_capabilities import require_report_action
from retailedge.stock_movement_filters import branch_query

REPORT_KEY = "cash-flow-outlook"
OUTLOOK_WEEKS = 13
MAX_LINK_RESULTS = 20


def _company_currency(company: str) -> str:
	return str(frappe.get_cached_value("Company", company, "default_currency") or "") if company else ""


def _default_branch(company: str) -> str:
	if not company or not frappe.has_permission("Company", "read", doc=company):
		return ""
	user = frappe.session.user
	scope = get_operational_branch_scope(company, user=user)
	allowed = _allowed_scope_branches(scope)
	candidate = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	if candidate:
		try:
			_validate_outlook_branch(
				company=company,
				branch=candidate,
				user=user,
				scope=scope,
			)
			return candidate
		except (frappe.PermissionError, frappe.ValidationError):
			pass
	if scope.get("restricted") and len(allowed) == 1:
		return allowed[0]
	return ""


def _validate_outlook_branch(
	*,
	company: str,
	branch: str,
	user: str,
	scope: dict[str, Any] | None = None,
) -> None:
	scope = scope or get_operational_branch_scope(company, user=user)
	if scope.get("restricted") and branch not in _allowed_scope_branches(scope):
		frappe.throw(
			_("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
			frappe.PermissionError,
		)
	validate_operating_branch(company=company, branch=branch, user=user, throw=True)


def _allowed_scope_branches(scope: dict[str, Any]) -> list[str]:
	return sorted(
		str(branch).strip()
		for branch in dict.fromkeys(scope.get("allowed_branches") or [])
		if str(branch or "").strip()
	)


def _assert_document_permissions() -> None:
	for doctype in ("Sales Invoice", "Purchase Invoice"):
		if not frappe.has_permission(doctype, "read"):
			frappe.throw(
				_(
					"You do not have permission to view {0} records required for 13-Week Cash Commitments."
				).format(doctype),
				frappe.PermissionError,
			)


@frappe.whitelist()
def get_cash_flow_outlook_context() -> dict[str, Any]:
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = _default_branch(company)
	capabilities = require_report_action(REPORT_KEY, "view", company=company, branch=branch)
	if company:
		_assert_document_permissions()
	return {
		"default_filters": {"company": company, "branch": branch},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
		"company_currency": _company_currency(company),
		"as_of_date": nowdate(),
		"outlook_weeks": OUTLOOK_WEEKS,
		"capabilities": capabilities,
	}


@frappe.whitelist()
def search_cash_flow_outlook_options(kind: str, txt: str = "", company: str = "") -> list[dict[str, str]]:
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
	if kind == "company":
		rows = frappe.get_list(
			"Company",
			filters={"name": ["like", f"%{txt}%"]},
			fields=["name"],
			order_by="name asc",
			limit=MAX_LINK_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]
	if kind == "branch":
		rows = branch_query("Branch", txt, "name", 0, MAX_LINK_RESULTS, {"company": company})
		return [{"value": row[0], "label": row[0]} for row in rows]
	frappe.throw(_("Unsupported 13-Week Cash Commitments search type."))


def _native_outstanding_rows(company: str, account_type: str) -> list[frappe._dict]:
	filters = frappe._dict(
		{
			"company": company,
			"report_date": nowdate(),
			"ageing_based_on": "Due Date",
			"age_as_on": "Report Date",
			"range": "30, 60, 90, 120",
			"group_by_party": 0,
			"based_on_payment_terms": 1,
			"show_future_payments": 0,
			"show_delivery_notes": 0,
			"show_sales_person": 0,
			"show_remarks": 0,
			"in_party_currency": 0,
			"for_revaluation_journals": 0,
			"ignore_accounts": 0,
		}
	)
	args = {
		"account_type": account_type,
		"naming_by": [
			"Selling Settings" if account_type == "Receivable" else "Buying Settings",
			"cust_master_name" if account_type == "Receivable" else "supp_master_name",
		],
	}
	report = ReceivablePayableReport(filters)
	_columns, data, *_rest = report.run(args)
	return [frappe._dict(row) for row in (data or []) if row]


def _permitted_invoice_names(company: str, branch: str) -> tuple[set[str], set[str], dict[str, int]]:
	sales_filters = frappe._dict({"company": company, "branch": branch, "ageing_bucket": "All"})
	customer_receivables._assert_report_access(sales_filters)
	sales_headers = customer_receivables._get_permitted_invoice_headers(sales_filters)

	purchase_filters = frappe._dict(
		{"company": company, "branch": branch, "as_of_date": nowdate(), "ageing_bucket": "All"}
	)
	purchase_reporting._assert_report_access(purchase_filters)
	purchase_headers = purchase_reporting._get_permitted_invoice_headers(purchase_filters, as_of=True)
	return (
		{str(row.name) for row in sales_headers},
		{str(row.name) for row in purchase_headers},
		{"sales_invoices": len(sales_headers), "purchase_invoices": len(purchase_headers)},
	)


def _bucket_index(due_date: Any, anchor_date: Any) -> int | None:
	anchor = getdate(anchor_date)
	due = getdate(due_date or anchor)
	if due <= anchor:
		return 0
	days_forward = (due - anchor).days
	week_index = ((days_forward - 1) // 7) + 1
	return week_index if week_index <= OUTLOOK_WEEKS else None


def _empty_buckets(anchor_date: Any) -> list[dict[str, Any]]:
	anchor = getdate(anchor_date)
	rows: list[dict[str, Any]] = [
		{
			"bucket": "due-now",
			"period_label": _("Due now"),
			"period_start": "",
			"period_end": str(anchor),
			"receivables_due": 0.0,
			"payables_due": 0.0,
			"net_scheduled": 0.0,
			"cumulative_scheduled_net": 0.0,
			"receivable_rows": 0,
			"payable_rows": 0,
		}
	]
	for week in range(1, OUTLOOK_WEEKS + 1):
		start = add_days(anchor, ((week - 1) * 7) + 1)
		end = add_days(anchor, week * 7)
		rows.append(
			{
				"bucket": f"week-{week}",
				"period_label": _("Week {0}").format(week),
				"period_start": str(start),
				"period_end": str(end),
				"receivables_due": 0.0,
				"payables_due": 0.0,
				"net_scheduled": 0.0,
				"cumulative_scheduled_net": 0.0,
				"receivable_rows": 0,
				"payable_rows": 0,
			}
		)
	return rows


def _eligible_native_rows(
	rows: list[frappe._dict],
	*,
	voucher_type: str,
	permitted_names: set[str],
) -> list[frappe._dict]:
	return [
		row
		for row in rows
		if str(row.get("voucher_type") or "") == voucher_type
		and str(row.get("voucher_no") or "") in permitted_names
		and flt(row.get("outstanding")) > 0
	]


def _apply_rows(
	buckets: list[dict[str, Any]],
	rows: list[frappe._dict],
	*,
	anchor_date: Any,
	amount_field: str,
	count_field: str,
) -> dict[str, float | int]:
	beyond_amount = 0.0
	beyond_rows = 0
	for row in rows:
		amount = flt(row.get("outstanding"))
		index = _bucket_index(row.get("due_date") or row.get("posting_date"), anchor_date)
		if index is None:
			beyond_amount += amount
			beyond_rows += 1
			continue
		buckets[index][amount_field] += amount
		buckets[index][count_field] += 1
	return {"amount": beyond_amount, "rows": beyond_rows}


def _columns(currency: str) -> list[dict[str, Any]]:
	return [
		{"fieldname": "period_label", "label": _("Period"), "fieldtype": "Data"},
		{"fieldname": "period_start", "label": _("From"), "fieldtype": "Date"},
		{"fieldname": "period_end", "label": _("To"), "fieldtype": "Date"},
		{
			"fieldname": "receivables_due",
			"label": _("Receivables Due"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "payables_due",
			"label": _("Payables Due"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "net_scheduled",
			"label": _("Net Scheduled Commitments"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "cumulative_scheduled_net",
			"label": _("Cumulative Scheduled Commitments"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{"fieldname": "receivable_rows", "label": _("Receivable Terms"), "fieldtype": "Int"},
		{"fieldname": "payable_rows", "label": _("Payable Terms"), "fieldtype": "Int"},
	]


def _build_dataset(filters: frappe._dict) -> dict[str, Any]:
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if branch:
		_validate_outlook_branch(
			company=company,
			branch=branch,
			user=frappe.session.user,
		)
	require_report_action(REPORT_KEY, "view", company=company, branch=branch)
	_assert_document_permissions()

	permitted_sales, permitted_purchases, scan = _permitted_invoice_names(company, branch)
	receivable_rows = _eligible_native_rows(
		_native_outstanding_rows(company, "Receivable"),
		voucher_type="Sales Invoice",
		permitted_names=permitted_sales,
	)
	payable_rows = _eligible_native_rows(
		_native_outstanding_rows(company, "Payable"),
		voucher_type="Purchase Invoice",
		permitted_names=permitted_purchases,
	)

	anchor = getdate(nowdate())
	buckets = _empty_buckets(anchor)
	beyond_receivables = _apply_rows(
		buckets,
		receivable_rows,
		anchor_date=anchor,
		amount_field="receivables_due",
		count_field="receivable_rows",
	)
	beyond_payables = _apply_rows(
		buckets,
		payable_rows,
		anchor_date=anchor,
		amount_field="payables_due",
		count_field="payable_rows",
	)

	cumulative = 0.0
	for row in buckets:
		row["net_scheduled"] = flt(row["receivables_due"]) - flt(row["payables_due"])
		cumulative += row["net_scheduled"]
		row["cumulative_scheduled_net"] = cumulative

	through_receivables = sum(flt(row["receivables_due"]) for row in buckets)
	through_payables = sum(flt(row["payables_due"]) for row in buckets)
	currency = _company_currency(company)
	return {
		"title": _("13-Week Cash Commitments"),
		"columns": _columns(currency),
		"rows": buckets,
		"summary": [
			{
				"label": _("Receivables Due Now"),
				"value": buckets[0]["receivables_due"],
				"datatype": "Currency",
			},
			{"label": _("Payables Due Now"), "value": buckets[0]["payables_due"], "datatype": "Currency"},
			{
				"label": _("Receivables Through 13 Weeks"),
				"value": through_receivables,
				"datatype": "Currency",
			},
			{"label": _("Payables Through 13 Weeks"), "value": through_payables, "datatype": "Currency"},
			{
				"label": _("Net Scheduled Commitments"),
				"value": through_receivables - through_payables,
				"datatype": "Currency",
			},
			{
				"label": _("Beyond 13 Weeks Net Commitments"),
				"value": flt(beyond_receivables["amount"]) - flt(beyond_payables["amount"]),
				"datatype": "Currency",
			},
		],
		"company_currency": currency,
		"as_of_date": str(anchor),
		"horizon_weeks": OUTLOOK_WEEKS,
		"branch": branch,
		"scan": {
			**scan,
			"receivable_schedule_rows": len(receivable_rows),
			"payable_schedule_rows": len(payable_rows),
			"beyond_horizon_receivable_rows": int(beyond_receivables["rows"]),
			"beyond_horizon_payable_rows": int(beyond_payables["rows"]),
		},
		"beyond_horizon": {
			"receivables": flt(beyond_receivables["amount"]),
			"payables": flt(beyond_payables["amount"]),
		},
		"metadata": {
			"source_of_truth": "ERPNext Accounts Receivable and Accounts Payable allocation",
			"basis": "current outstanding allocated by native payment terms and due dates",
			"forecasting": False,
			"forecast_owner": "RetailEdge R12 Forecasting & Planning Intelligence",
			"r12_reconciliation_contract": "Replace the R12 simplified known-due commitment scheduler with this payment-term schedule when the intelligence stack is reconciled; do not run parallel commitment calculators.",
			"cash_balance_included": False,
			"journal_entries_included": False,
			"orders_included": False,
			"manual_scenarios_included": False,
			"accounting_mutation": False,
		},
	}


@frappe.whitelist()
def get_cash_flow_outlook(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return _build_dataset(frappe._dict(filters or {}))


def get_cash_flow_outlook_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	return get_cash_flow_outlook(filters)
