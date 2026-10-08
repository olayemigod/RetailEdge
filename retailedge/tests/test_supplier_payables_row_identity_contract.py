from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "public/js/purchase_reporting.bundle.js"


def test_invoice_level_purchase_reports_use_invoice_identity_before_rendering():
	text = BUNDLE.read_text(encoding="utf-8")

	assert 'const INVOICE_LEVEL_REPORT_KEYS = new Set(["purchase-register", "supplier-payables"]);' in text
	assert 'function withInvoiceRowIdentity(result = {}, reportKey = "")' in text
	assert 'group_key: row.group_key || row.invoice || ""' in text
	assert 'const identifiedResult = withInvoiceRowIdentity(rawResult, config.key);' in text
	assert 'config.key === "purchase-register" ? await enrichPurchaseRegister(identifiedResult) : identifiedResult' in text


def test_grouped_purchase_reports_keep_their_existing_group_identity():
	text = BUNDLE.read_text(encoding="utf-8")

	assert 'if (!INVOICE_LEVEL_REPORT_KEYS.has(reportKey)) return result;' in text
