from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestActionCenterShell(unittest.TestCase):
	def test_page_uses_edgesuite_shell_and_read_only_drill_through(self):
		vue = (APP_ROOT / "public/js/action_center/ActionCenter.vue").read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public/js/action_center.bundle.js").read_text(encoding="utf-8")
		page = (APP_ROOT / "retailedge/page/action_center/action_center.js").read_text(encoding="utf-8")
		self.assertIn("EdgeAppShell", vue)
		self.assertIn("EdgeDashboardShell", vue)
		self.assertIn("Critical", vue)
		self.assertIn("Needs Attention", vue)
		self.assertIn("read-only prioritisation layer", vue)
		self.assertIn("openRoute(item.route)", vue)
		self.assertNotIn("apply_workflow", vue)
		self.assertNotIn("submit()", vue)
		self.assertNotIn("approve", vue.lower())
		self.assertIn("createEdgeApp", bundle)
		self.assertIn("action_center.bundle.js", page)

	def test_preview_is_not_promoted_to_normal_navigation_yet(self):
		for relative in (
			"retailedge/workspace/retailedge/retailedge.json",
			"retailedge/workspace_sidebar/retailedge/retailedge.json",
			"workspace_sidebar/retailedge.json",
		):
			text = (APP_ROOT / relative).read_text(encoding="utf-8")
			self.assertNotIn('"action-center"', text)


if __name__ == "__main__":
	unittest.main()
