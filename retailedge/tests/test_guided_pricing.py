from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.guided_pricing import (
	_effective_erpnext_rate,
	resolve_price_list_context,
	resolve_purchase_item_pricing,
	resolve_sales_item_pricing,
)

APP_ROOT = Path(__file__).resolve().parents[1]


def uncached_price_list_resolver():
	return getattr(resolve_price_list_context, "__wrapped__", resolve_price_list_context)


class TestGuidedPricing(unittest.TestCase):
	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._valid_price_list", return_value=True)
	@patch("retailedge.guided_pricing._available_assigned_price_lists", return_value=["Assigned Retail"])
	@patch("retailedge.guided_pricing._party_price_list", return_value="Customer Retail")
	@patch("retailedge.guided_pricing.get_retailedge_settings")
	def test_default_selling_policy_prioritizes_customer_default(
		self,
		mock_settings,
		_mock_party,
		_mock_available,
		_mock_valid,
		mock_context,
	):
		mock_settings.return_value = frappe._dict(
			{
				"enable_price_list_governance": 1,
				"allow_price_list_switch": 1,
				"selling_price_list_policy": "Party > POS > Branch > Assigned Choice",
			}
		)
		mock_context.side_effect = lambda name, **kwargs: {
			"price_list": name,
			"source": kwargs["source"],
		}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			party="CUST-001",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "Customer Retail")
		self.assertEqual(result["source"], "party_default")

	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._valid_price_list", return_value=True)
	@patch("retailedge.guided_pricing._available_assigned_price_lists", return_value=["Assigned Buy"])
	@patch("retailedge.guided_pricing.get_exact_branch_profile")
	@patch("retailedge.guided_pricing._party_price_list", return_value="")
	@patch("retailedge.guided_pricing.get_retailedge_settings")
	def test_default_buying_policy_uses_branch_before_assigned_choice(
		self,
		mock_settings,
		_mock_party,
		mock_branch_profile,
		_mock_available,
		_mock_valid,
		mock_context,
	):
		mock_settings.return_value = frappe._dict(
			{
				"enable_price_list_governance": 1,
				"allow_price_list_switch": 1,
				"buying_price_list_policy": "Party > Branch > Assigned Choice",
			}
		)
		mock_branch_profile.return_value = frappe._dict(
			{"default_buying_price_list": "Branch Buying"}
		)
		mock_context.side_effect = lambda name, **kwargs: {
			"price_list": name,
			"source": kwargs["source"],
		}
		result = uncached_price_list_resolver()(
			mode="buying",
			company="Demo Company",
			branch="Lagos",
			party="SUP-001",
			user="buyer@example.com",
		)
		self.assertEqual(result["price_list"], "Branch Buying")
		self.assertEqual(result["source"], "branch_default")

	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._valid_price_list", return_value=True)
	@patch(
		"retailedge.guided_pricing._available_assigned_price_lists",
		return_value=["Assigned Retail"],
	)
	@patch("retailedge.guided_pricing._resolve_user_pos_profile")
	@patch("retailedge.guided_pricing.get_retailedge_settings")
	def test_single_assigned_list_can_switch_when_pos_list_is_effective(
		self,
		mock_settings,
		mock_pos,
		_mock_available,
		_mock_valid,
		mock_context,
	):
		mock_settings.return_value = frappe._dict(
			{
				"enable_price_list_governance": 1,
				"allow_price_list_switch": 1,
				"selling_price_list_policy": "POS > Party > Branch > Assigned Choice",
			}
		)
		mock_pos.return_value = frappe._dict(
			{"name": "POS-KETU", "selling_price_list": "Standard Selling", "allow_rate_change": 1}
		)
		mock_context.side_effect = lambda name, **kwargs: {
			"price_list": name,
			"source": kwargs["source"],
			"allow_rate_change": True,
		}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Ketu",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "Standard Selling")
		self.assertEqual(result["available_price_lists"], ["Assigned Retail"])
		self.assertTrue(result["can_switch_price_list"])

	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._valid_price_list", return_value=True)
	@patch(
		"retailedge.guided_pricing._available_assigned_price_lists",
		return_value=["Retail A", "Retail B"],
	)
	@patch("retailedge.guided_pricing.get_retailedge_settings")
	def test_assigned_choice_can_be_selected_when_policy_allows_it_first(
		self,
		mock_settings,
		_mock_available,
		_mock_valid,
		mock_context,
	):
		mock_settings.return_value = frappe._dict(
			{
				"enable_price_list_governance": 1,
				"allow_price_list_switch": 1,
				"selling_price_list_policy": "Assigned Choice > Party > POS > Branch",
			}
		)
		mock_context.side_effect = lambda name, **kwargs: {
			"price_list": name,
			"source": kwargs["source"],
		}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
			requested_price_list="Retail B",
		)
		self.assertEqual(result["price_list"], "Retail B")
		self.assertEqual(result["source"], "assigned_choice")
		self.assertTrue(result["can_switch_price_list"])

	@patch(
		"retailedge.guided_pricing._available_assigned_price_lists",
		return_value=["Retail A"],
	)
	@patch("retailedge.guided_pricing.get_retailedge_settings")
	def test_unassigned_requested_price_list_fails_closed(self, mock_settings, _mock_available):
		mock_settings.return_value = frappe._dict(
			{
				"enable_price_list_governance": 1,
				"allow_price_list_switch": 1,
				"selling_price_list_policy": "Assigned Choice > Party > POS > Branch",
			}
		)
		with self.assertRaises(frappe.PermissionError):
			uncached_price_list_resolver()(
				mode="selling",
				company="Demo Company",
				branch="Lagos",
				user="sales@example.com",
				requested_price_list="Not Assigned",
			)

	def test_erpnext_placeholder_zero_does_not_mask_price_list_rate(self):
		details = frappe._dict(
			rate=0,
			price_list_rate=125000,
			discount_percentage=0,
			discount_amount=0,
			margin_type="",
			margin_rate_or_amount=0,
		)
		self.assertEqual(_effective_erpnext_rate(details), 125000.0)

	def test_erpnext_pricing_rule_discount_and_margin_are_preserved(self):
		details = frappe._dict(
			rate=0,
			price_list_rate=1000,
			margin_type="Percentage",
			margin_rate_or_amount=10,
			discount_percentage=20,
			discount_amount=0,
		)
		self.assertEqual(_effective_erpnext_rate(details), 880.0)

	def test_legitimate_full_discount_can_resolve_to_zero(self):
		details = frappe._dict(
			rate=0,
			price_list_rate=1000,
			margin_type="",
			margin_rate_or_amount=0,
			discount_percentage=100,
			discount_amount=0,
		)
		self.assertEqual(_effective_erpnext_rate(details), 0.0)

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

	@patch("retailedge.guided_pricing.frappe.get_cached_value", return_value=0)
	@patch(
		"retailedge.guided_pricing._erpnext_item_details",
		return_value=frappe._dict(rate=0, price_list_rate=0),
	)
	@patch("retailedge.guided_pricing.resolve_price_list_context")
	@patch("retailedge.guided_pricing._assert_read_permission")
	def test_missing_item_price_and_zero_standard_rate_remain_unresolved(
		self,
		_mock_read,
		mock_context,
		_mock_details,
		_mock_cached,
	):
		mock_context.return_value = {
			"price_list": "Standard Selling",
			"source": "pos_profile",
			"allow_rate_change": True,
		}
		result = resolve_sales_item_pricing(
			item_code="ITEM-001",
			company="Demo Company",
			customer="CUST-001",
			user="sales@example.com",
		)
		self.assertIsNone(result["rate"])
		self.assertEqual(result["rate_source"], "unresolved")

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

	def test_pricing_uses_erpnext_service_and_only_accepts_governed_client_price_list(self):
		source = (APP_ROOT / "guided_pricing.py").read_text(encoding="utf-8")
		self.assertIn("get_item_details", source)
		self.assertIn("get_pos_profile", source)
		self.assertIn("get_user_permissions", source)
		self.assertIn('"Standard Selling"', source)
		self.assertIn('"Standard Buying"', source)
		self.assertIn('"standard_rate"', source)
		self.assertIn('"last_purchase_rate"', source)
		self.assertIn("requested_price_list", source)
		self.assertIn("requested_price_list not in available_price_lists", source)
		self.assertIn("get_assignment_price_lists", source)
		self.assertIn("get_exact_branch_profile", source)
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
