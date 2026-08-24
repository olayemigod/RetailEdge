from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.customer_opportunity_intelligence import get_customer_opportunity_intelligence
from retailedge.sales_quality_intelligence import get_sales_quality_intelligence


DEFAULT_CHANGE_THRESHOLD_PERCENT = 25.0
DEFAULT_HIGH_REDUCTION_PERCENT = 10.0
DEFAULT_LOW_MARGIN_PERCENT = 10.0


def get_customer_sales_action_summary(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	"""Return aggregate R11 actions without creating a parallel customer/sales truth store."""
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

	opportunity = get_customer_opportunity_intelligence(filters)
	quality = get_sales_quality_intelligence(filters, page=1, page_size=1)

	items: list[dict[str, Any]] = []
	retention_count = _summary_value(opportunity, "Retention Follow-up")
	growth_count = _summary_value(opportunity, "Growth Opportunities")
	high_reduction_count = _summary_value(quality, "High Reduction Invoices")
	low_margin_count = _summary_value(quality, "Low / Negative Margin Invoices")

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
		},
	}


def _summary_value(payload: dict[str, Any], label: str) -> float:
	for card in payload.get("summary") or []:
		if str(card.get("label") or "").strip() == label:
			return flt(card.get("value"))
	return 0.0


def _action_item(
	*,
	source: str,
	kind: str,
	label: str,
	value: float,
	severity: str,
	route: str,
	target: str,
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
		"target_type": "Page",
		"target": target,
		"open_mode": "same_tab",
	}
