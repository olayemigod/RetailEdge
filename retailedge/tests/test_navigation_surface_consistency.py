from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
	return (ROOT / relative).read_text(encoding="utf-8")


def test_reports_centre_uses_final_permission_filtered_navigation_context():
	source = read("public/js/reports_centre/ReportsCentre.vue")
	assert "window.retailedgeGetBusinessHubContext" in source
	assert "retailedge.navigation_consolidation.get_retailedge_business_hub_context" in source
	assert "this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || [])" in source
	assert "this.menuItems = this.mapNavigationGroups(result.navigation_groups || [])" not in source


def test_professional_selling_cashier_page_access_is_declared_and_upgrade_reconciled():
	page = json.loads(read("retailedge/page/professional_selling/professional_selling.json"))
	roles = {row.get("role") for row in page.get("roles") or []}
	assert {"RetailEdgeCashier", "RetailEdge Cashier"}.issubset(roles)

	patch = read("patches/ensure_retailedge_cashier_professional_selling_access.py")
	assert 'PROFESSIONAL_SELLING_PAGE = "professional-selling"' in patch
	assert '"RetailEdgeCashier"' in patch
	assert '"RetailEdge Cashier"' in patch
	assert 'page.append("roles", {"role": role})' in patch

	patches = read("patches.txt")
	assert "retailedge.patches.ensure_retailedge_cashier_professional_selling_access" in patches
