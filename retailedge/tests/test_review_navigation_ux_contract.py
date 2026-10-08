from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANAGED_REVIEW = ROOT / "public/js/managed_review_reports/ManagedReviewReport.vue"
REPORTS_CENTRE = ROOT / "public/js/reports_centre/ReportsCentre.vue"


def test_unmatched_bank_reviews_expose_inline_apply_filters_without_backend_contract_change():
	text = MANAGED_REVIEW.read_text(encoding="utf-8")

	assert 'const INLINE_APPLY_FILTER_SURFACES = new Set(["unmatched-bank-payments", "unmatched-bank-transactions"]);' in text
	assert 'v-if="showInlineApplyFilters" class="managed-filter-action"' in text
	assert '{{ loading ? "Applying…" : "Apply Filters" }}' in text
	assert 'showInlineApplyFilters() { return INLINE_APPLY_FILTER_SURFACES.has(this.surfaceKey); }' in text
	assert 'callMethod("retailedge.managed_review_reports.search_review_report_options"' in text
	assert "cashier: this.filters.cashier" not in text


def test_reports_centre_opens_sales_forecast_in_a_new_tab_only():
	text = REPORTS_CENTRE.read_text(encoding="utf-8")

	assert 'const NEW_TAB_PAGE_TARGETS = new Set(["sales-forecast"]);' in text
	assert 'if (NEW_TAB_PAGE_TARGETS.has(item.target)) {' in text
	assert 'window.open(route, "_blank", "noopener,noreferrer");' in text
	new_tab_block = text.split('if (NEW_TAB_PAGE_TARGETS.has(item.target)) {', 1)[1].split('return;', 1)[0]
	assert "retailedgeSetReportRouteHandoff" not in new_tab_block
	assert "frappe.set_route" not in new_tab_block
	assert "frappe.set_route(item.target);" in text
