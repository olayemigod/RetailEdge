from __future__ import annotations

from pathlib import Path

import frappe

from retailedge import cash_shift_verification as page

APP_ROOT = Path(__file__).resolve().parents[1]


def test_cash_shift_preview_uses_existing_report_engine_and_bounded_guard(monkeypatch):
	captured = {}

	def fake_get_data(filters, limit_page_length=0):
		captured["limit"] = limit_page_length
		return []

	monkeypatch.setattr(page, "get_data", fake_get_data)
	monkeypatch.setattr(frappe, "has_permission", lambda *args, **kwargs: True)
	result = page._build_dataset(frappe._dict(company="Test Company"))
	assert captured["limit"] == page.MAX_SHIFT_ROWS + 1
	assert result["rows"] == []
	assert result["scan"]["row_limit"] == 1000


def test_cash_shift_preview_source_preserves_legacy_report_and_shell_contract():
	backend = (APP_ROOT / "cash_shift_verification.py").read_text(encoding="utf-8")
	legacy = (APP_ROOT / "retailedge" / "report" / "retailedge_cash_shift_verification" / "retailedge_cash_shift_verification.py").read_text(encoding="utf-8")
	component = (APP_ROOT / "public" / "js" / "cash_shift_verification" / "CashShiftVerificationReport.vue").read_text(encoding="utf-8")
	bundle = (APP_ROOT / "public" / "js" / "cash_shift_verification.bundle.js").read_text(encoding="utf-8")
	assert "get_data" in backend and "get_report_summary" in backend
	assert "def get_data(filters, limit_page_length=0)" in legacy
	assert "EdgeReportShell" in component
	assert "createBoundedPaginatedReportProvider" in bundle
	assert "maxDatasetRows: 1000" in bundle
	assert "ignore_permissions" not in backend
