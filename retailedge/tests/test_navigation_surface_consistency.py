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


def test_cashier_selling_document_permissions_are_upgrade_reconciled():
	permission_patch = read("patches/ensure_retailedge_cashier_selling_document_permissions.py")
	for doctype in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
		assert f'"{doctype}"' in permission_patch
	for permission_type in ("read", "create", "write", "submit", "print"):
		assert f'"{permission_type}"' in permission_patch

	patches = read("patches.txt")
	assert "retailedge.patches.ensure_retailedge_cashier_selling_document_permissions" in patches


def test_cashier_selling_permissions_remain_outside_generic_accounting_authority():
	permission_patch = read("patches/ensure_retailedge_cashier_selling_document_permissions.py")
	assert '"Payment Entry"' not in permission_patch
	assert '"Journal Entry"' not in permission_patch
	assert '"Purchase Invoice"' not in permission_patch


def test_persisted_sales_pages_refresh_the_shared_navigation_snapshot_on_show():
	my_work = read("retailedge/page/cashier_my_work/cashier_my_work.js")
	professional_selling = read("retailedge/page/professional_selling/professional_selling.js")
	for source in (my_work, professional_selling):
		assert "__retailedgeBusinessHubContextCache = null" in source
		assert "__retailedgeBusinessHubContextRequest = null" in source

	assert "refreshMountedMyWork(wrapper)" in my_work
	assert 'CustomEvent("retailedge-professional-selling-page-show")' in professional_selling


def test_cross_route_browser_acceptance_is_part_of_the_exact_head_gate():
	workflow = read("../.github/workflows/browser-persona-smoke.yml")
	spec = read("../browser-tests/retailedge_cashier_sidebar_consistency.spec.cjs")
	assert "browser-tests/retailedge_cashier_sidebar_consistency.spec.cjs" in workflow
	assert 'openRoute(page, "cashier-my-work")' in spec
	assert 'openRoute(page, "professional-selling")' in spec
	assert 'getByText("Professional Selling", { exact: true })' in spec
	for label in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
		assert f'"{label}"' in spec
