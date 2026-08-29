from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.customer_sales_action_metrics import (
	get_customer_opportunity_action_counts,
	get_sales_quality_action_counts,
)


DEFAULT_CHANGE_THRESHOLD_PERCENT = 25.0
DEFAULT_HIGH_REDUCTION_PERCENT = 10.0
DEFAULT_LOW_MARGIN_PERCENT = 10.0


def get_customer_sales_action_summary(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	"""Return aggregate R11 actions without constructing full report payloads."""
	filters = frappe._dict(dict(filters or {}))
	filters.change_threshold_percent = flt(
		filters.get("change_threshold_percent") or DEFAULT_CHANGE_THRESHOLD_PERCENT
	)
	filters.high_reduction_percent = flt(
		filters.get("high_reduction_percent") or DEFAULT_HIGH_REDUCTION_PERCENT
	)
	filters.low_margin_percent = flt(
		filters.get("low_margin_percent") or DEFAULT_LOW_MARGIN_PERCENT
	)
	period_scope = _period_scope(filters)

	opportunity = get_customer_opportunity_action_counts(filters)
	quality = get_sales_quality_action_counts(filters)

	items: list[dict[str, Any]] = []
	retention_count = flt(opportunity.get("retention_follow_up"))
	growth_count = flt(opportunity.get("growth_opportunities"))
	high_reduction_count = flt(quality.get("high_reduction_invoices"))
	low_margin_count = flt(quality.get("low_or_negative_margin_invoices"))

	if retention_count > 0:
		items.append(
			_action_item(
				source="r11_customer_opportunity",
				kind="customer_retention_follow_up",
				label=_("Customers need retention follow-up"),
				value=retention_count,
				severity="warning",
				route="/app/customer-opportunity-intelligence",
				target="customer-opportunity-intelligence",
				fingerprint_scope=period_scope,
			)
		)
	if growth_count > 0:
		items.append(
			_action_item(
				source="r11_customer_opportunity",
				kind="customer_growth_opportunity",
				label=_("Customer growth opportunities are available"),
				value=growth_count,
				severity="info",
				route="/app/customer-opportunity-intelligence",
				target="customer-opportunity-intelligence",
				fingerprint_scope=period_scope,
			)
		)
	if high_reduction_count > 0:
		items.append(
			_action_item(
				source="r11_sales_quality",
				kind="high_price_reduction",
				label=_("Sales invoices have high recorded price reduction"),
				value=high_reduction_count,
				severity="warning",
				route="/app/sales-quality-intelligence",
				target="sales-quality-intelligence",
				fingerprint_scope=period_scope,
			)
		)
	if low_margin_count > 0:
		items.append(
			_action_item(
				source="r11_sales_quality",
				kind="low_or_negative_transactional_margin",
				label=_("Sales invoices have low or negative transactional margin"),
				value=low_margin_count,
				severity="warning",
				route="/app/sales-quality-intelligence",
				target="sales-quality-intelligence",
				fingerprint_scope=period_scope,
			)
		)

	return {
		"items": items,
		"metadata": {
			"read_only": True,
			"customer_signal_truth": opportunity.get("metadata") or {},
			"sales_quality_truth": quality.get("metadata") or {},
			"receivables_excluded": True,
			"receivables_reason": "Overdue receivables remain owned by the existing Action Centre receivables provider.",
			"basket_affinity_actionable": False,
			"basket_affinity_reason": "Product affinity is insight-only and does not by itself represent an exception or required follow-up.",
			"cost_visibility_applied": bool(quality.get("show_costs")),
			"follow_up_scope": period_scope,
			"lightweight_summary": True,
		},
	}


def _period_scope(filters: frappe._dict) -> str:
	return "period:{0}:{1}".format(
		str(filters.get("from_date") or "").strip(),
		str(filters.get("to_date") or "").strip(),
	)


def _action_item(
	*,
	source: str,
	kind: str,
	label: str,
	value: float,
	severity: str,
	route: str,
	target: str,
	fingerprint_scope: str,
) -> dict[str, Any]:
	return {
		"source": source,
		"label": label,
		"value": int(value) if float(value).is_integer() else value,
		"datatype": "Int",
		"severity": severity,
		"route": route,
		"time_basis": "period",
		"kind": kind,
		"semantic_key": kind,
		"fingerprint_scope": fingerprint_scope,
		"target_type": "Page",
		"target": target,
		"open_mode": "same_tab",
	}
