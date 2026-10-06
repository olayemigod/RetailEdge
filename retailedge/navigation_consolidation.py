from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe

from retailedge.master_experience import (
	get_retailedge_business_hub_context as _get_master_business_hub_context,
)


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


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	"""Return final RetailEdge navigation with consolidated shift review surfaces."""
	context = deepcopy(_get_master_business_hub_context() or {})
	navigation_groups = context.get("navigation_groups") or []
	_consolidate_shift_review_navigation(navigation_groups)
	context["navigation_groups"] = navigation_groups
	return context
