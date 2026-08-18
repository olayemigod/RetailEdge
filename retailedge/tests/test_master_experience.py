from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.master_experience import (
	CUSTOMER_ACTION,
	SUPPLIER_ACTION,
	get_retailedge_business_hub_context,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestMasterExperience(unittest.TestCase):
	@patch("retailedge.master_experience._can_create_master")
	@patch(
		"retailedge.master_experience._base_business_hub_context",
		return_value={"quick_actions": [{"key": "new-sales-invoice"}], "feature_flags": {}},
	)
	def test_customer_and_supplier_actions_follow_create_permission(self, _base, can_create):
		can_create.side_effect = lambda doctype: doctype in {"Customer", "Supplier"}
		context = get_retailedge_business_hub_context()
		actions = {action["key"]: action for action in context["quick_actions"]}
		self.assertIn("new-customer", actions)
		self.assertIn("new-supplier", actions)
		self.assertEqual(actions["new-customer"]["doctype"], "Customer")
		self.assertEqual(actions["new-supplier"]["doctype"], "Supplier")
		self.assertTrue(actions["new-customer"]["master_entry"])
		self.assertTrue(actions["new-supplier"]["master_entry"])
		self.assertEqual(context["feature_flags"]["simple_master_data_stage"], "customer_supplier")

	@patch("retailedge.master_experience._can_create_master", return_value=False)
	@patch(
		"retailedge.master_experience._base_business_hub_context",
		return_value={"quick_actions": [{"key": "new-sales-invoice"}], "feature_flags": {}},
	)
	def test_master_actions_are_hidden_without_create_permission(self, _base, _can_create):
		context = get_retailedge_business_hub_context()
		keys = {action["key"] for action in context["quick_actions"]}
		self.assertNotIn("new-customer", keys)
		self.assertNotIn("new-supplier", keys)

	def test_master_action_contracts_use_native_erpnext_masters(self):
		self.assertEqual(CUSTOMER_ACTION["doctype"], "Customer")
		self.assertEqual(SUPPLIER_ACTION["doctype"], "Supplier")
		self.assertNotIn("submit", CUSTOMER_ACTION)
		self.assertNotIn("submit", SUPPLIER_ACTION)
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn(
			'"retailedge.edgesuite_ui.get_retailedge_business_hub_context": '
			'"retailedge.master_experience.get_retailedge_business_hub_context"',
			hooks,
		)


if __name__ == "__main__":
	unittest.main()
