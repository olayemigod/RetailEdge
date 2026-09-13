from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master_experience.py"
REVIEW = ROOT / "public/js/expense_review/ExpenseReviewReport.vue"
DOC = ROOT.parent / "docs/rir2f3f25_expense_edgesuite_ownership_correction.md"


def test_final_navigation_promotes_expense_register_over_cashier_expense_doctype():
	source = MASTER.read_text(encoding="utf-8")
	assert 'EXPENSE_REGISTER_PAGE_TARGET = "expense-register"' in source
	assert 'CASHIER_EXPENSE_NATIVE_PEER_DOCTYPE = "RetailEdge Cashier Expense"' in source
	assert "def _promote_cashier_expense_ownership" in source
	assert "_promote_cashier_expense_ownership(navigation_groups)" in source
	assert 'feature_flags["cashier_expense_ownership"] = "edgesuite_expense_register"' in source


def test_expense_review_routes_retailedge_owned_entities_to_edgesuite():
	source = REVIEW.read_text(encoding="utf-8")
	assert 'frappe.set_route("expense-register")' in source
	assert 'frappe.set_route("retailedge-setup")' in source
	assert 'frappe.set_route("Form", "RetailEdge Cashier Expense", value)' not in source
	assert 'frappe.set_route("Form", "RetailEdge Expense Category", value)' not in source


def test_only_user_reference_remains_native_advanced():
	source = REVIEW.read_text(encoding="utf-8")
	assert 'if (column.fieldname === "cashier" && this.canUseNativeDesk) frappe.set_route("Form", "User", value);' in source


def test_contract_supersedes_only_wrong_f3f23_routing_classification():
	doc = DOC.read_text(encoding="utf-8")
	assert "supersedes the F3F23 routing classification" in doc
	assert "does not change Cashier Expense accounting, posting, review, or Branch scope" in doc
