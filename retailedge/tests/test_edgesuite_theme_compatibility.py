from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
THEME_CSS = APP_ROOT / "public" / "css" / "retailedge_edgeui_theme_compat.css"
IDENTITY_CSS = APP_ROOT / "public" / "css" / "retailedge_product_identity.css"
WORKSPACE_CSS = APP_ROOT / "public" / "css" / "retailedge_workspace_home.css"
BUSINESS_HUB = APP_ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
STOCK_ACCOUNTING_INTEGRITY = (
	APP_ROOT / "public" / "js" / "stock_accounting_integrity" / "StockAccountingIntegrityReport.vue"
)


class RetailEdgeThemeCompatibilityTests(unittest.TestCase):
	def test_workspace_loads_theme_compatibility_after_card_layer(self):
		workspace = WORKSPACE_CSS.read_text(encoding="utf-8")
		self.assertTrue(
			workspace.startswith('@import url("/assets/retailedge/css/retailedge_edgeui_theme_compat.css");')
		)
		self.assertTrue(THEME_CSS.exists())

	def test_retailedge_neutrals_and_statuses_follow_edgesuite_semantic_tokens(self):
		css = THEME_CSS.read_text(encoding="utf-8")
		for expected in (
			":root[data-edge-palette]",
			"--pe-blue-700: var(--edge-color-brand-600)",
			"--pe-grey-950: var(--edge-color-ink-950)",
			"--pe-grey-500: var(--edge-color-ink-500)",
			"--pe-grey-200: var(--edge-color-border)",
			"--pe-grey-100: var(--edge-color-surface-muted)",
			"--pe-white: var(--edge-color-surface)",
			"--pe-success: var(--edge-color-success)",
			"--pe-warning: var(--edge-color-warning)",
			"--pe-danger: var(--edge-color-danger)",
			"--pe-info: var(--edge-color-info)",
			"--retailedge-shadow: var(--edge-shadow-sm",
		):
			self.assertIn(expected, css)

	def test_cards_and_workspace_use_theme_surfaces_when_palette_is_active(self):
		css = THEME_CSS.read_text(encoding="utf-8")
		for expected in (
			"var(--edge-color-surface) 0%",
			"var(--edge-color-surface-muted) 100%",
			"border-color: var(--edge-color-border)",
			"color: var(--edge-color-ink-950)",
			"var(--edge-color-brand-600)",
			"Workspaces/RetailEdge",
		):
			self.assertIn(expected, css)

	def test_product_sidebar_follows_light_dark_edgesuite_semantic_tokens(self):
		css = IDENTITY_CSS.read_text(encoding="utf-8")
		for expected in (
			"--retailedge-sidebar: var(--edge-color-surface);",
			"--retailedge-sidebar-muted: var(--edge-color-ink-500);",
			"background: var(--edge-color-surface);",
			"border-right: 1px solid var(--edge-color-border);",
			"color: var(--edge-color-ink-950);",
			".edge-sidebar__brand-copy strong",
			".edge-topbar__title-copy strong",
			"background: var(--edge-color-surface-muted);",
			'edge-sidebar-item[aria-current="page"]',
			':root[data-edge-appearance="dark"] [data-edge-product="retailedge"]',
		):
			self.assertIn(expected, css)

		for forbidden in (
			"color: #f7fbfc;",
			"color: #dce6ec;",
			"background: rgba(255, 255, 255, 0.07);",
			"border-right: 0;",
		):
			self.assertNotIn(forbidden, css)

	def test_business_hub_uses_semantic_theme_tokens_and_compact_business_indices(self):
		component = BUSINESS_HUB.read_text(encoding="utf-8")
		for expected in (
			"var(--edge-color-border",
			"var(--edge-color-surface",
			"var(--edge-color-surface-muted",
			"var(--edge-color-ink-950",
			"var(--edge-color-ink-500",
			"var(--edge-color-brand-600",
			':global(:root[data-edge-appearance="dark"]) .retailedge-business-hub',
			".home-signal-icon {",
			"width: 24px;",
			"font-size: 0.96rem;",
		):
			self.assertIn(expected, component)

		for forbidden in (
			"var(--edge-surface, #ffffff)",
			"var(--edge-surface-muted, #f8fafc)",
			"var(--edge-text-muted, #667085)",
			"var(--edge-primary, #2563eb)",
		):
			self.assertNotIn(forbidden, component)

	def test_c22_integrity_page_uses_edgesuite_shell_and_semantic_theme_aliases(self):
		component = STOCK_ACCOUNTING_INTEGRITY.read_text(encoding="utf-8")
		for expected in (
			"EdgeAppShell",
			"EdgeReportShell",
			"var(--edge-border",
			"var(--edge-surface",
			"var(--edge-text-muted",
		):
			self.assertIn(expected, component)


if __name__ == "__main__":
	unittest.main()
