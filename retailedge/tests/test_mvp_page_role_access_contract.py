from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _roles(relative_path: str) -> set[str]:
	payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
	return {row["role"] for row in payload.get("roles") or []}


def test_business_hub_accepts_canonical_retailedge_personas():
	roles = _roles("retailedge/page/retailedge_business_hub/retailedge_business_hub.json")
	for role in ("RetailEdgeManager", "RetailEdgeBranchManager", "RetailEdgeCashier"):
		assert role in roles


def test_banking_pages_accept_canonical_manager_personas():
	for page in ("banking_readiness", "bank_matching_reconciliation"):
		roles = _roles(f"retailedge/page/{page}/{page}.json")
		for role in ("System Manager", "RetailEdgeManager", "RetailEdgeBranchManager"):
			assert role in roles


def test_role_normalization_does_not_depend_on_new_spaced_cashier_alias():
	roles = _roles("retailedge/page/retailedge_business_hub/retailedge_business_hub.json")
	assert "RetailEdgeCashier" in roles
	setup_roles = (ROOT / "setup_roles.py").read_text(encoding="utf-8")
	assert '"RetailEdgeCashier",' in setup_roles
	assert '"RetailEdgeCashier": (' not in setup_roles
