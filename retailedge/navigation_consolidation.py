from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe

from retailedge.master_experience import (
	get_retailedge_business_hub_context as _get_master_business_hub_context,
)
from retailedge.printing_navigation import normalize_printing_navigation


SHIFT_RECONCILIATION_TARGET = "pos-closing-variance"
SHIFT_REVIEW_GROUP_KEYS = {
	"review-approvals",
	"operations-review",
}
LEGACY_SHIFT_REVIEW_TARGETS = {
	"cash-shift-verification",
	"daily-sales-audit-register",
}
PRESERVED_SHIFT_WORKFLOW_TARGETS = {
	"daily-sales-audit",
	"expense-review",
}
SALES_GROUP_KEY = "sales"
MAKE_SALE_TARGET = "make-sale"
PROFESSIONAL_SELLING_TARGET = "professional-selling"
LEGACY_SALES_FORECAST_TARGET = "sales-forecast"
RETAILEDGE_SALES_FORECAST_TARGET = "retailedge-sales-forecast"


def _consolidate_shift_review_navigation(navigation_groups: list[dict[str, Any]]) -> None:
	"""Expose one clear shift-control front door without deleting review workflows.

	The final Business Hub context is already permission-filtered before this helper runs.
	Master Experience presents the legacy ``review-approvals`` bucket to users as
	``operations-review``, so both keys are accepted to keep the helper safe for the
	final customer-facing context and for older callers. Shift Reconciliation is only
	promoted when the current user was already permitted to see the existing POS Closing
	Variance page. Read-only/detail duplicates leave everyday navigation, while Daily
	Sales Audit and Cashier Expense Review remain available until their mutation workflows
	are deliberately absorbed into the canonical surface. All legacy routes remain
	directly routable for backward compatibility.
	"""
	for group in navigation_groups:
		if group.get("key") not in SHIFT_REVIEW_GROUP_KEYS:
			continue

		items = list(group.get("items") or [])
		canonical_item = next(
			(item for item in items if item.get("target") == SHIFT_RECONCILIATION_TARGET),
			None,
		)
		if canonical_item is None:
			# Preserve the permission-filtered fallback exactly as received. A user who
			# cannot open Shift Reconciliation must not lose an older permitted review
			# route merely because the canonical page is unavailable to that role.
			continue

		consolidated = deepcopy(canonical_item)
		consolidated["label"] = "Shift Reconciliation"
		consolidated["icon"] = "check-circle"

		cleaned = [
			item
			for item in items
			if item.get("target") not in LEGACY_SHIFT_REVIEW_TARGETS
			and item.get("target") != SHIFT_RECONCILIATION_TARGET
		]

		# Keep the consolidated cash-control entry close to Action Centre / other
		# operational review work rather than among low-level historical reports.
		insert_at = next(
			(
				index + 1
				for index, item in enumerate(cleaned)
				if item.get("target") == "action-center"
			),
			0,
		)
		cleaned.insert(insert_at, consolidated)
		group["items"] = cleaned
		return


def _prioritize_sales_navigation(navigation_groups: list[dict[str, Any]]) -> None:
	"""Keep Make Sale as the first visible Sales operation when it is permitted.

	Master Experience promotes Transaction Workspace, Make Sale and Professional Selling
	before task-frequency reclassification. Transaction Workspace is then intentionally
	hidden as a duplicate, which can leave Professional Selling ahead of Make Sale because
	both promotions insert beside the same temporary anchor. Final composition owns the
	customer-facing order, so normalize only the already-permitted Sales items here.
	"""
	for group in navigation_groups:
		if group.get("key") != SALES_GROUP_KEY:
			continue

		items = list(group.get("items") or [])
		make_sale = next((item for item in items if item.get("target") == MAKE_SALE_TARGET), None)
		if make_sale is None:
			return

		group["items"] = [
			make_sale,
			*[
				item
				for item in items
				if item is not make_sale
			],
		]
		return


def _normalize_sales_forecast_route(navigation_groups: list[dict[str, Any]]) -> None:
	"""Use the RetailEdge Page route without shadowing ERPNext's Sales Forecast DocType."""
	for group in navigation_groups:
		for item in group.get("items") or []:
			if item.get("target_type") == "Page" and item.get("target") == LEGACY_SALES_FORECAST_TARGET:
				item["target"] = RETAILEDGE_SALES_FORECAST_TARGET


def _load_master_context_quietly() -> dict[str, Any]:
	"""Build permission-aware navigation without leaking probe messages to Desk.

	The master context intentionally probes many native ERPNext destinations so an
	inaccessible target can be omitted. Frappe permission probes may append user-facing
	messages before returning False. Those probe messages are not workflow errors and
	must not become modal dialogs on unrelated RetailEdge pages.

	Exceptions still propagate; only message-log side effects from capability probes are
	restored to the caller's prior state.
	"""
	previous_messages = list(getattr(frappe.local, "message_log", []) or [])
	try:
		return deepcopy(_get_master_business_hub_context() or {})
	finally:
		frappe.local.message_log = previous_messages


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	"""Return final RetailEdge navigation with review, sales-order and printing governance composed."""
	context = _load_master_context_quietly()
	navigation_groups = context.get("navigation_groups") or []
	_consolidate_shift_review_navigation(navigation_groups)
	_prioritize_sales_navigation(navigation_groups)
	_normalize_sales_forecast_route(navigation_groups)
	context["navigation_groups"] = navigation_groups
	# Printing normalization is presentation/navigation-only. It runs last so the
	# final Business Hub keeps the current consolidated review and Sales ordering model
	# while shared Devices & Printing remains a queryless internal Page route.
	return normalize_printing_navigation(context)
