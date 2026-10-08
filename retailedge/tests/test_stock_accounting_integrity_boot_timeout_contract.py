from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE_LOADER = ROOT / "retailedge/page/stock_accounting_integrity/stock_accounting_integrity.js"


def test_stock_accounting_integrity_asset_loading_is_bounded():
	text = PAGE_LOADER.read_text(encoding="utf-8")

	assert "const LOAD_TIMEOUT_MS = 15000;" in text
	assert "const FRAPPE_REQUIRE_POLL_MS = 50;" in text
	assert "const deadlineTimer = window.setTimeout(" in text
	assert "Timed out waiting for the Frappe asset loader while loading {0}" in text
	assert "window.clearTimeout(deadlineTimer);" in text
	assert "pollTimer = window.setTimeout(attemptRequire, FRAPPE_REQUIRE_POLL_MS);" in text
	assert "const pending = window.frappe.require(assetName, finish);" in text
	assert 'pending.then(finish).catch(fail)' in text


def test_stock_accounting_integrity_boot_failure_clears_spinner_and_renders_error():
	text = PAGE_LOADER.read_text(encoding="utf-8")

	catch_block = text.split("} catch (error) {", 1)[1]
	assert "bootLoading.remove();" in catch_block
	assert "renderLoadError(wrapper, error);" in catch_block
