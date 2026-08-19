from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class TestMoneyOverviewShell(unittest.TestCase):
	def test_money_overview_page_uses_shared_edgesuite_dashboard_shell(self):
		vue = (APP_ROOT / "public" / "js" / "money_overview" / "MoneyOverview.vue").read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public" / "js" / "money_overview.bundle.js").read_text(encoding="utf-8")
		controller = (APP_ROOT / "retailedge" / "page" / "money_overview" / "money_overview.js").read_text(encoding="utf-8")
		self.assertIn("EdgeDashboardShell", vue)
		self.assertIn('const DASHBOARD_KEY = "money-overview"', vue)
		self.assertIn("Period net change is a flow metric, not a closing cash or bank balance", vue)
		self.assertIn("get_money_dashboard_data", vue)
		self.assertIn("exportDashboard", vue)
		self.assertIn("printDashboard", vue)
		self.assertIn("createEdgeApp", bundle)
		self.assertIn("mountMoneyOverview", bundle)
		self.assertIn('const DASHBOARD_ASSET = "money_overview.bundle.js"', controller)

	def test_page_definition_exists(self):
		path = APP_ROOT / "retailedge" / "page" / "money_overview" / "money_overview.json"
		page = json.loads(path.read_text(encoding="utf-8"))
		self.assertEqual(page["name"], "money-overview")
		self.assertEqual(page["title"], "Money Overview")

	def test_preview_is_not_promoted_to_navigation_before_browser_qa(self):
		for path in (
			APP_ROOT / "workspace.py",
			APP_ROOT / "workspace_sidebar.py",
			APP_ROOT / "edgesuite_ui.py",
		):
			if path.exists():
				self.assertNotIn('"money-overview"', path.read_text(encoding="utf-8"))

	def test_shared_dashboard_export_registers_money_overview(self):
		source = (APP_ROOT / "dashboard_files.py").read_text(encoding="utf-8")
		self.assertIn("build_money_dashboard_export_dataset", source)
		self.assertIn('"money-overview"', source)


if __name__ == "__main__":
	unittest.main()
