from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
THEME_CSS = APP_ROOT / "public" / "css" / "retailedge_edgeui_theme_compat.css"
WORKSPACE_CSS = APP_ROOT / "public" / "css" / "retailedge_workspace_home.css"
BUSINESS_HUB = (
	APP_ROOT
	/ "public"
	/ "js"
	/ "retailedge_business_hub"
	/ "RetailEdgeBusinessHub.vue"
)


class RetailEdgeThemeCompatibilityTests(unittest.TestCase):
	def test_workspace_loads_theme_compatibility_after_card_layer(self):
		workspace = WORKSPACE_CSS.read_text(encoding="utf-8")
		self.assertTrue(workspace.startswith('@import url("/assets/retailedge/css/retailedge_edgeui_theme_compat.css");'))
		self.assertTrue(THEME_CSS.exists())

	def test_retailedge_neutrals_and_statuses_follow_edgesuite_semantic_tokens(self):
		css = THEME_CSS.read_text(encoding="utf-8")
		for expected in (
			':root[data-edge-palette]',
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

	def test_business_hub_keeps_shared_edgesuite_aliases_instead_of_private_fixed_palette(self):
		component = BUSINESS_HUB.read_text(encoding="utf-8")
		for expected in (
			"var(--edge-border",
			"var(--edge-surface",
			"var(--edge-text-muted",
			"var(--edge-primary",
		):
			self.assertIn(expected, component)


if __name__ == "__main__":
	unittest.main()
