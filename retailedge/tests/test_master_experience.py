from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.master_experience import (
	CUSTOMER_ACTION,
	ITEM_ACTION,
	SUPPLIER_ACTION,
	_promote_long_transaction_pages,
	_promote_make_sale,
	get_retailedge_business_hub_context,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestMasterExperience(unittest.TestCase):
	@patch("retailedge.master_experience._can_create_master")
	@patch(
		"retailedge.master_experience._base_business_hub_context",
		return_value={"quick_actions": [{"key": "new-sales-invoice"}], "feature_flags": {}},
	)
	def test_master_actions_follow_create_permission(self, _base, can_create):
		can_create.side_effect = lambda doctype: doctype in {"Customer", "Supplier", "Item"}
		context = get_retailedge_business_hub_context()
		actions = {action["key"]: action for action in context["quick_actions"]}
		self.assertIn("new-customer", actions)
		self.assertIn("new-supplier", actions)
		self.assertIn("new-item", actions)
		self.assertEqual(actions["new-customer"]["doctype"], "Customer")
		self.assertEqual(actions["new-supplier"]["doctype"], "Supplier")
		self.assertEqual(actions["new-item"]["doctype"], "Item")
		self.assertTrue(actions["new-customer"]["master_entry"])
		self.assertTrue(actions["new-supplier"]["master_entry"])
		self.assertTrue(actions["new-item"]["master_entry"])
		self.assertEqual(context["feature_flags"]["simple_master_data_stage"], "customer_supplier_item")

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
		self.assertNotIn("new-item", keys)

	@patch("retailedge.master_experience.frappe.has_permission", return_value=True)
	@patch("retailedge.master_experience.frappe.db.exists", return_value=True)
	@patch("retailedge.master_experience._can_open_page", return_value=True)
	def test_transaction_promotions_recreate_groups_removed_by_edgesuite_only_containment(
		self, _can_open_page, _exists, _has_permission
	):
		navigation = [{"key": "home", "label": "Home", "icon": "home", "items": []}]
		_promote_make_sale(navigation)
		_promote_long_transaction_pages(navigation)

		groups = {group["key"]: group for group in navigation}
		self.assertIn("sell", groups)
		self.assertIn("buy", groups)
		self.assertIn("stock", groups)
		self.assertIn("make-sale", {item["target"] for item in groups["sell"]["items"]})
		self.assertIn("record-purchase", {item["target"] for item in groups["buy"]["items"]})
		self.assertIn("transfer-stock", {item["target"] for item in groups["stock"]["items"]})
		self.assertIn("stock-adjustment", {item["target"] for item in groups["stock"]["items"]})

	@patch("retailedge.master_experience.frappe.has_permission", return_value=False)
	@patch("retailedge.master_experience.frappe.db.exists", return_value=True)
	@patch("retailedge.master_experience._can_open_page", return_value=True)
	def test_transaction_promotions_do_not_create_groups_without_doctype_create_permission(
		self, _can_open_page, _exists, _has_permission
	):
		navigation = [{"key": "home", "label": "Home", "icon": "home", "items": []}]
		_promote_make_sale(navigation)
		_promote_long_transaction_pages(navigation)
		self.assertEqual([group["key"] for group in navigation], ["home"])

	def test_master_action_contracts_use_native_erpnext_masters(self):
		self.assertEqual(CUSTOMER_ACTION["doctype"], "Customer")
		self.assertEqual(SUPPLIER_ACTION["doctype"], "Supplier")
		self.assertEqual(ITEM_ACTION["doctype"], "Item")
		for action in (CUSTOMER_ACTION, SUPPLIER_ACTION, ITEM_ACTION):
			self.assertNotIn("submit", action)
		hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
		self.assertIn(
			'"retailedge.edgesuite_ui.get_retailedge_business_hub_context": '
			'"retailedge.master_experience.get_retailedge_business_hub_context"',
			hooks,
		)


if __name__ == "__main__":
	unittest.main()
