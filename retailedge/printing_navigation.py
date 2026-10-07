from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe

from retailedge.master_experience import (
	get_retailedge_business_hub_context as _get_retailedge_business_hub_context,
)

PRINTING_PAGE = "edge-printing"
PRINTING_LABEL = "Devices & Printing"


def normalize_printing_navigation(context: dict[str, Any] | None) -> dict[str, Any]:
	"""Return Business Hub context with shared printing exposed as an internal Page.

	Older printing adoption code carried Product/Company/Branch through an `/app/...?...`
	URL menu target. Frappe v16 can treat that query string as part of the Page name and
	URL items can also be rendered as external/new-tab links by shared navigation.

	The shared printing Page now resolves active product/company/branch identity itself,
	so normal navigation must remain a canonical Page route with no query string.
	"""
	result = deepcopy(context or {})
	for group in result.get("navigation_groups") or []:
		for item in group.get("items") or []:
			target = str(item.get("target") or "").strip()
			label = str(item.get("label") or "").strip()
			is_printing_target = (
				label == PRINTING_LABEL
				or target == PRINTING_PAGE
				or target.startswith("/app/edge-printing?")
				or target.startswith("/desk/edge-printing?")
			)
			if not is_printing_target:
				continue
			item["target_type"] = "Page"
			item["target"] = PRINTING_PAGE
	return result


@frappe.whitelist()
def get_retailedge_business_hub_context() -> dict[str, Any]:
	return normalize_printing_navigation(_get_retailedge_business_hub_context())
