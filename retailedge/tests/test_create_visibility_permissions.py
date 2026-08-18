from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.edgesuite_ui import QUICK_ACTIONS, _get_permitted_quick_actions

APP_ROOT = Path(__file__).resolve().parents[1]
HUB_ROOT = APP_ROOT / "public" / "js" / "retailedge_business_hub"


class TestCreateVisibilityPermissions(unittest.TestCase):
	def test_business_hub_server_omits_actions_without_create_permission(self):
		with (
			patch("retailedge.edgesuite_ui._doctype_exists_cached", return_value=True),
			patch("retailedge.edgesuite_ui._has_permission_cached", return_value=False) as permission,
		):
			actions = _get_permitted_quick_actions(target_cache={}, permission_cache={})
		self.assertEqual(actions, [])
		self.assertEqual(permission.call_count, len(QUICK_ACTIONS))
		self.assertTrue(all(call.args[1] == "create" for call in permission.call_args_list))

	def test_business_hub_hides_create_control_when_no_actions_are_permitted(self):
		component = (HUB_ROOT / "RetailEdgeBusinessHub.vue").read_text(encoding="utf-8")
		host = (APP_ROOT / "public" / "js" / "retailedge_business_hub_page.js").read_text(encoding="utf-8")
		self.assertIn(':disabled="!quickActions.length"', component)
		self.assertIn('v-for="action in quickActions"', component)
		self.assertIn("enforceCreateVisibility", host)
		self.assertIn('root.querySelectorAll(".hub-create-button")', host)
		self.assertIn("button.hidden = unavailable", host)
		self.assertIn("installCreateVisibilityGuard", host)

	def test_inline_master_create_controls_remain_permission_gated(self):
		contracts = {
			"SimpleSalesInvoiceDialog.vue": (
				':canCreate="canCreateCustomer"',
				':canCreate="canCreateItem"',
			),
			"SimplePurchaseInvoiceDialog.vue": (
				':canCreate="canCreateSupplier"',
				':canCreate="canCreateItem"',
			),
			"SimpleStockTransferDialog.vue": (
				"canCreateItemLink",
				"quickCreateItem",
			),
		}
		for filename, expected in contracts.items():
			with self.subTest(filename=filename):
				source = (HUB_ROOT / filename).read_text(encoding="utf-8")
				for contract in expected:
					self.assertIn(contract, source)

	def test_backend_master_capabilities_use_create_permission(self):
		contracts = {
			"guided_sales_invoice.py": (
				'frappe.has_permission("Customer", "create")',
				'frappe.has_permission("Item", "create")',
			),
			"guided_purchase_invoice.py": (
				'frappe.has_permission("Supplier", "create")',
				'frappe.has_permission("Item", "create")',
			),
			"guided_stock_transfer.py": ('frappe.has_permission("Item", "create")',),
		}
		for filename, expected in contracts.items():
			with self.subTest(filename=filename):
				source = (APP_ROOT / filename).read_text(encoding="utf-8")
				for contract in expected:
					self.assertIn(contract, source)


if __name__ == "__main__":
	unittest.main()
