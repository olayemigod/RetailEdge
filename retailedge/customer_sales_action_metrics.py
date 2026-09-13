from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint, flt

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.customer_opportunity_intelligence import (
	_change_threshold,
	_prior_period_filters,
	build_comparison_rows,
)
from retailedge.customer_sales_intelligence import _get_receivable_exposure, _normalise_filters
from retailedge.sales_quality_intelligence import (
	DEFAULT_HIGH_REDUCTION_PERCENT,
	DEFAULT_LOW_MARGIN_PERCENT,
	ITEM_SCOPE_FIELDS,
	_get_sales_quality_items,
	_matching_invoice_parents,
	build_sales_quality_rows,
)
from retailedge.sales_reporting import (
	_assert_report_access,
	_filter_headers_by_salesperson,
	_get_permitted_invoice_headers,
	_validate_filters,
)


def get_customer_opportunity_action_counts(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	"""Compute only R11 retention/growth counts needed by Action Centre."""
	current_filters = _normalise_filters(filters)
	_validate_filters(current_filters)
	_assert_report_access(current_filters)
	threshold = _change_threshold(current_filters)
	prior_filters = _prior_period_filters(current_filters)
	current_headers = _get_permitted_invoice_headers(current_filters)
	prior_headers = _get_permitted_invoice_headers(prior_filters)
	receivables = _get_receivable_exposure(current_filters)
	rows = build_comparison_rows(
		current_headers,
		prior_headers,
		receivables=receivables,
		change_threshold_percent=threshold,
	)
	return {
		"retention_follow_up": sum(1 for row in rows if row.get("attention_status") == "Follow-up"),
		"growth_opportunities": sum(1 for row in rows if row.get("attention_status") == "Opportunity"),
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice",
			"comparison_basis": "Selected period versus immediately preceding equal-length period",
			"receivables_excluded_from_actions": True,
		},
	}


def get_sales_quality_action_counts(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	"""Compute sales-quality action counts without report-only detail queries."""
	resolved = _normalise_filters(filters)
	resolved.invoice_kind = "All"
	_validate_filters(resolved)
	_assert_report_access(resolved)

	headers = _get_permitted_invoice_headers(resolved)
	headers = _filter_headers_by_salesperson(headers, resolved.get("salesperson"))
	line_scoped = any(resolved.get(field) for field in ITEM_SCOPE_FIELDS)
	if line_scoped:
		matching = _matching_invoice_parents([row.name for row in headers], resolved)
		headers = [row for row in headers if row.name in matching]
	sales_headers = [row for row in headers if not cint(row.get("is_return"))]
	sales_names = [str(row.name) for row in sales_headers]
	show_costs = not should_hide_cost_price()
	items = _get_sales_quality_items(
		sales_names,
		show_costs=show_costs,
		filters=resolved if line_scoped else None,
	)
	rows = build_sales_quality_rows(
		sales_headers,
		invoice_details={},
		items=items,
		team_map={},
		show_costs=show_costs,
		high_reduction_percent=max(
			flt(resolved.get("high_reduction_percent") or DEFAULT_HIGH_REDUCTION_PERCENT),
			0.0,
		),
		low_margin_percent=flt(resolved.get("low_margin_percent") or DEFAULT_LOW_MARGIN_PERCENT),
	)
	return {
		"high_reduction_invoices": sum(1 for row in rows if row.get("high_reduction")),
		"low_or_negative_margin_invoices": (
			sum(1 for row in rows if row.get("low_margin")) if show_costs else 0
		),
		"show_costs": 1 if show_costs else 0,
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice / Sales Invoice Item",
			"cost_visibility_applied": show_costs,
			"lightweight_action_summary": True,
		},
	}
