from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retailedge import edgesuite_ui

APP_ROOT = Path(__file__).resolve().parents[1]
DIALOG_NAMES = (
	"SimpleSalesInvoiceDialog",
	"SimplePaymentDialog",
	"SimpleCashDepositDialog",
	"SimpleCashTransferDialog",
	"SimplePurchaseInvoiceDialog",
	"SimpleCashierExpenseDialog",
	"SimpleStockTransferDialog",
	"SimpleStockAdjustmentDialog",
)


class RetailEdgePreReportingAccessHardeningTests(unittest.TestCase):
	def test_page_navigation_uses_native_frappe_page_permission(self):
		page = SimpleNamespace(is_permitted=lambda: False)
		with patch.object(edgesuite_ui.frappe, "get_doc", return_value=page) as get_doc:
			self.assertFalse(edgesuite_ui._can_open_page("restricted-page"))
		get_doc.assert_called_once_with("Page", "restricted-page")

	def test_page_permission_failure_fails_closed(self):
		with patch.object(edgesuite_ui.frappe, "get_doc", side_effect=RuntimeError("no page")):
			self.assertFalse(edgesuite_ui._can_open_page("missing-page"))

	def test_native_fallback_quick_action_is_hidden_for_edgesuite_only_users(self):
		with (
			patch("retailedge.edgesuite_ui._doctype_exists_cached", return_value=True),
			patch("retailedge.edgesuite_ui._has_permission_cached", return_value=True),
			patch("retailedge.edgesuite_ui._cashier_deposit_available", return_value=True),
		):
			actions = edgesuite_ui._get_permitted_quick_actions(
				roles={"System Manager"}, native_desk_enabled=False
			)
		keys = {action["key"] for action in actions}
		self.assertNotIn("new-warranty-claim", keys)
		self.assertTrue(actions)
		self.assertTrue(all(action["mode"] == "available" for action in actions))

	def test_native_fallback_remains_available_for_native_desk_users(self):
		with (
			patch("retailedge.edgesuite_ui._doctype_exists_cached", return_value=True),
			patch("retailedge.edgesuite_ui._has_permission_cached", return_value=True),
			patch("retailedge.edgesuite_ui._cashier_deposit_available", return_value=True),
		):
			actions = edgesuite_ui._get_permitted_quick_actions(
				roles={"System Manager"}, native_desk_enabled=True
			)
		self.assertIn("new-warranty-claim", {action["key"] for action in actions})

	def test_retailedge_roles_remain_system_user_roles(self):
		roles = (APP_ROOT / "setup_roles.py").read_text()
		self.assertIn('"desk_access": 1', roles)
		self.assertNotIn('"desk_access": 0', roles)

	def test_business_hub_preserves_native_link_type_for_shared_access_filter(self):
		hub = (APP_ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue").read_text()
		self.assertIn("link_type: item.target_type", hub)
		self.assertIn("link_to: item.target", hub)
		self.assertIn("data.access || {}", hub)
		self.assertIn("if (this.nativeFallbackEnabled)", hub)
		self.assertIn(':native-fallback-enabled="nativeFallbackEnabled"', hub)

	def test_guided_dialogs_hide_full_form_fallback_when_native_desk_is_unavailable(self):
		for name in DIALOG_NAMES:
			with self.subTest(name=name):
				source = (APP_ROOT / f"public/js/retailedge_business_hub/{name}.vue").read_text()
				self.assertIn("nativeFallbackEnabled: { type: Boolean, default: true }", source)
				self.assertIn('v-if="nativeFallbackEnabled"', source)


if __name__ == "__main__":
	unittest.main()
