from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BANKING_LOADER = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"
BANKING_DARK_CSS = APP_ROOT / "public/css/bank_matching_dark_contrast.css"
READINESS_CSS = APP_ROOT / "retailedge/page/banking_readiness/banking_readiness.css"


class BankingDarkModeContractTests(unittest.TestCase):
	def test_bank_matching_loads_page_scoped_dark_contrast(self):
		loader = BANKING_LOADER.read_text(encoding="utf-8")
		css = BANKING_DARK_CSS.read_text(encoding="utf-8")

		self.assertIn("/assets/retailedge/css/bank_matching_dark_contrast.css", loader)
		self.assertIn('loadVersionedStylesheet(DARK_CONTRAST_CSS, "dark-contrast")', loader)
		self.assertIn('STYLE_VERSION = "20260827-5"', loader)
		self.assertIn(':root[data-edge-appearance="dark"] .retailedge-bank-layout', css)
		self.assertIn(":has(.retailedge-bank-layout)", css)
		self.assertIn(".layout-main-section", css)
		self.assertIn("var(--edge-color-surface-soft", css)
		self.assertIn(".retailedge-bank-reset-link", css)
		self.assertIn(".retailedge-bank-table .edge-link-button", css)
		self.assertIn(".retailedge-bank-sort", css)
		self.assertIn(".retailedge-bank-sort.is-active", css)
		self.assertIn("tbody tr:hover > *", css)
		self.assertIn("tbody tr:focus-within > *", css)
		self.assertIn("--bs-table-hover-bg", css)
		self.assertIn("--bs-table-bg-state: transparent", css)
		self.assertIn("background-color: var(--edge-color-surface-muted", css)
		self.assertIn("var(--edge-color-ink-950)", css)
		self.assertIn("var(--edge-color-ink-600)", css)

	def test_banking_readiness_dark_surfaces_keep_readable_text(self):
		css = READINESS_CSS.read_text(encoding="utf-8")

		self.assertIn(':root[data-edge-appearance="dark"] .retailedge-banking-readiness-shell', css)
		self.assertIn(":has(.retailedge-banking-readiness-shell)", css)
		self.assertIn(".layout-main-section", css)
		self.assertIn("var(--edge-color-surface-soft", css)
		self.assertIn(".retailedge-readiness-card__header p", css)
		self.assertIn(".retailedge-readiness-context-value strong", css)
		self.assertIn(".retailedge-readiness-issue span", css)
		self.assertIn(".retailedge-readiness-context-item", css)
		self.assertIn(".retailedge-readiness-diagnostics", css)
		self.assertIn("var(--edge-color-surface-muted", css)
		self.assertIn("var(--edge-color-ink-950)", css)


if __name__ == "__main__":
	unittest.main()
