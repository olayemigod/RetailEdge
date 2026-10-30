from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.navigation_visibility import _project_cashier_navigation


class TestCashierNavigationProjection(unittest.TestCase):
	@patch("retailedge.navigation_visibility.frappe.has_permission", return_value=False)
	@patch("retailedge.navigation_visibility.frappe.get_roles", return_value=["RetailEdgeCashier"])
	def test_thin_cashier_keeps_only_self_service_and_pos_when_sales_create_is_denied(
		self,
		_roles,
		_has_permission,
	):
		context = {
			"navigation_groups": [
				{
					"key": "sales",
					"items": [
						{"label": "My Work", "target_type": "Page", "target": "cashier-my-work"},
						{"label": "Start POS", "target_type": "URL", "target": "/pos/"},
						{"label": "Make Sale", "target_type": "Page", "target": "make-sale"},
						{"label": "Reports Centre", "target_type": "Page", "target": "reports-centre"},
					],
				},
				{
					"key": "management",
					"items": [
						{"label": "Assets", "target_type": "Page", "target": "assets-control"},
						{"label": "Warranty", "target_type": "Page", "target": "service-warranty-control"},
					],
				},
			],
			"quick_actions": [
				{"label": "Start POS", "target_type": "URL", "target": "/pos/"},
				{"label": "Quick Sale", "target_type": "DocType", "target": "Sales Invoice"},
			],
		}

		_project_cashier_navigation(context)

		self.assertEqual([group["key"] for group in context["navigation_groups"]], ["sales"])
		self.assertEqual(
			[item["target"] for item in context["navigation_groups"][0]["items"]],
			["cashier-my-work", "/pos/"],
		)
		self.assertEqual([action["target"] for action in context["quick_actions"]], ["/pos/"])

	@patch("retailedge.navigation_visibility.frappe.db.exists", return_value=True)
	@patch("retailedge.navigation_visibility.frappe.has_permission", return_value=True)
	@patch("retailedge.navigation_visibility.frappe.get_roles", return_value=["RetailEdgeCashier"])
	def test_cashier_keeps_make_sale_and_quick_sale_only_when_native_create_is_granted(
		self,
		_roles,
		_has_permission,
		_exists,
	):
		context = {
			"navigation_groups": [
				{
					"key": "sales",
					"items": [
						{"label": "My Work", "target_type": "Page", "target": "cashier-my-work"},
						{"label": "Make Sale", "target_type": "Page", "target": "make-sale"},
					],
				}
			],
			"quick_actions": [
				{"label": "Quick Sale", "target_type": "DocType", "target": "Sales Invoice"},
			],
		}

		_project_cashier_navigation(context)

		self.assertEqual(
			[item["target"] for item in context["navigation_groups"][0]["items"]],
			["cashier-my-work", "make-sale"],
		)
		self.assertEqual([action["target"] for action in context["quick_actions"]], ["Sales Invoice"])

	@patch(
		"retailedge.navigation_visibility.frappe.get_roles",
		return_value=["RetailEdgeCashier", "RetailEdgeManager"],
	)
	def test_manager_who_also_has_cashier_role_is_not_reduced_to_cashier_menu(self, _roles):
		context = {
			"navigation_groups": [
				{
					"key": "management",
					"items": [{"label": "Assets", "target_type": "Page", "target": "assets-control"}],
				}
			],
			"quick_actions": [],
		}

		_project_cashier_navigation(context)

		self.assertEqual(context["navigation_groups"][0]["items"][0]["target"], "assets-control")


if __name__ == "__main__":
	unittest.main()
