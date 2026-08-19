from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestActionCenterShell(unittest.TestCase):
	def test_page_uses_edgesuite_shell_and_safe_follow_up_drill_through(self):
		vue = (APP_ROOT / "public/js/action_center/ActionCenter.vue").read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public/js/action_center.bundle.js").read_text(encoding="utf-8")
		page = (APP_ROOT / "retailedge/page/action_center/action_center.js").read_text(encoding="utf-8")
		self.assertIn("EdgeAppShell", vue)
		self.assertIn("EdgeDashboardShell", vue)
		self.assertIn("Critical", vue)
		self.assertIn("Needs Attention", vue)
		self.assertIn("Follow-up tracking is separate from business resolution", vue)
		self.assertIn("Open workflow", vue)
		self.assertIn("Acknowledge", vue)
		self.assertIn("Assign", vue)
		self.assertIn("Follow-up", vue)
		self.assertIn("Snooze", vue)
		self.assertIn("Reopen", vue)
		self.assertIn("Follow-up Status", vue)
		self.assertIn("My Actions", vue)
		self.assertIn("Due / Overdue", vue)
		self.assertIn("effective_status", vue)
		self.assertIn("retailedge.action_follow_up.update_action_follow_up", vue)
		self.assertNotIn("apply_workflow", vue)
		self.assertNotIn("submit()", vue)
		self.assertNotIn("approve", vue.lower())
		self.assertIn("createEdgeApp", bundle)
		self.assertIn("action_center.bundle.js", page)

	def test_preview_page_is_restricted_to_management_and_control_roles(self):
		page_path = APP_ROOT / "retailedge/page/action_center/action_center.json"
		page = json.loads(page_path.read_text(encoding="utf-8"))
		roles = {row["role"] for row in page.get("roles") or []}
		self.assertIn("System Manager", roles)
		self.assertIn("RetailEdge Manager", roles)
		self.assertIn("RetailEdge Branch Manager", roles)
		self.assertIn("RetailEdge Auditor", roles)
		self.assertIn("Accounts Manager", roles)
		self.assertIn("Stock Manager", roles)
		self.assertNotIn("Sales User", roles)
		self.assertNotIn("Stock User", roles)
		self.assertNotIn("Purchase User", roles)

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
