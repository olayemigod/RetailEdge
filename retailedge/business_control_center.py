from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.action_center import get_action_center_data
from retailedge.action_follow_up import decorate_action_items
from retailedge.control_early_warning import get_control_early_warning

_DUPLICATE_WARNING_FAMILIES = {"Collections", "Supplier Obligations"}


@frappe.whitelist()
def get_business_control_center(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	resolved = _coerce_filters(filters)
	action_center = get_action_center_data(resolved)
	warnings = get_control_early_warning(resolved)
	payload = _build_business_control_center(action_center=action_center, warnings=warnings)
	filters_out = payload.get("filters") or {}
	items = decorate_action_items(
		payload.get("items") or [],
		company=str(filters_out.get("company") or ""),
		branch=str(filters_out.get("branch") or ""),
	)
	for item in items:
		item["follow_up_supported"] = True
	items.sort(key=_business_control_sort_key)
	payload["items"] = items
	payload["metadata"]["follow_up_contract"] = (
		"All visible Business Control Centre items use the existing RetailEdge Action Follow Up store. "
		"Writes must re-resolve the fingerprint against this same permission-aware Business Control Centre scope before persistence."
	)
	return payload


def _build_business_control_center(
	*,
	action_center: dict[str, Any],
	warnings: dict[str, Any],
) -> dict[str, Any]:
	existing = [dict(item) for item in action_center.get("items") or []]
	r9_items = [
		_warning_as_control_item(item)
		for item in warnings.get("warnings") or []
		if str(item.get("family") or "") not in _DUPLICATE_WARNING_FAMILIES
	]
	combined = _dedupe_control_items([*existing, *r9_items])
	combined.sort(key=_business_control_sort_key)

	return {
		"title": _("Business Control Centre"),
		"filters": action_center.get("filters") or {},
		"summary": {
			"critical": sum(1 for item in combined if item.get("severity") == "danger"),
			"warning": sum(1 for item in combined if item.get("severity") == "warning"),
			"total": len(combined),
		},
		"items": combined,
		"action_center": {
			"summary": action_center.get("summary") or [],
			"sources": action_center.get("sources") or {},
			"metadata": action_center.get("metadata") or {},
		},
		"early_warning": {
			"critical_count": warnings.get("critical_count") or 0,
			"warning_count": warnings.get("warning_count") or 0,
			"profitability_trend": warnings.get("profitability_trend") or {},
			"metadata": warnings.get("metadata") or {},
		},
		"metadata": {
			"composition": "existing_action_center_plus_r9_early_warning",
			"duplicate_domains": "Collections and Supplier Obligations remain owned by the existing Action Centre receivables/payables sources and are not duplicated from R9 early warning.",
			"follow_up_contract": "R9-only warnings are read-only in the pure composition helper; the runtime endpoint decorates all visible items through the existing Action Follow Up store after permission-aware resolution.",
			"accounting_truth": "Business Control Centre composes existing ERPNext/RetailEdge reporting and control engines; it does not create a ledger or mutate accounting documents.",
		},
	}


def _warning_as_control_item(item: dict[str, Any]) -> dict[str, Any]:
	family = str(item.get("family") or _("Business Control"))
	label = str(item.get("label") or _("Business control warning"))
	severity = "danger" if str(item.get("severity") or "") == "critical" else "warning"
	route = str(item.get("route") or "")
	return {
		"source": "r9_early_warning",
		"family": family,
		"label": label,
		"value": item.get("value"),
		"datatype": item.get("datatype") or "Data",
		"severity": severity,
		"route": route,
		"time_basis": "control",
		"kind": f"r9_{_slug(family)}",
		"semantic_key": f"r9_{_slug(family)}_{_slug(label)}",
		"target_type": "Report" if "/query-report/" in route else "Page",
		"target": route,
		"open_mode": "new_tab" if "/query-report/" in route else "same_tab",
		"follow_up_supported": False,
		"priority_reason": "Critical exception" if severity == "danger" else "Needs attention",
	}


def _dedupe_control_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	seen: set[tuple[str, str]] = set()
	result: list[dict[str, Any]] = []
	for item in items:
		key = (
			str(item.get("source") or ""),
			str(item.get("semantic_key") or item.get("kind") or item.get("label") or ""),
		)
		if key in seen:
			continue
		seen.add(key)
		result.append(item)
	return result


def _business_control_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
	severity_rank = {"danger": 0, "warning": 1, "info": 2}
	follow_up = item.get("follow_up") or {}
	return (
		severity_rank.get(str(item.get("severity") or ""), 9),
		0 if follow_up.get("is_due") else 1,
		str(item.get("source") or ""),
		str(item.get("family") or ""),
		str(item.get("label") or ""),
	)


def _slug(value: str) -> str:
	return "_".join(part for part in "".join(character.lower() if character.isalnum() else " " for character in value).split() if part)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
