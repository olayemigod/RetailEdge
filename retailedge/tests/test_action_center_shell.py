from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge import edgesuite_ui

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
		self.assertIn("openWorkflow(item)", vue)
		self.assertIn('item.open_mode === "new_tab"', vue)
		self.assertIn('window.open(route, "_blank", "noopener,noreferrer")', vue)
		self.assertIn("window.location.assign(route)", vue)
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

	def test_page_is_restricted_to_management_and_control_roles(self):
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

	@patch("retailedge.edgesuite_ui._can_open_target", return_value=True)
	def test_edgesuite_navigation_promotes_action_center_only_for_allowed_roles(self, _can_open):
		manager_groups = edgesuite_ui._get_permitted_navigation_groups({"RetailEdge Manager"})
		manager_items = [item for group in manager_groups for item in group.get("items") or []]
		self.assertTrue(any(item.get("target") == "action-center" for item in manager_items))

		ordinary_groups = edgesuite_ui._get_permitted_navigation_groups({"Sales User"})
		ordinary_items = [item for group in ordinary_groups for item in group.get("items") or []]
		self.assertFalse(any(item.get("target") == "action-center" for item in ordinary_items))
		self.assertTrue(all("required_roles" not in item for item in manager_items))

	def test_native_workspace_fallback_does_not_bypass_role_gated_promotion(self):
		for relative in (
			"retailedge/workspace/retailedge/retailedge.json",
			"retailedge/workspace_sidebar/retailedge/retailedge.json",
			"workspace_sidebar/retailedge.json",
		):
			text = (APP_ROOT / relative).read_text(encoding="utf-8")
			self.assertNotIn('"action-center"', text)


if __name__ == "__main__":
	unittest.main()
