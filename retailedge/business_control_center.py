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
	# Action Centre is the canonical operational scope resolver. Reuse its resolved
	# Company/Branch/date scope so R9 warnings cannot silently widen a single-branch
	# user's blank Branch filter back to company scope.
	warning_filters = frappe._dict(action_center.get("filters") or resolved)
	warnings = _safe_early_warning(warning_filters)
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
		"Writes must re-resolve the fingerprint against the same permission-aware scope before persistence."
	)
	payload["metadata"]["scope_contract"] = (
		"R9 warnings reuse the Branch scope resolved by Action Centre; a blank client Branch cannot widen a branch-restricted user's scope."
	)
	return payload


def build_business_control_export_dataset(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	result = get_business_control_center(filters)
	rows: list[dict[str, Any]] = []
	for item in result.get("items") or []:
		follow_up = item.get("follow_up") or {}
		rows.append(
			{
				"severity": _("Critical") if item.get("severity") == "danger" else _("Needs Attention"),
				"family": item.get("family") or item.get("source") or "",
				"control": item.get("label") or "",
				"value": item.get("value"),
				"datatype": item.get("datatype") or "Data",
				"time_basis": _export_time_basis(item.get("time_basis")),
				"follow_up_status": follow_up.get("effective_status") or follow_up.get("status") or _("Open"),
				"assigned_to": follow_up.get("assigned_to") or "",
				"follow_up_on": follow_up.get("follow_up_on") or "",
				"route": item.get("route") or "",
			}
		)
	summary = result.get("summary") or {}
	return {
		"title": _("Business Control Centre"),
		"columns": [
			{"fieldname": "severity", "label": _("Priority"), "fieldtype": "Data", "width": 130},
			{"fieldname": "family", "label": _("Control Family"), "fieldtype": "Data", "width": 180},
			{"fieldname": "control", "label": _("Control"), "fieldtype": "Data", "width": 300},
			{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 150},
			{"fieldname": "time_basis", "label": _("Basis"), "fieldtype": "Data", "width": 140},
			{"fieldname": "follow_up_status", "label": _("Follow-up Status"), "fieldtype": "Data", "width": 150},
			{"fieldname": "assigned_to", "label": _("Assigned To"), "fieldtype": "Data", "width": 180},
			{"fieldname": "follow_up_on", "label": _("Follow Up On"), "fieldtype": "Datetime", "width": 170},
			{"fieldname": "route", "label": _("Workflow Route"), "fieldtype": "Data", "width": 260},
		],
		"rows": rows,
		"summary": [
			{"label": _("Critical"), "value": summary.get("critical") or 0, "datatype": "Int"},
			{"label": _("Needs Attention"), "value": summary.get("warning") or 0, "datatype": "Int"},
			{"label": _("Open Controls"), "value": summary.get("total") or 0, "datatype": "Int"},
		],
		"filters": result.get("filters") or {},
	}


def _safe_early_warning(filters: frappe._dict) -> dict[str, Any]:
	try:
		return get_control_early_warning(filters)
	except frappe.PermissionError:
		# Business Control Centre extends Action Centre; it must not revoke an
		# operator's existing Action Centre/follow-up access merely because that
		# operator is not entitled to owner-level R9 financial intelligence.
		return _unavailable_early_warning(
			_("Your permissions allow operational Action Centre controls but not owner-level financial intelligence."),
			permission_isolated=True,
		)
	except frappe.ValidationError as exc:
		# Bounded scans, unavailable accounting attribution, or a misconfigured
		# financial-intelligence source must not take down the canonical operational
		# Action Centre. Keep the source failure visible instead of fabricating data.
		return _unavailable_early_warning(str(exc) or _("R9 financial intelligence is temporarily unavailable for this scope."))


def _unavailable_early_warning(reason: str, *, permission_isolated: bool = False) -> dict[str, Any]:
	return {
		"available": False,
		"warnings": [],
		"critical_count": 0,
		"warning_count": 0,
		"profitability_trend": {},
		"liquidity": {},
		"budget_spend": {},
		"metadata": {
			"reason": reason,
			"permission_isolated": permission_isolated,
			"failure_isolated": True,
		},
	}


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
			"available": warnings.get("available", True),
			"critical_count": warnings.get("critical_count") or 0,
			"warning_count": warnings.get("warning_count") or 0,
			"profitability_trend": warnings.get("profitability_trend") or {},
			"liquidity": warnings.get("liquidity") or {},
			"budget_spend": warnings.get("budget_spend") or {},
			"metadata": warnings.get("metadata") or {},
		},
		"metadata": {
			"composition": "existing_action_center_plus_r9_early_warning",
			"duplicate_domains": "Collections and Supplier Obligations remain owned by the existing Action Centre receivables/payables sources and are not duplicated from R9 early warning.",
			"follow_up_contract": "R9-only warnings are read-only in the pure composition helper; the runtime endpoint decorates all visible items through the existing Action Follow Up store after permission-aware resolution.",
			"accounting_truth": "Business Control Centre composes existing ERPNext/RetailEdge reporting and control engines; it does not create a ledger or mutate accounting documents.",
			"financial_payload_contract": "Liquidity and budget/spend payloads already computed by R9 early warning are exposed for presentation without triggering duplicate financial queries.",
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


def _export_time_basis(value: Any) -> str:
	if value == "current":
		return _("Current Position")
	if value == "period":
		return _("Selected Period")
	return _("Control Signal")


def _slug(value: str) -> str:
	return "_".join(part for part in "".join(character.lower() if character.isalnum() else " " for character in value).split() if part)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	return frappe._dict(filters or {})
