from __future__ import annotations

import ast
import json
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
EDGESUITE = APP_ROOT / "edgesuite_ui.py"
SUPPLIER_REVIEW = APP_ROOT / "supplier_document_review.py"
SUPPLIER_REVIEW_PAGE = (
	APP_ROOT
	/ "retailedge"
	/ "page"
	/ "supplier_document_review"
	/ "supplier_document_review.json"
)
CUSTOMER_360 = APP_ROOT / "public" / "js" / "customer_360" / "Customer360.vue"

AUTHORITATIVE_SUPPLIER_REVIEW_ROLES = {
	"System Manager",
	"Purchase Manager",
	"Purchase User",
	"Accounts Manager",
	"Accounts User",
}
RETAILEDGE_GENERAL_ROLES = {
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}


def _assigned_set(path: Path, name: str) -> set[str]:
	tree = ast.parse(path.read_text(encoding="utf-8"))
	for node in tree.body:
		if not isinstance(node, ast.Assign):
			continue
		if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
			continue
		value = ast.literal_eval(node.value)
		return set(value)
	raise AssertionError(f"{name} was not found in {path}")


def test_supplier_document_review_remains_governed_by_native_purchase_accounts_authority():
	"""RetailEdge persona labels must not silently grant buying/accounting review authority."""
	page = json.loads(SUPPLIER_REVIEW_PAGE.read_text(encoding="utf-8"))
	page_roles = {row["role"] for row in page.get("roles") or []}
	navigation_roles = _assigned_set(EDGESUITE, "SUPPLIER_DOCUMENT_REVIEW_ROLES")
	action_roles = _assigned_set(SUPPLIER_REVIEW, "INTERNAL_REVIEW_ROLES")

	assert page_roles == AUTHORITATIVE_SUPPLIER_REVIEW_ROLES
	assert navigation_roles == AUTHORITATIVE_SUPPLIER_REVIEW_ROLES
	assert action_roles == AUTHORITATIVE_SUPPLIER_REVIEW_ROLES
	assert not page_roles.intersection(RETAILEDGE_GENERAL_ROLES)
	assert not navigation_roles.intersection(RETAILEDGE_GENERAL_ROLES)
	assert not action_roles.intersection(RETAILEDGE_GENERAL_ROLES)


def test_customer_360_filter_layout_is_not_the_edge_filter_bar_failure_mode():
	"""Customer 360 owns a page-width responsive grid and should stay QA-only unless reproduced."""
	text = CUSTOMER_360.read_text(encoding="utf-8")

	assert "<EdgeFilterBar" not in text
	assert 'class="customer-360-filter-grid"' in text
	assert ".customer-360-filter-grid { display: grid;" in text
	assert "grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));" in text
	assert ".customer-360-period-filter { min-width: 0; width: 100%; }" in text
