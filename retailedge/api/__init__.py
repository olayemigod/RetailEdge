"""Permission-aware RetailEdge API providers for product-owned EdgeSuite UI pages.

This package coexists with the legacy ``retailedge.api`` module contract. Keep
established public helpers available here while product-specific APIs move into
submodules.
"""

from __future__ import annotations

import frappe

from retailedge.cost_fields import COST_FIELDNAMES, COST_FIELD_LABEL_KEYWORDS
from retailedge.cost_visibility import should_hide_cost_price as _should_hide_cost_price


@frappe.whitelist()
def get_cost_visibility_rules() -> dict:
	"""Return the existing cost-price masking contract without affecting selling rates."""
	if not _should_hide_cost_price():
		return {
			"hide_cost_price": 0,
			"fieldnames": [],
			"label_keywords": [],
		}

	return {
		"hide_cost_price": 1,
		"fieldnames": sorted(COST_FIELDNAMES),
		"label_keywords": COST_FIELD_LABEL_KEYWORDS[:],
	}
