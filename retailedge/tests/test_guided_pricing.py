from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.guided_pricing import (
	resolve_price_list_context,
	resolve_purchase_item_pricing,
	resolve_sales_item_pricing,
)

APP_ROOT = Path(__file__).resolve().parents[1]


def uncached_price_list_resolver():
	return getattr(resolve_price_list_context, "__wrapped__", resolve_price_list_context)


class TestGuidedPricing(unittest.TestCase):
	@patch("retailedge.guided_pricing._valid_price_list")
	@patch("retailedge.guided_pricing.frappe.defaults.get_user_default")
	def test_direct_user_selling_price_list_has_first_priority(self, mock_default, mock_valid):
		mock_default.side_effect = lambda key: "User Retail" if key == "Selling Price List" else None
		mock_valid.return_value = True
		with patch("retailedge.guided_pricing._price_context") as mock_context:
			mock_context.return_value = {
				"price_list": "User Retail",
				"source": "user_default",
			}
			result = uncached_price_list_resolver()(
				mode="selling",
				company="Demo Company",
				user="sales@example.com",
			)
		self.assertEqual(result["price_list"], "User Retail")
		mock_context.assert_called_once_with("User Retail", mode="selling", source="user_default")

	@patch("retailedge.guided_pricing.frappe.db.get_value", return_value="NGN")
	@patch("retailedge.guided_pricing._valid_price_list")
	@patch("retailedge.guided_pricing._resolve_user_pos_profile")
	@patch("retailedge.guided_pricing._default_user_permission_price_list", return_value="")
	@patch("retailedge.guided_pricing.frappe.defaults.get_user_default", return_value=None)
	def test_assigned_pos_profile_supplies_selling_price_list(
		self,
		_mock_default,
		_mock_permission_price,
		mock_pos,
		mock_valid,
		_mock_get_value,
	):
		mock_pos.return_value = frappe._dict(
			{
				"name": "POS-LAGOS",
				"selling_price_list": "POS Retail",
				"allow_rate_change": 0,
			}
		)
		mock_valid.side_effect = lambda name, **_kwargs: bool(str(name or "").strip())
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "POS Retail")
		self.assertEqual(result["source"], "pos_profile")
		self.assertEqual(result["pos_profile"], "POS-LAGOS")
		self.assertFalse(result["allow_rate_change"])

	@patch("retailedge.guided_pricing.frappe.get_cached_value")
	@patch("retailedge.guided_pricing._erpnext_item_details", return_value=frappe._dict())
	@patch("retailedge.guided_pricing.resolve_price_list_context")
	@patch("retailedge.guided_pricing._assert_read_permission")
	def test_sales_falls_back_to_item_standard_rate(
		self,
		_mock_read,
		mock_context,
		_mock_details,
		mock_cached,
	):
		mock_context.return_value = {
			"price_list": "",
			"source": "item_fallback",
			"allow_rate_change": True,
		}
		mock_cached.return_value = 1750
		result = resolve_sales_item_pricing(
			item_code="ITEM-001",
			company="Demo Company",
			customer="CUST-001",
			user="sales@example.com",
		)
		self.assertEqual(result["rate"], 1750.0)
		self.assertEqual(result["rate_source"], "item_standard_rate")

	@patch("retailedge.guided_pricing.frappe.get_cached_value")
	@patch("retailedge.guided_pricing._erpnext_item_details", return_value=frappe._dict())
	@patch("retailedge.guided_pricing.resolve_price_list_context")
	@patch("retailedge.guided_pricing._assert_read_permission")
	def test_purchase_falls_back_to_item_last_purchase_rate(
		self,
		_mock_read,
		mock_context,
		_mock_details,
		mock_cached,
	):
		mock_context.return_value = {"price_list": "", "source": "item_fallback"}
		mock_cached.return_value = 925
		result = resolve_purchase_item_pricing(
			item_code="ITEM-001",
			company="Demo Company",
			supplier="SUP-001",
			user="buyer@example.com",
		)
		self.assertEqual(result["rate"], 925.0)
		self.assertEqual(result["rate_source"], "item_last_purchase_rate")

	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._assignment_price_list_scope", return_value={"names": ["Branch Wholesale"], "restricted": True, "assignment_names": ["BA-1"]})
	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="Branch Retail")
	def test_branch_default_always_precedes_selected_or_assigned_price_list(
		self, _mock_branch_default, _mock_assignment, mock_context
	):
		mock_context.return_value = {"price_list": "Branch Retail", "source": "branch_default"}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			selected_price_list="Branch Wholesale",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "Branch Retail")
		self.assertTrue(result["locked"])
		self.assertFalse(result["can_select"])

	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._default_selectable_price_lists", return_value=[])
	@patch("retailedge.guided_pricing._assignment_price_list_scope", return_value={"names": ["Retail", "Wholesale"], "restricted": True, "assignment_names": ["BA-1"]})
	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="")
	@patch("retailedge.guided_pricing._valid_price_list", return_value=True)
	def test_selected_assigned_price_list_is_accepted(
		self, _mock_valid, _mock_branch_default, _mock_assignment, _mock_defaults, mock_context
	):
		mock_context.return_value = {"price_list": "Wholesale", "source": "user_selected"}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			selected_price_list="Wholesale",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "Wholesale")
		self.assertEqual(result["source"], "user_selected")

	@patch("retailedge.guided_pricing._default_selectable_price_lists", return_value=[])
	@patch("retailedge.guided_pricing._assignment_price_list_scope", return_value={"names": ["Retail", "Wholesale"], "restricted": True, "assignment_names": ["BA-1"]})
	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="")
	def test_unassigned_selected_price_list_is_rejected(
		self, _mock_branch_default, _mock_assignment, _mock_defaults
	):
		with self.assertRaises(frappe.PermissionError):
			uncached_price_list_resolver()(
				mode="selling",
				company="Demo Company",
				branch="Lagos",
				selected_price_list="Secret VIP",
				user="sales@example.com",
			)

	@patch("retailedge.guided_pricing._default_user_permission_price_list", return_value="")
	@patch("retailedge.guided_pricing.frappe.defaults.get_user_default", return_value=None)
	@patch("retailedge.guided_pricing._default_selectable_price_lists", return_value=[])
	@patch("retailedge.guided_pricing._assignment_price_list_scope", return_value={"names": ["Retail", "Wholesale"], "restricted": True, "assignment_names": ["BA-1"]})
	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="")
	def test_multiple_assigned_price_lists_require_selection_without_default(
		self, _mock_branch_default, _mock_assignment, _mock_defaults, _mock_user_default, _mock_permission
	):
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
		)
		self.assertTrue(result["selection_required"])
		self.assertEqual(result["allowed_price_lists"], ["Retail", "Wholesale"])

	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._default_selectable_price_lists", return_value=["User Retail"])
	@patch("retailedge.guided_pricing._assignment_price_list_scope", return_value={"names": ["Wholesale"], "restricted": True, "assignment_names": ["BA-1"]})
	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="")
	@patch("retailedge.guided_pricing._valid_price_list", return_value=True)
	@patch("retailedge.guided_pricing.frappe.defaults.get_user_default")
	def test_existing_user_default_is_preserved_alongside_branch_assignments(
		self, mock_default, _mock_valid, _mock_branch_default, _mock_assignment, _mock_selectable, mock_context
	):
		mock_default.side_effect = lambda key: "User Retail" if key == "Selling Price List" else None
		mock_context.return_value = {"price_list": "User Retail", "source": "user_default"}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "User Retail")
		self.assertIn("Wholesale", result["allowed_price_lists"])
		self.assertIn("User Retail", result["allowed_price_lists"])
		self.assertTrue(result["can_select"])

	def test_pricing_uses_erpnext_service_and_validates_selected_price_list(self):
		source = (APP_ROOT / "guided_pricing.py").read_text(encoding="utf-8")
		self.assertIn("get_item_details", source)
		self.assertIn("get_pos_profile", source)
		self.assertIn("get_user_permissions", source)
		self.assertIn('"Standard Selling"', source)
		self.assertIn('"Standard Buying"', source)
		self.assertIn('"standard_rate"', source)
		self.assertIn('"last_purchase_rate"', source)
		self.assertIn("selected_price_list", source)
		self.assertIn("branch_default", source)
		self.assertIn("get_branch_assignment_price_lists", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.get_all(", source)

	def test_stock_transfer_remains_rate_free(self):
		backend = (APP_ROOT / "guided_stock_transfer.py").read_text(encoding="utf-8")
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "retailedge_business_hub"
			/ "SimpleStockTransferDialog.vue"
		).read_text(encoding="utf-8")
		self.assertNotIn('fieldname: "rate"', component)
		self.assertNotIn('"rate": item', backend)
		self.assertNotIn('row["rate"]', backend)


if __name__ == "__main__":
	unittest.main()
