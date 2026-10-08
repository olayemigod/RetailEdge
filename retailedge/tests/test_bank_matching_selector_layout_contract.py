from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
SELECTOR_CSS = APP_ROOT / "public/css/bank_matching_selector_layout.css"


def test_bank_matching_page_loads_selector_layout_stylesheet():
	text = PAGE_JS.read_text(encoding="utf-8")

	assert 'bank_matching_selector_layout.css' in text
	assert 'loadVersionedStylesheet(SELECTOR_LAYOUT_CSS, "selector-layout")' in text
	assert 'const STYLE_VERSION = "20261005-4";' in text


def test_selector_bars_are_compact_inline_groups_on_wide_screens():
	text = SELECTOR_CSS.read_text(encoding="utf-8")

	for expected in (
		'.retailedge-bank-layout .edge-action-bar {',
		'display: inline-flex !important;',
		'flex-wrap: nowrap !important;',
		'width: auto !important;',
		'padding: .32rem .4rem !important;',
		'font-size: .76rem !important;',
		'.retailedge-bank-layout .edge-action-bar [class*="actions"] {',
		'gap: .22rem !important;',
		'.retailedge-bank-layout .edge-action-bar .edge-button {',
		'min-height: 1.8rem !important;',
		'padding: .3rem .46rem !important;',
	):
		assert expected in text


def test_selector_bars_wrap_only_at_small_screen_breakpoints():
	text = SELECTOR_CSS.read_text(encoding="utf-8")

	assert '@media (max-width: 900px)' in text
	assert '@media (max-width: 700px)' in text
	assert 'width: 100% !important;' in text
