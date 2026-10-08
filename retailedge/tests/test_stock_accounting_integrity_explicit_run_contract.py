from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "public/js/stock_accounting_integrity/StockAccountingIntegrityReport.vue"
BACKEND = ROOT / "stock_accounting_integrity.py"


def test_integrity_page_loads_controls_without_auto_running_native_comparison():
	text = REPORT.read_text(encoding="utf-8")

	assert "if (this.filters.company) await this.fetchData();" not in text
	assert '@click="applyFilters"' in text
	assert '{{ loading ? "Checking…" : "Apply / Refresh" }}' in text
	assert "hasRun: false" in text
	assert "this.hasRun = true;" in text
	assert "Choose a review scope" in text
	assert "This control does not run automatically." in text


def test_scope_changes_clear_and_invalidate_stale_integrity_results():
	text = REPORT.read_text(encoding="utf-8")

	assert "resetReviewResults()" in text
	for contract in (
		"loadToken: 0",
		"this.loadToken += 1;",
		"this.loading = false;",
		"this.hasRun = false;",
		"this.rows = [];",
		"this.columns = [];",
		"this.summary = [];",
		"this.pagination = {};",
		"this.scan = {};",
		"this.scope = {};",
		"const requestToken = ++this.loadToken;",
		"if (requestToken === this.loadToken) this.loading = false;",
	):
		assert contract in text
	assert text.count("this.resetReviewResults();") >= 5
	assert text.count("if (requestToken !== this.loadToken) return;") >= 2


def test_native_erpnext_comparison_remains_the_server_source_of_truth():
	text = BACKEND.read_text(encoding="utf-8")

	assert "stock_and_account_value_comparison as native_report" in text
	assert "columns, rows = native_report.execute(filters)" in text
	assert '"read_only": 1' in text
