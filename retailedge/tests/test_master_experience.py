from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.master_experience import CUSTOMER_ACTION, get_retailedge_business_hub_context

APP_ROOT = Path(__file__).resolve().parents[1]


class TestMasterExperience(unittest.TestCase):
	@patch("retailedge.master_experience._can_create_customer", return_value=True)
	@patch(
		"retailedge.master_experience._base_business_hub_context",
		return_value={"quick_actions": [{"key": "new-sales-invoice"}], "feature_flags": {}},
	)
	def test_customer_action_is_added_when_create_is_allowed(self, _base, _can_create):
		context = get_retailedge_business_hub_context()
		actions = {action["key"]: action for action in context["quick_actions"]}
		self.assertIn("new-customer", actions)
		self.assertEqual(actions["new-customer"]["doctype"], "Customer")
		self.assertEqual(actions["new-customer"]["mode"], "quick_entry")
		self.assertTrue(actions["new-customer"]["master_entry"])
		self.assertEqual(context["feature_flags"]["simple_master_data_stage"], "customer")

	@patch("retailedge.master_experience._can_create_customer", return_value=False)
	@patch(
		"retailedge.master_experience._base_business_hub_context",
		return_value={"quick_actions": [{"key": "new-sales-invoice"}], "feature_flags": {}},
	)
	def test_customer_action_is_hidden_without_create_permission(self, _base, _can_create):
		context = get_retailedge_business_hub_context()
		self.assertNotIn("new-customer", {action["key"] for action in context["quick_actions"]})

	def test_customer_action_contract_uses_native_customer_master(self):
		self.assertEqual(CUSTOMER_ACTION["doctype"], "Customer")
		self.assertNotIn("submit", CUSTOMER_ACTION)
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn(
			'"retailedge.edgesuite_ui.get_retailedge_business_hub_context": '
			'"retailedge.master_experience.get_retailedge_business_hub_context"',
			hooks,
		)


if __name__ == "__main__":
	unittest.main()
