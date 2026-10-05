from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
SELECTOR_CSS = APP_ROOT / "public/css/bank_matching_selector_layout.css"


def test_bank_matching_page_loads_selector_layout_stylesheet():
	text = PAGE_JS.read_text(encoding="utf-8")

	assert 'bank_matching_selector_layout.css' in text
	assert 'loadVersionedStylesheet(SELECTOR_LAYOUT_CSS, "selector-layout")' in text


def test_selector_bar_reserves_space_for_label_and_wraps_actions():
	text = SELECTOR_CSS.read_text(encoding="utf-8")

	for expected in (
		'.retailedge-bank-layout .edge-action-bar {',
		'display: flex !important;',
		'flex-wrap: wrap !important;',
		'column-gap: .75rem !important;',
		'.retailedge-bank-layout .edge-action-bar > :first-child {',
		'white-space: nowrap;',
		'.retailedge-bank-layout .edge-action-bar [class*="actions"] {',
		'gap: .5rem !important;',
	):
		assert expected in text
