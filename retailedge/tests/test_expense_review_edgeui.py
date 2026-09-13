from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = APP_ROOT / "expense_review.py"
AUDIT_ENGINE = APP_ROOT / "cashier_expense_audit.py"
BUNDLE = APP_ROOT / "public" / "js" / "expense_review.bundle.js"
COMPONENT = APP_ROOT / "public" / "js" / "expense_review" / "ExpenseReviewReport.vue"
PAGE_JS = APP_ROOT / "retailedge" / "page" / "expense_review" / "expense_review.js"
PAGE_JSON = APP_ROOT / "retailedge" / "page" / "expense_review" / "expense_review.json"
NAVIGATION = APP_ROOT / "edgesuite_ui.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_expense_review_adapter_reuses_existing_review_engine_with_bounded_rows():
	source = _read(ADAPTER)
	for expected in (
		"MAX_REVIEW_ROWS = 5000",
		"get_cashier_expenses_for_daily_audit",
		"limit_page_length=MAX_REVIEW_ROWS + 1",
		"build_review_summary",
		"user_is_reviewer",
		"mark_cashier_expense_included_for_daily_audit",
		"mark_cashier_expense_excluded_from_daily_audit",
		"mark_cashier_expense_needs_clarification",
	):
		assert expected in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit()" not in source


def test_existing_cashier_expense_audit_engine_supports_optional_bounded_reads_without_changing_default():
	source = _read(AUDIT_ENGINE)
	assert "def get_cashier_expenses_for_daily_audit(filters=None, limit_page_length=0):" in source
	assert "limit_page_length=limit_page_length" in source


def test_expense_review_uses_edgesuite_report_shell_and_existing_review_actions():
	component = _read(COMPONENT)
	bundle = _read(BUNDLE)
	for expected in (
		"EdgeReportShell",
		"EdgeLinkField",
		"review_action",
		"frappe.prompt",
		"retailedge.expense_review.apply_expense_review_action",
		"Read-only review access",
	):
		assert expected in component
	assert "<table" not in component.lower()
	assert "createBoundedPaginatedReportProvider" in bundle
	assert "maxDatasetRows: 5000" in bundle
	assert "retailedge.reporting_actions.get_report_export_data" in bundle
	assert 'report_key: REPORT_KEY' in bundle


def test_expense_review_page_is_available_as_preview_but_not_promoted_to_primary_navigation():
	page_js = _read(PAGE_JS)
	page_json = _read(PAGE_JSON)
	navigation = _read(NAVIGATION)
	assert 'const PAGE_ROUTE = "expense-review"' in page_js
	assert 'expense_review.bundle.js' in page_js
	assert 'edgeui.bundle.js' in page_js
	assert '"page_name": "expense-review"' in page_json
	assert '"RetailEdge Cashier Expense Review"' in navigation
	assert '"target": "expense-review"' not in navigation
