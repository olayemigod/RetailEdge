from __future__ import annotations

import re
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "browser-persona-smoke.yml"
PLAYWRIGHT_CONFIG = REPO_ROOT / "browser-tests" / "playwright.config.cjs"


class TestBrowserPersonaGateInventory(unittest.TestCase):
	def test_every_workflow_browser_spec_is_collectable_by_playwright_config(self):
		workflow = WORKFLOW.read_text(encoding="utf-8")
		config = PLAYWRIGHT_CONFIG.read_text(encoding="utf-8")
		workflow_specs = re.findall(r"browser-tests/retailedge_([a-z0-9_]+)\.spec\.cjs", workflow)

		self.assertTrue(workflow_specs, "Browser persona workflow must list explicit RetailEdge specs.")
		for stem in workflow_specs:
			with self.subTest(spec=stem):
				self.assertIn(
					stem,
					config,
					f"retailedge_{stem}.spec.cjs is passed by the browser workflow but excluded by Playwright testMatch.",
				)

	def test_cashier_receipt_acceptance_is_in_browser_gate(self):
		workflow = WORKFLOW.read_text(encoding="utf-8")
		config = PLAYWRIGHT_CONFIG.read_text(encoding="utf-8")
		self.assertIn("browser-tests/retailedge_cashier_sale_continuity.spec.cjs", workflow)
		self.assertIn("cashier_sale_continuity", config)


if __name__ == "__main__":
	unittest.main()
