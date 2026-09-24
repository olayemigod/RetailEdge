from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from typing import Any, Callable

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, get_first_day, getdate, now_datetime, nowdate, today

from retailedge.customer_receivables import get_customer_receivables
from retailedge.dashboard_capabilities import require_dashboard_action
from retailedge.expense_register import get_expense_register
from retailedge.financial_position import _get_liquid_position
from retailedge.operating_context import get_effective_operating_context
from retailedge.payment_settlement_analysis import get_payment_settlement_analysis_export
from retailedge.profitability_intelligence import get_profitability_summary
from retailedge.reporting_scope import has_unrestricted_report_scope
from retailedge.sales_reporting import (
	get_sales_by_item_export,
	get_sales_financial_summary,
	get_sales_visual_aggregates,
)
from retailedge.stock_position import get_stock_position
from retailedge.supplier_payables import get_supplier_payables
from retailedge.utils.settings import get_retailedge_settings

DASHBOARD_KEY = "owner-dashboard"
SCHEMA_VERSION = 1
TOP_COMPOSITION_ROWS = 8
COMPARISON_MODES = {"Previous Period", "Off"}
COMPOSITION_DIMENSIONS = {"Item Group", "Brand", "Branch"}


def _financial_dashboard_preferences() -> dict[str, Any]:
	settings = get_retailedge_settings()
	comparison_mode = str(
		getattr(settings, "financial_dashboard_comparison_mode", "") or "Previous Period"
	).strip()
	if comparison_mode not in COMPARISON_MODES:
		comparison_mode = "Previous Period"
	composition_dimension = str(
		getattr(settings, "financial_dashboard_composition_dimension", "") or "Item Group"
	).strip()
	if composition_dimension not in COMPOSITION_DIMENSIONS:
		composition_dimension = "Item Group"
	return {
		"comparison_mode": comparison_mode,
		"composition_dimension": composition_dimension,
		"show_collection": bool(
			1 if getattr(settings, "financial_dashboard_show_collection", None) is None
			else int(getattr(settings, "financial_dashboard_show_collection", 1) or 0)
		),
		"show_financial_health": bool(
			1 if getattr(settings, "financial_dashboard_show_financial_health", None) is None
			else int(getattr(settings, "financial_dashboard_show_financial_health", 1) or 0)
		),
		"show_outstanding": bool(
			1 if getattr(settings, "financial_dashboard_show_outstanding", None) is None
			else int(getattr(settings, "financial_dashboard_show_outstanding", 1) or 0)
		),
	}


@frappe.whitelist()
def get_financial_dashboard_context() -> dict[str, Any]:
	operating = get_effective_operating_context()
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	capabilities = require_dashboard_action(
		DASHBOARD_KEY,
		"view",
		company=company,
		branch=branch,
	)
	preferences = _financial_dashboard_preferences()
	return {
		"title": _("Financial Dashboard"),
		"dashboard_key": DASHBOARD_KEY,
		"schema_version": SCHEMA_VERSION,
		"default_filters": {
			"company": company,
			"branch": branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
			"comparison_mode": preferences["comparison_mode"],
			"composition_dimension": preferences["composition_dimension"],
		},
		"tenant_name": company,
		"branch_name": branch,
		"user_name": frappe.db.get_value("User", frappe.session.user, "full_name")
		or frappe.session.user,
		"capabilities": capabilities,
		"preferences": preferences,
		"comparison_options": ["Previous Period", "Off"],
		"composition_options": ["Item Group", "Brand", "Branch"],
		"date_reference": today(),
	}


@frappe.whitelist()
def get_financial_dashboard_data(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	company = str(filters.get("company") or "").strip()
	branch = str(filters.get("branch") or "").strip()
	if not company:
		operating = get_effective_operating_context()
		company = str(operating.get("company") or "").strip()
		if "branch" not in filters:
			branch = str(operating.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Company is required."), frappe.ValidationError)
	preferences = _financial_dashboard_preferences()
	comparison_mode = str(filters.get("comparison_mode") or preferences["comparison_mode"]).strip()
	if comparison_mode not in COMPARISON_MODES:
		frappe.throw(_("Unsupported Financial Dashboard comparison mode."), frappe.ValidationError)
	composition_dimension = str(filters.get("composition_dimension") or preferences["composition_dimension"]).strip()
	if composition_dimension not in COMPOSITION_DIMENSIONS:
		frappe.throw(_("Unsupported Financial Dashboard composition dimension."), frappe.ValidationError)
	from_date = getdate(filters.get("from_date") or get_first_day(today()))
	to_date = getdate(filters.get("to_date") or today())
	if from_date > to_date:
		frappe.throw(_("From Date cannot be after To Date."), frappe.ValidationError)

	capabilities = require_dashboard_action(
		DASHBOARD_KEY,
		"view",
		company=company,
		branch=branch,
	)
	period_filters = {
		"company": company,
		"branch": branch,
		"from_date": str(from_date),
		"to_date": str(to_date),
	}
	current_filters = {"company": company, "branch": branch}
	currency = str(
		frappe.get_cached_value("Company", company, "default_currency") or ""
	)

	sales_visual = _safe_payload(
		lambda: get_sales_visual_aggregates(period_filters),
		restricted_reason=_("Your current permissions do not allow sales summary or trend."),
	)
	sales = _sales_summary_from_visual(sales_visual)
	sales_detail = {
		"available": False,
		"availability": "unavailable",
		"reason": _("Item-level sales detail is not required for the selected composition."),
		"payload": {},
	}
	if composition_dimension in {"Item Group", "Brand"}:
		sales_detail = _safe_payload(
			lambda: get_sales_by_item_export(period_filters),
			restricted_reason=_("Your current permissions do not allow sales detail."),
		)
	invoices = _safe_payload(
		lambda: get_sales_financial_summary(period_filters),
		restricted_reason=_("Your current permissions do not allow invoice totals."),
	)
	payments = _safe_payload(
		lambda: get_payment_settlement_analysis_export(
			{**period_filters, "group_by": "Payment Type"}
		),
		restricted_reason=_("Your current permissions do not allow settlement analysis."),
	)
	expenses = _safe_payload(
		lambda: get_expense_register(
			filters={
				**period_filters,
				"view_mode": "consolidated",
				"include_unposted_cashier_expenses": 1,
			},
			page=1,
			page_size=1,
		),
		restricted_reason=_("Your current permissions do not allow consolidated expenses."),
	)
	profitability = _safe_payload(
		lambda: get_profitability_summary(period_filters),
		restricted_reason=_("Your current cost-visibility policy does not allow profitability values."),
	)
	receivables = _safe_payload(
		lambda: get_customer_receivables(
			filters=current_filters,
			page=1,
			page_size=1,
		),
		restricted_reason=_("Your current permissions do not allow receivables."),
	)
	payables = _safe_payload(
		lambda: get_supplier_payables(
			filters=current_filters,
			page=1,
			page_size=1,
		),
		restricted_reason=_("Your current permissions do not allow payables."),
	)
	stock = _safe_payload(
		lambda: get_stock_position(
			filters=current_filters,
			page=1,
			page_size=1,
		),
		restricted_reason=_("Your current permissions do not allow stock position."),
	)

	unrestricted_company_scope = has_unrestricted_report_scope(
		company,
		user=frappe.session.user,
	)
	liquid = _safe_payload(
		lambda: _get_liquid_position(
			company=company,
			branch=branch,
			unrestricted_company_scope=unrestricted_company_scope,
		),
		restricted_reason=_("Your current permissions do not allow Cash & Bank balances."),
	)
	if liquid["available"] and not (liquid["payload"] or {}).get("available"):
		liquid = {
			"available": False,
			"availability": "restricted",
			"reason": (liquid["payload"] or {}).get("reason")
			or _("Cash & Bank balance is unavailable for this scope."),
			"payload": {},
		}

	previous_to = add_days(from_date, -1)
	period_days = max(date_diff(to_date, from_date) + 1, 1)
	previous_from = add_days(previous_to, -(period_days - 1))
	previous_filters = {
		**period_filters,
		"from_date": str(previous_from),
		"to_date": str(previous_to),
	}
	previous_sales = {"available": False, "availability": "unavailable", "reason": _("Comparison is off."), "payload": {}}
	if comparison_mode == "Previous Period":
		previous_sales = _safe_payload(
			lambda: get_sales_visual_aggregates(previous_filters),
			restricted_reason=_("Your current permissions do not allow the comparison sales period."),
		)

	summary = _build_summary(
		sales=sales,
		payments=payments,
		expenses=expenses,
		profitability=profitability,
		receivables=receivables,
		payables=payables,
		stock=stock,
		liquid=liquid,
		currency=currency,
		period_filters=period_filters,
		current_filters=current_filters,
	)
	_attach_period_comparisons(
		summary,
		comparison_mode=comparison_mode,
		previous_sales=previous_sales,
	)

	payload = {
		"schema_version": SCHEMA_VERSION,
		"title": _("Financial Dashboard"),
		"eyebrow": _("Financial Overview"),
		"subtitle": _(
			"Sales, settlement, expenses, current exposure and financial health for the authorised business scope."
		),
		"context": {
			"company": company,
			"branch": branch,
			"currency": currency,
			"from_date": str(from_date),
			"to_date": str(to_date),
			"comparison_from_date": str(previous_from),
			"comparison_to_date": str(previous_to),
			"comparison_mode": comparison_mode,
			"composition_dimension": composition_dimension,
			"current_snapshot_date": nowdate(),
			"generated_at": str(now_datetime()),
			"scope_fingerprint": _scope_fingerprint(
				company=company,
				branch=branch,
				from_date=str(from_date),
				to_date=str(to_date),
			),
		},
		"capabilities": {
			"view": bool(capabilities.get("can_view")),
			"print": bool(capabilities.get("can_print")),
			"export": bool(capabilities.get("can_export")),
			"costs": bool(profitability.get("available")),
			"dimensions": ["item_group", "brand", "branch"],
			"comparison_modes": ["Previous Period", "Off"],
			"actions": [
				"sales_invoice_register",
				"sales_by_item",
				"payment_settlement_analysis",
				"cash_movement",
				"expense_register",
				"customer_receivables",
				"supplier_payables",
				"profitability_intelligence",
				"branch_performance",
			],
		},
		"summary": summary,
		"collection_metrics": _build_collection_metrics(
			invoices=invoices,
			receivables=receivables,
			currency=currency,
			period_filters=period_filters,
			current_filters=current_filters,
		) if preferences["show_collection"] else [],
		"composition": _build_composition(
			sales=sales_detail,
			sales_visual=sales_visual,
			dimension=composition_dimension,
			branch=branch,
			currency=currency,
			period_filters=period_filters,
		),
		"health": _build_health(
			sales=sales,
			expenses=expenses,
			profitability=profitability,
			currency=currency,
			period_filters=period_filters,
		) if preferences["show_financial_health"] else {"title": _("Financial Health"), "rows": []},
		"outstanding": _build_outstanding(
			receivables=receivables,
			payables=payables,
			currency=currency,
			current_filters=current_filters,
		) if preferences["show_outstanding"] else {"title": _("Outstanding Insights"), "rows": []},
		"trends": _build_trends(
			sales_visual=sales_visual,
			currency=currency,
			period_filters=period_filters,
		),
		"alerts": _build_alerts(
			profitability=profitability,
			expenses=expenses,
			receivables=receivables,
			payables=payables,
			currency=currency,
			period_filters=period_filters,
			current_filters=current_filters,
		),
		"report_links": _report_links(
			period_filters=period_filters,
			current_filters=current_filters,
		),
		"metadata": {
			"accounting_authority": "ERPNext",
			"net_sales_basis": "submitted Sales Invoice base_net_total after returns; tax exclusive; Company currency",
			"posted_expense_basis": "governed consolidated posted expense register",
			"receivable_payable_basis": "current ERPNext outstanding",
			"cash_bank_basis": "current eligible Cash/Bank closing balances; Company-only when unrestricted",
			"customer_receipts_coverage": "Payment Entry customer Receive payments only; POS/Journal/refund consolidation not yet complete",
			"invoice_cohort_collection": "withheld until complete allocation/credit/write-off coverage is accepted",
			"comparison_policy": "preceding equal-length period for Net Sales using the bounded tax-exclusive sales aggregate; zero previous values are reported as no comparable baseline",
			"preferences": preferences,
			"source_scans": _source_scan_metadata({
				"sales_summary": sales_visual,
				"sales_detail": sales_detail,
				"invoices": invoices,
				"expenses": expenses,
				"receivables": receivables,
				"payables": payables,
				"stock": stock,
			}),
		},
	}
	return payload


def build_financial_dashboard_export_dataset(
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	payload = get_financial_dashboard_data(filters)
	rows: list[dict[str, Any]] = []
	for metric in payload.get("summary") or []:
		rows.append(_export_metric_row(_("Executive Summary") if metric.get("group") == "executive" else _("Current Position"), metric))
	for metric in payload.get("collection_metrics") or []:
		rows.append(_export_metric_row(_("Collection Performance"), metric))
	for section_key, title in (
		("health", _("Financial Health")),
		("outstanding", _("Outstanding Insights")),
	):
		for row in (payload.get(section_key) or {}).get("rows") or []:
			rows.append(
				{
					"section": title,
					"metric": row.get("metric") or row.get("label") or "",
					"basis": row.get("basis") or "",
					"value": row.get("display_value") or row.get("value"),
					"availability": row.get("availability") or "available",
					"definition": row.get("definition") or "",
				}
			)
	return {
		"title": _("Financial Dashboard"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 180},
			{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 230},
			{"fieldname": "basis", "label": _("Basis"), "fieldtype": "Data", "width": 150},
			{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 180},
			{"fieldname": "availability", "label": _("Availability"), "fieldtype": "Data", "width": 120},
			{"fieldname": "definition", "label": _("Definition"), "fieldtype": "Data", "width": 360},
		],
		"rows": rows,
		"summary": [
			{
				"label": metric.get("label"),
				"value": metric.get("value"),
				"datatype": metric.get("datatype"),
				"currency": metric.get("currency"),
			}
			for metric in payload.get("summary") or []
			if metric.get("group") == "executive"
			and metric.get("availability") in {"available", "partial"}
		],
		"filters": {
			"company": (payload.get("context") or {}).get("company"),
			"branch": (payload.get("context") or {}).get("branch"),
			"from_date": (payload.get("context") or {}).get("from_date"),
			"to_date": (payload.get("context") or {}).get("to_date"),
		},
	}


def _build_summary(
	*,
	sales: dict[str, Any],
	payments: dict[str, Any],
	expenses: dict[str, Any],
	profitability: dict[str, Any],
	receivables: dict[str, Any],
	payables: dict[str, Any],
	stock: dict[str, Any],
	liquid: dict[str, Any],
	currency: str,
	period_filters: dict[str, Any],
	current_filters: dict[str, Any],
) -> list[dict[str, Any]]:
	sales_value = _summary_value(sales, "Net Sales")
	posted_expenses = _summary_value(expenses, "Posted Expenses")
	margin = _summary_value(profitability, "Transactional Gross Profit")
	missing_cost = _summary_value(profitability, "Items Missing Recorded Cost")
	customer_receipts, receipt_exceptions = _payment_entry_customer_receipts(payments)
	summary = [
		_metric(
			"net_sales",
			_("Net Sales"),
			sales_value,
			"Currency",
			currency,
			"period",
			"sales.net_sales",
			sales,
			action=_action("sales-by-item", period_filters, basis="period"),
			helper=_("Submitted Sales Invoice base net totals after discounts and returns; tax exclusive."),
			group="executive",
		),
		_metric(
			"customer_receipts_payment_entries",
			_("Customer Receipts — Payment Entries"),
			customer_receipts,
			"Currency",
			currency,
			"period",
			"settlement.customer_receipts.payment_entries",
			payments,
			availability_override="partial" if payments.get("available") else None,
			action=_action("payment-settlement-analysis", period_filters, basis="period"),
			helper=_(
				"Customer Receive Payment Entries only. POS settlement, Journal adjustment and refund consolidation remains outside this card until verified."
			)
			+ (
				_(" Multi-currency Payment Entry exceptions exist in this period.")
				if receipt_exceptions
				else ""
			),
			group="executive",
		),
		_metric(
			"posted_expenses",
			_("Posted Expenses"),
			posted_expenses,
			"Currency",
			currency,
			"period",
			"expenses.posted",
			expenses,
			action=_action("expense-register", period_filters, basis="period"),
			helper=_("Governed consolidated posted-expense total; unposted cashier exposure is excluded."),
			group="executive",
		),
		_metric(
			"sales_margin_contribution",
			_("Sales Margin Contribution"),
			margin,
			"Currency",
			currency,
			"period",
			"profitability.transactional_margin_contribution",
			profitability,
			availability_override=(
				"partial"
				if profitability.get("available") and flt(missing_cost) > 0
				else None
			),
			action=_action("profitability-intelligence", period_filters, basis="period"),
			helper=(
				_("Some sold items are missing recorded cost; the displayed contribution is partial.")
				if flt(missing_cost) > 0
				else _("Transactional net sales minus recorded item cost; distinct from accounting gross profit.")
			),
			group="executive",
		),
	]

	current_specs = (
		(
			"receivables",
			_("Receivables"),
			_summary_value(receivables, "Total Receivables"),
			receivables,
			"receivables.current",
			"customer-receivables",
		),
		(
			"payables",
			_("Payables"),
			_summary_value(payables, "Total Payables"),
			payables,
			"payables.current",
			"supplier-payables",
		),
	)
	for metric_id, label, value, source, definition_id, destination in current_specs:
		summary.append(
			_metric(
				metric_id,
				label,
				value,
				"Currency",
				currency,
				"current",
				definition_id,
				source,
				action=_action(destination, current_filters, basis="current"),
				helper=_("Current outstanding balance; earlier unpaid documents remain included."),
				group="current_position",
			)
		)

	liquid_payload = liquid.get("payload") or {}
	summary.append(
		_metric(
			"cash_bank",
			_("Cash & Bank"),
			liquid_payload.get("balance"),
			"Currency",
			currency,
			"current",
			"cash_bank.current_closing_balance",
			liquid,
			action={},
			helper=liquid.get("reason")
			or _("Current closing balances of eligible Company Cash and Bank accounts. Use the supporting Cash Movement report for period inflows and outflows."),
			group="current_position",
		)
	)

	stock_value = _summary_value(stock, "Stock Value")
	stock_source = dict(stock)
	if stock.get("available") and stock_value is None:
		stock_source = {
			**stock,
			"available": False,
			"availability": "restricted",
			"reason": _("Stock valuation is hidden by the current cost-visibility policy."),
		}
	summary.append(
		_metric(
			"stock_value",
			_("Stock Value"),
			stock_value,
			"Currency",
			currency,
			"current",
			"stock.current_valuation",
			stock_source,
			action=_action("stock-position", current_filters, basis="current"),
			helper=stock_source.get("reason")
			or _("Current governed stock valuation; never derived from selling price."),
			group="current_position",
		)
	)
	return summary


def _build_collection_metrics(
	*,
	invoices: dict[str, Any],
	receivables: dict[str, Any],
	currency: str,
	period_filters: dict[str, Any],
	current_filters: dict[str, Any],
) -> list[dict[str, Any]]:
	net_invoiced = _summary_value(invoices, "Net Invoiced")
	invoice_count = _summary_value(invoices, "Invoices")
	average_invoice = (
		flt(net_invoiced) / flt(invoice_count)
		if net_invoiced is not None and flt(invoice_count)
		else 0.0
	)
	return [
		{
			"id": "invoice_cohort_collection_rate",
			"label": _("Invoice-cohort Collection"),
			"value": None,
			"datatype": "Percent",
			"currency": "",
			"basis": "invoice_cohort",
			"definition_id": "collection.invoice_cohort",
			"availability": "unavailable",
			"reason": _(
				"Withheld until Payment Entry references, POS settlements, credits, write-offs and reversals are reconciled to the same invoice cohort."
			),
			"action": _action("payment-settlement-analysis", period_filters, basis="invoice_cohort"),
		},
		_metric(
			"average_sales_invoice_value",
			_("Average Sales Invoice Value"),
			average_invoice,
			"Currency",
			currency,
			"period",
			"sales.average_invoice.tax_inclusive",
			invoices,
			action=_action("sales-invoice-register", period_filters, basis="period"),
			helper=_("Tax-inclusive Net Invoiced divided by submitted invoice count for the selected period."),
		),
		_metric(
			"overdue_receivables",
			_("Overdue Receivables"),
			_summary_value(receivables, "Overdue"),
			"Currency",
			currency,
			"current",
			"receivables.current_overdue",
			receivables,
			action=_action(
				"customer-receivables",
				{**current_filters, "collection_status": "Overdue"},
				basis="current",
			),
			helper=_("Current overdue customer balance; not limited to invoices issued in the selected period."),
		),
		{
			"id": "days_to_full_payment",
			"label": _("Days to Full Payment"),
			"value": None,
			"datatype": "Float",
			"currency": "",
			"basis": "invoice_cohort",
			"definition_id": "collection.days_to_full_settlement",
			"availability": "unavailable",
			"reason": _(
				"Full-settlement timing is withheld until partial payments, reversals and POS settlement paths are reconstructed reliably."
			),
			"action": _action("payment-settlement-analysis", period_filters, basis="invoice_cohort"),
		},
	]


def _build_composition(
	*,
	sales: dict[str, Any],
	sales_visual: dict[str, Any],
	dimension: str,
	branch: str,
	currency: str,
	period_filters: dict[str, Any],
) -> dict[str, Any]:
	dimension = dimension if dimension in COMPOSITION_DIMENSIONS else "Item Group"
	buckets: dict[str, float] = defaultdict(float)
	drill_field = ""
	destination = ""
	placeholder = _("Unspecified")

	if dimension == "Branch":
		if not sales_visual.get("available"):
			return {
				"title": _("Revenue Composition"),
				"dimension_label": _("Branch"),
				"currency": currency,
				"availability": sales_visual.get("availability") or "unavailable",
				"reason": sales_visual.get("reason") or "",
				"rows": [],
			}
		visual_payload = sales_visual.get("payload") or {}
		if branch:
			buckets[branch] = sum(flt(row.get("net_sales")) for row in visual_payload.get("trend") or [])
		elif visual_payload.get("branch_mix_supported"):
			for row in visual_payload.get("branch_mix") or []:
				label = str(row.get("branch") or _("Unattributed")).strip() or _("Unattributed")
				buckets[label] += flt(row.get("net_sales"))
		else:
			return {
				"title": _("Revenue Composition"),
				"description": _("Branch attribution is unavailable for this Company."),
				"dimension_label": _("Branch"),
				"currency": currency,
				"availability": "unavailable",
				"reason": _("Sales Invoice Branch attribution is unavailable for this Company."),
				"rows": [],
			}
		drill_field = "branch"
		destination = "sales-invoice-register"
		placeholder = _("Unattributed")
	else:
		if not sales.get("available"):
			return {
				"title": _("Revenue Composition"),
				"dimension_label": _(dimension),
				"currency": currency,
				"availability": sales.get("availability") or "unavailable",
				"reason": sales.get("reason") or "",
				"rows": [],
			}
		fieldname = "brand" if dimension == "Brand" else "item_group"
		placeholder = _("Unbranded") if dimension == "Brand" else _("Unspecified")
		for row in (sales.get("payload") or {}).get("rows") or []:
			label = str(row.get(fieldname) or placeholder).strip() or placeholder
			buckets[label] += flt(row.get("net_sales"))
		if dimension == "Item Group":
			drill_field = "item_group"
			destination = "sales-by-item"

	ordered = sorted(buckets.items(), key=lambda item: (-abs(item[1]), item[0]))
	visible = ordered[:TOP_COMPOSITION_ROWS]
	remainder = ordered[TOP_COMPOSITION_ROWS:]
	if remainder:
		visible.append((_("Other"), sum(value for _label, value in remainder)))
	total = sum(value for _label, value in visible)
	signed = any(value < 0 for _label, value in visible)
	rows = []
	for label, value in visible:
		filters = dict(period_filters)
		action = {}
		if destination and drill_field and label not in {_("Other"), placeholder}:
			filters[drill_field] = label
			action = _action(destination, filters, basis="period")
		rows.append(
			{
				"id": label,
				"label": label,
				"value": value,
				"datatype": "Currency",
				"currency": currency,
				"share": (value / total * 100.0) if not signed and total > 0 else None,
				"action": action,
			}
		)
	return {
		"title": _("Revenue Composition"),
		"description": _("Tax-exclusive Net Sales by {0} for the authorised selected period.").format(_(dimension)),
		"dimension_label": _(dimension),
		"value_label": _("Net Sales"),
		"datatype": "Currency",
		"currency": currency,
		"chart_kind": "bar" if signed else "donut",
		"rows": rows,
	}


def _build_trends(
	*,
	sales_visual: dict[str, Any],
	currency: str,
	period_filters: dict[str, Any],
) -> dict[str, Any]:
	if not sales_visual.get("available"):
		return {
			"title": _("Performance Trends"),
			"availability": sales_visual.get("availability") or "unavailable",
			"reason": sales_visual.get("reason") or "",
			"rows": [],
		}
	rows = []
	for row in (sales_visual.get("payload") or {}).get("trend") or []:
		rows.append(
			{
				"name": str(row.get("posting_date") or ""),
				"posting_date": row.get("posting_date"),
				"net_sales": flt(row.get("net_sales")),
				"transactions": int(row.get("transactions") or 0),
				"action": _action(
					"sales-invoice-register",
					{
						**period_filters,
						"from_date": str(row.get("posting_date") or ""),
						"to_date": str(row.get("posting_date") or ""),
					},
					basis="period",
				),
			}
		)
	return {
		"title": _("Performance Trends"),
		"description": _("Daily tax-exclusive Net Sales using the same authority as the headline."),
		"columns": [
			{"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date", "sortable": False},
			{"fieldname": "net_sales", "label": _("Net Sales"), "fieldtype": "Currency", "options": currency, "sortable": False},
			{"fieldname": "transactions", "label": _("Transactions"), "fieldtype": "Int", "sortable": False},
		],
		"rows": rows,
	}


def _sales_summary_from_visual(source: dict[str, Any]) -> dict[str, Any]:
	if not source.get("available"):
		return dict(source)
	payload = source.get("payload") or {}
	value = sum(flt(row.get("net_sales")) for row in payload.get("trend") or [])
	return {
		"available": True,
		"availability": "available",
		"reason": "",
		"payload": {
			"summary": [{"label": _("Net Sales"), "value": value, "datatype": "Currency"}],
			"scan": payload.get("scan") or {},
		},
	}


def _attach_period_comparisons(
	summary: list[dict[str, Any]],
	*,
	comparison_mode: str,
	previous_sales: dict[str, Any],
) -> None:
	if comparison_mode != "Previous Period":
		return
	by_id = {str(metric.get("id") or ""): metric for metric in summary}
	metric = by_id.get("net_sales")
	if not metric or metric.get("availability") not in {"available", "partial"}:
		return
	if not previous_sales.get("available"):
		metric["comparison"] = {
			"availability": previous_sales.get("availability") or "unavailable",
			"value": None,
			"label": _("Comparison unavailable"),
			"reason": previous_sales.get("reason") or _("Comparison unavailable."),
		}
		return
	previous_value = sum(
		flt(row.get("net_sales"))
		for row in (previous_sales.get("payload") or {}).get("trend") or []
	)
	metric["comparison"] = _period_comparison_value(metric.get("value"), previous_value)


def _period_comparison_value(current_value: Any, previous_value: Any) -> dict[str, Any]:
	previous_number = flt(previous_value)
	if previous_number == 0:
		return {
			"availability": "unavailable",
			"value": None,
			"label": _("No comparable baseline"),
			"reason": _("The previous period value is zero."),
			"previous_value": previous_number,
		}
	change_percent = (flt(current_value) - previous_number) / abs(previous_number) * 100.0
	return {
		"availability": "available",
		"value": change_percent,
		"unit": "percent",
		"label": _("vs previous period"),
		"previous_value": previous_number,
	}


def _period_comparison(
	current_value: Any,
	previous_source: dict[str, Any],
	previous_label: str,
) -> dict[str, Any]:
	if not previous_source.get("available"):
		return {
			"availability": previous_source.get("availability") or "unavailable",
			"value": None,
			"label": _("Comparison unavailable"),
			"reason": previous_source.get("reason") or _("Comparison unavailable."),
		}
	previous_value = _summary_value(previous_source, previous_label)
	if previous_value is None:
		return {
			"availability": "unavailable",
			"value": None,
			"label": _("No comparable baseline"),
			"reason": _("The previous period did not return this metric."),
		}
	return _period_comparison_value(current_value, previous_value)


def _build_health(
	*,
	sales: dict[str, Any],
	expenses: dict[str, Any],
	profitability: dict[str, Any],
	currency: str,
	period_filters: dict[str, Any],
) -> dict[str, Any]:
	rows: list[dict[str, Any]] = []
	for label, definition, source_label in (
		(_("Accounting Gross Profit"), "profitability.accounting_gross_profit", "Accounting Gross Profit"),
		(_("Accounting Net Profit"), "profitability.accounting_net_profit", "Accounting Net Profit"),
		(_("Transactional Gross Margin"), "profitability.transactional_gross_margin", "Transactional Gross Margin"),
	):
		value = _summary_value(profitability, source_label)
		if value is None:
			continue
		datatype = "Percent" if "Margin" in source_label else "Currency"
		rows.append(
			{
				"name": definition,
				"metric": label,
				"display_value": _display_value(value, datatype, currency),
				"basis": _("Selected period"),
				"availability": "available",
				"definition": definition,
				"action": _action("profitability-intelligence", period_filters, basis="period"),
			}
		)

	net_sales = _summary_value(sales, "Net Sales")
	posted_expenses = _summary_value(expenses, "Posted Expenses")
	if net_sales not in (None, 0) and posted_expenses is not None:
		ratio = flt(posted_expenses) / abs(flt(net_sales)) * 100.0
		rows.append(
			{
				"name": "expenses.posted_ratio",
				"metric": _("Posted Expense Ratio"),
				"display_value": _display_value(ratio, "Percent", currency),
				"basis": _("Selected period"),
				"availability": "available",
				"definition": "expenses.posted_ratio_to_net_sales",
				"action": _action("expense-register", period_filters, basis="period"),
			}
		)
	return {
		"title": _("Financial Health"),
		"description": _("Accounting and transactional measures remain explicitly separated."),
		"columns": [
			{"fieldname": "metric", "label": _("Measure"), "fieldtype": "Data", "sortable": False},
			{"fieldname": "display_value", "label": _("Value"), "fieldtype": "Data", "sortable": False},
			{"fieldname": "basis", "label": _("Basis"), "fieldtype": "Data", "sortable": False},
		],
		"rows": rows,
	}


def _build_outstanding(
	*,
	receivables: dict[str, Any],
	payables: dict[str, Any],
	currency: str,
	current_filters: dict[str, Any],
) -> dict[str, Any]:
	specs = (
		(_("Customer Receivables"), receivables, "Total Receivables", "customer-receivables"),
		(_("Customer Overdue"), receivables, "Overdue", "customer-receivables"),
		(_("Supplier Payables"), payables, "Total Payables", "supplier-payables"),
		(_("Supplier Overdue"), payables, "Overdue", "supplier-payables"),
	)
	rows = []
	for label, source, metric_label, destination in specs:
		value = _summary_value(source, metric_label)
		if value is None:
			continue
		rows.append(
			{
				"name": f"{destination}:{metric_label}",
				"metric": label,
				"display_value": _display_value(value, "Currency", currency),
				"basis": _("Current"),
				"availability": "available",
				"definition": "current_outstanding",
				"action": _action(destination, current_filters, basis="current"),
			}
		)
	return {
		"title": _("Outstanding Insights"),
		"description": _("Current customer and supplier exposure using the same balance date as the underlying registers."),
		"columns": [
			{"fieldname": "metric", "label": _("Exposure"), "fieldtype": "Data", "sortable": False},
			{"fieldname": "display_value", "label": _("Amount"), "fieldtype": "Data", "sortable": False},
			{"fieldname": "basis", "label": _("Basis"), "fieldtype": "Data", "sortable": False},
		],
		"rows": rows,
	}


def _build_alerts(
	*,
	profitability: dict[str, Any],
	expenses: dict[str, Any],
	receivables: dict[str, Any],
	payables: dict[str, Any],
	currency: str,
	period_filters: dict[str, Any],
	current_filters: dict[str, Any],
) -> list[dict[str, Any]]:
	alerts: list[dict[str, Any]] = []
	missing_cost = flt(_summary_value(profitability, "Items Missing Recorded Cost"))
	if missing_cost > 0:
		alerts.append(
			{
				"id": "missing_recorded_cost",
				"label": _("Items missing recorded cost"),
				"description": _("Margin contribution is incomplete until recorded cost is available."),
				"value": missing_cost,
				"datatype": "Int",
				"tone": "warning",
				"availability": "available",
				"action": _action("profitability-intelligence", period_filters, basis="period"),
			}
		)
	posting_blocked = flt(_summary_value(expenses, "Posting Blocked"))
	if posting_blocked > 0:
		alerts.append(
			{
				"id": "expense_posting_blocked",
				"label": _("Expense posting exceptions"),
				"description": _("Cashier expense records require posting review."),
				"value": posting_blocked,
				"datatype": "Int",
				"tone": "warning",
				"availability": "available",
				"action": _action("expense-register", period_filters, basis="period"),
			}
		)
	for alert_id, label, source, destination in (
		("overdue_customers", _("Overdue customer balance"), receivables, "customer-receivables"),
		("overdue_suppliers", _("Overdue supplier balance"), payables, "supplier-payables"),
	):
		value = flt(_summary_value(source, "Overdue"))
		if value <= 0:
			continue
		alerts.append(
			{
				"id": alert_id,
				"label": label,
				"description": _("Current overdue exposure requires review."),
				"value": value,
				"datatype": "Currency",
				"currency": currency,
				"tone": "danger",
				"availability": "available",
				"action": _action(destination, current_filters, basis="current"),
			}
		)
	return alerts[:4]


def _report_links(
	*,
	period_filters: dict[str, Any],
	current_filters: dict[str, Any],
) -> list[dict[str, Any]]:
	return [
		{"id": "sales_invoice_register", "label": _("Sales Invoice Register"), "action": _action("sales-invoice-register", period_filters, basis="period")},
		{"id": "sales_by_item", "label": _("Sales by Item"), "action": _action("sales-by-item", period_filters, basis="period")},
		{"id": "payment_settlement", "label": _("Payment & Settlement Analysis"), "action": _action("payment-settlement-analysis", period_filters, basis="period")},
		{"id": "cash_movement", "label": _("Cash Movement"), "action": _action("cash-movement", period_filters, basis="period")},
		{"id": "expense_register", "label": _("Expense Register"), "action": _action("expense-register", period_filters, basis="period")},
		{"id": "receivables", "label": _("Receivables"), "action": _action("customer-receivables", current_filters, basis="current")},
		{"id": "payables", "label": _("Payables"), "action": _action("supplier-payables", current_filters, basis="current")},
		{"id": "profitability", "label": _("Profitability"), "action": _action("profitability-intelligence", period_filters, basis="period")},
		{"id": "branch_performance", "label": _("Branch Performance"), "action": _action("branch-performance-dashboard", period_filters, basis="period")},
	]


def _payment_entry_customer_receipts(source: dict[str, Any]) -> tuple[float | None, int]:
	if not source.get("available"):
		return None, 0
	allocated = 0.0
	advances = 0.0
	exceptions = 0
	for row in (source.get("payload") or {}).get("rows") or []:
		allocated += flt(row.get("customer_receipts_allocated"))
		advances += flt(row.get("customer_advance_available"))
		exceptions += int(row.get("multi_currency_exception_count") or 0)
	return allocated + advances, exceptions


def _metric(
	metric_id: str,
	label: str,
	value: Any,
	datatype: str,
	currency: str,
	basis: str,
	definition_id: str,
	source: dict[str, Any],
	*,
	action: dict[str, Any] | None = None,
	helper: str = "",
	group: str = "",
	availability_override: str | None = None,
) -> dict[str, Any]:
	available = bool(source.get("available"))
	availability = (
		availability_override
		or ("available" if available else source.get("availability") or "unavailable")
	)
	return {
		"id": metric_id,
		"label": label,
		"value": value if availability in {"available", "partial"} else None,
		"datatype": datatype,
		"currency": currency if datatype == "Currency" else "",
		"basis": basis,
		"definition_id": definition_id,
		"availability": availability,
		"reason": "" if available else source.get("reason") or "",
		"helper": helper,
		"group": group,
		"action": action or {},
	}


def _safe_payload(
	loader: Callable[[], dict[str, Any]],
	*,
	restricted_reason: str,
) -> dict[str, Any]:
	previous_messages = list(getattr(frappe.local, "message_log", []) or [])
	try:
		return {
			"available": True,
			"availability": "available",
			"reason": "",
			"payload": loader() or {},
		}
	except frappe.PermissionError:
		return {
			"available": False,
			"availability": "restricted",
			"reason": restricted_reason,
			"payload": {},
		}
	except frappe.ValidationError as exc:
		return {
			"available": False,
			"availability": "unavailable",
			"reason": str(exc),
			"payload": {},
		}
	finally:
		frappe.local.message_log = previous_messages


def _summary_value(source: dict[str, Any], label: str) -> Any:
	if not source.get("available"):
		return None
	for card in (source.get("payload") or {}).get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return card.get("value")
	return None


def _action(
	destination: str,
	filters: dict[str, Any],
	*,
	basis: str,
) -> dict[str, Any]:
	clean = {
		key: value
		for key, value in dict(filters or {}).items()
		if value not in (None, "")
	}
	if basis == "current":
		clean.pop("from_date", None)
		clean.pop("to_date", None)
	return {
		"kind": "page",
		"destination": destination,
		"filters": clean,
		"basis": basis,
	}


def _display_value(value: Any, datatype: str, currency: str) -> str:
	if value is None:
		return "—"
	if datatype == "Percent":
		return f"{flt(value):,.1f}%"
	if datatype == "Currency":
		return f"{currency} {flt(value):,.2f}".strip()
	return f"{flt(value):,.2f}"


def _export_metric_row(section: str, metric: dict[str, Any]) -> dict[str, Any]:
	availability = metric.get("availability") or "available"
	value = metric.get("value") if availability in {"available", "partial"} else None
	return {
		"section": section,
		"metric": metric.get("label") or "",
		"basis": metric.get("basis") or "",
		"value": value,
		"availability": availability,
		"definition": metric.get("definition_id") or "",
	}


def _source_scan_metadata(
	sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
	result: dict[str, Any] = {}
	for key, source in sources.items():
		if not source.get("available"):
			result[key] = {
				"availability": source.get("availability") or "unavailable",
				"reason": source.get("reason") or "",
			}
			continue
		payload = source.get("payload") or {}
		scan = payload.get("scan")
		if isinstance(scan, dict) and scan:
			result[key] = {"availability": "available", "scan": scan}
	return result


def _scope_fingerprint(
	*,
	company: str,
	branch: str,
	from_date: str,
	to_date: str,
) -> str:
	raw = "|".join(
		(
			frappe.session.user,
			company,
			branch,
			from_date,
			to_date,
		)
	)
	return sha256(raw.encode("utf-8")).hexdigest()[:20]


def _coerce_filters(
	filters: dict[str, Any] | str | None,
) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
