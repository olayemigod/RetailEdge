from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt


def get_accounting_profitability(filters: frappe._dict) -> dict[str, Any]:
	"""Return company-level accounting profit using ERPNext's own financial-report engines.

	RetailEdge must not invent a competing company-profit calculation. The P&L is
	authoritative for income, expense and net profit; ERPNext's Gross and Net Profit
	report is authoritative for the chart-of-accounts `include_in_gross` definition.
	"""
	company = str(filters.get("company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	if filters.get("branch"):
		return {
			"available": False,
			"reason": _(
				"Accounting P&L comparison is company-level until this Branch is mapped to an ERPNext accounting dimension or Cost Center."
			),
			"scope": "company",
		}
	if not frappe.has_permission("Company", "read", doc=company):
		raise frappe.PermissionError(_("You do not have permission to view accounting profitability for this Company."))

	report_filters = frappe._dict(
		company=company,
		filter_based_on="Date Range",
		period_start_date=filters.from_date,
		period_end_date=filters.to_date,
		from_fiscal_year=None,
		to_fiscal_year=None,
		periodicity="Yearly",
		accumulated_values=0,
		presentation_currency=None,
		cost_center=[],
		project=[],
		finance_book=None,
		include_default_book_entries=1,
		show_zero_values=0,
		report_template=None,
		selected_view="Report",
	)

	from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import execute as execute_pl
	from erpnext.accounts.report.gross_and_net_profit_report.gross_and_net_profit_report import execute as execute_gross

	_pl_columns, _pl_data, _message, _chart, report_summary, primitive_net_profit = execute_pl(report_filters)
	_gross_columns, gross_data = execute_gross(report_filters)

	total_income = _summary_value(report_summary, ("Total Income", "Total Income This Year"))
	total_expense = _summary_value(report_summary, ("Total Expense", "Total Expense This Year"))
	net_profit = flt(primitive_net_profit)
	gross_profit = _named_total(gross_data, "Gross Profit")
	gross_margin = (gross_profit / total_income * 100.0) if total_income else None

	return {
		"available": True,
		"scope": "company",
		"total_income": total_income,
		"total_expense": total_expense,
		"gross_profit": gross_profit,
		"gross_margin_percent": gross_margin,
		"net_profit": net_profit,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"source": "ERPNext Profit and Loss Statement + Gross and Net Profit Report",
		"route": "/app/query-report/Profit%20and%20Loss%20Statement",
	}


def build_profit_reconciliation(accounting: dict[str, Any], transactional: dict[str, Any]) -> dict[str, Any]:
	if not accounting.get("available"):
		return {
			"available": False,
			"reason": accounting.get("reason") or _("Accounting reconciliation is unavailable for this scope."),
		}
	transaction_gross_profit = flt(transactional.get("gross_profit"))
	ledger_gross_profit = flt(accounting.get("gross_profit"))
	difference = transaction_gross_profit - ledger_gross_profit
	return {
		"available": True,
		"transaction_gross_profit": transaction_gross_profit,
		"accounting_gross_profit": ledger_gross_profit,
		"difference": difference,
		"matches": abs(difference) < 0.01,
		"explanation": _(
			"A difference can arise from GL adjustments, stock valuation, landed costs, non-stock costs, Journal Entries, returns or account configuration. ERPNext accounting remains authoritative."
		),
	}


def _summary_value(summary: list[dict[str, Any]] | None, labels: tuple[str, ...]) -> float:
	accepted = set(labels) | {_(label) for label in labels}
	for row in summary or []:
		if str(row.get("label") or "") in accepted:
			return flt(row.get("value"))
	return 0.0


def _named_total(rows: list[dict[str, Any]] | None, name: str) -> float:
	accepted = {name, _(name)}
	for row in reversed(rows or []):
		account_name = str(row.get("account_name") or "").strip("'")
		account = str(row.get("account") or "").strip("'")
		if account_name in accepted or account in accepted:
			return flt(row.get("total"))
	return 0.0
