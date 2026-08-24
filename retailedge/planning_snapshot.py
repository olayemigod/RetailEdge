from __future__ import annotations

from typing import Any

from frappe.utils import now_datetime

from retailedge.planning_intelligence import get_planning_intelligence

SNAPSHOT_VERSION = 1
SCORED_DOMAINS = ("sales", "cash", "expenses", "profitability")


def build_planning_snapshot(filters: dict[str, Any]) -> dict[str, Any]:
	"""Freeze the forecast/plan baseline used by later Forecast-vs-Actual scoring."""
	dataset = get_planning_intelligence(filters)
	domains: dict[str, Any] = {}
	for key in SCORED_DOMAINS:
		domain = dataset.get("domains", {}).get(key) or {}
		domains[key] = {
			"available": bool(domain.get("available")),
			"source": domain.get("source"),
			"future_rows": [
				{
					"period_start": str(row.get("period_start") or ""),
					"forecast": row.get("forecast"),
					"plan": row.get("plan"),
				}
				for row in domain.get("future_rows") or []
				if row.get("period_start")
			],
		}

	inventory = dataset.get("domains", {}).get("inventory") or {}
	inventory_risk_items = sorted({
		str(row.get("item_code") or "")
		for row in inventory.get("rows") or []
		if row.get("coverage_risk") and row.get("item_code")
	})
	domains["inventory"] = {
		"available": bool(inventory.get("available")),
		"at_risk_count": len(inventory_risk_items),
		"at_risk_items": inventory_risk_items,
		"snapshot_semantics": "Current projected stock and planned cumulative demand frozen when the scenario baseline is saved.",
	}

	return {
		"version": SNAPSHOT_VERSION,
		"generated_at": str(now_datetime()),
		"scope": dataset.get("scope") or {},
		"assumptions": dataset.get("assumptions") or {},
		"domains": domains,
		"metadata": {
			"immutable_baseline": True,
			"actuals_may_change": "Later posted or backdated ERPNext transactions may change Actual, but never rewrite this saved Forecast/Plan baseline.",
			"accounting_mutation": False,
		},
	}
