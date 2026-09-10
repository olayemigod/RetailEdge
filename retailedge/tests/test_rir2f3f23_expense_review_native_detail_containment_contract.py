from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/expense_review/ExpenseReviewReport.vue"
DOC = ROOT.parent / "docs/rir2f3f23_expense_review_native_detail_containment.md"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_expense_review_uses_final_access_context_fail_closed():
	source = _source()
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);" in source
	assert "retailedge.master_experience.get_retailedge_business_hub_context" in source
	assert "retailedge.edgesuite_ui.get_retailedge_business_hub_context" not in source


def test_review_action_remains_edgesuite_owned():
	source = _source()
	assert 'column.fieldname === "review_action" ? this.canReview' in source
	assert 'if (column.fieldname === "review_action") { this.openReviewDialog(row); return; }' in source
	assert "retailedge.expense_review.apply_expense_review_action" in source
	assert "if (!this.canReview)" in source


def test_native_detail_columns_require_native_desk():
	source = _source()
	assert 'this.canUseNativeDesk && ["name", "cashier", "expense_category"].includes(column.fieldname)' in source
	assert "if (!this.canUseNativeDesk) return;" in source
	assert 'frappe.set_route("Form", "RetailEdge Cashier Expense", value)' in source
	assert 'frappe.set_route("Form", "User", value)' in source
	assert 'frappe.set_route("Form", "RetailEdge Expense Category", value)' in source


def test_generic_native_navigation_is_defensively_gated():
	source = _source()
	assert 'if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;' in source


def test_slice_changes_no_expense_review_backend_semantics():
	doc = DOC.read_text(encoding="utf-8")
	assert "No Expense Review backend file is changed" in doc
	assert "review mutation endpoints remain unchanged" in doc
	assert "B4B10 read-scope contract remains unchanged" in doc
