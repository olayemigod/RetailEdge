from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.guided_pricing import (
	DEFAULT_PRICE_PRECEDENCE,
	_resolve_default_price_list_candidate,
	get_allowed_price_list_context,
	resolve_price_list_context,
	resolve_purchase_item_pricing,
	resolve_sales_item_pricing,
)

APP_ROOT = Path(__file__).resolve().parents[1]


def uncached_price_list_resolver():
	return getattr(resolve_price_list_context, "__wrapped__", resolve_price_list_context)


def policy(**overrides):
	base = {
		"enabled": True,
		"precedence": list(DEFAULT_PRICE_PRECEDENCE["selling"]),
		"enable_assigned_switching": True,
		"allow_switch_from_party_default": False,
		"allow_switch_from_pos_profile": False,
		"allow_switch_from_branch_default": True,
		"allow_switch_from_user_default": True,
		"allow_switch_from_system_default": True,
	}
	base.update(overrides)
	return base


class TestGuidedPricing(unittest.TestCase):
	def test_default_merchant_policy_is_party_then_pos_then_branch_for_sales(self):
		self.assertEqual(
			list(DEFAULT_PRICE_PRECEDENCE["selling"])[:3],
			["party_default", "pos_profile", "branch_default"],
		)
		self.assertEqual(
			list(DEFAULT_PRICE_PRECEDENCE["buying"])[:2],
			["party_default", "branch_default"],
		)

	@patch("retailedge.guided_pricing._price_source_candidate")
	def test_custom_precedence_controls_which_default_source_wins(self, mock_candidate):
		def candidate(*, source, **_kwargs):
			return {
				"party_default": {"price_list": "Customer Retail", "source": source},
				"branch_default": {"price_list": "Branch Retail", "source": source},
			}.get(source)

		mock_candidate.side_effect = candidate
		result = _resolve_default_price_list_candidate(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			party="CUST-001",
			user="sales@example.com",
			precedence=["branch_default", "party_default", "pos_profile"],
		)
		self.assertEqual(result["price_list"], "Branch Retail")
		self.assertEqual(result["source"], "branch_default")
		self.assertEqual(mock_candidate.call_args_list[0].kwargs["source"], "branch_default")

	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="Branch Retail")
	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._resolve_default_price_list_candidate")
	@patch("retailedge.guided_pricing._assignment_price_list_scope")
	@patch("retailedge.guided_pricing._price_list_governance_policy")
	def test_party_default_can_be_locked_by_merchant_policy(
		self, mock_policy, mock_assignment, mock_default, mock_context, _mock_branch
	):
		mock_policy.return_value = policy(allow_switch_from_party_default=False)
		mock_assignment.return_value = {
			"names": ["Wholesale"],
			"restricted": True,
			"assignment_names": ["BA-1"],
		}
		mock_default.return_value = {
			"price_list": "Customer Retail",
			"source": "party_default",
			"allow_rate_change": True,
		}
		mock_context.return_value = {
			"price_list": "Customer Retail",
			"source": "party_default",
		}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			party="CUST-001",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "Customer Retail")
		self.assertTrue(result["locked"])
		self.assertFalse(result["can_select"])
		self.assertEqual(result["allowed_price_lists"], ["Customer Retail"])

	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="Branch Retail")
	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._resolve_default_price_list_candidate")
	@patch("retailedge.guided_pricing._assignment_price_list_scope")
	@patch("retailedge.guided_pricing._price_list_governance_policy")
	def test_party_default_can_be_preferred_but_switchable(
		self, mock_policy, mock_assignment, mock_default, mock_context, _mock_branch
	):
		mock_policy.return_value = policy(allow_switch_from_party_default=True)
		mock_assignment.return_value = {
			"names": ["Wholesale", "VIP Retail"],
			"restricted": True,
			"assignment_names": ["BA-1"],
		}
		mock_default.return_value = {
			"price_list": "Customer Retail",
			"source": "party_default",
			"allow_rate_change": True,
		}
		mock_context.return_value = {
			"price_list": "Customer Retail",
			"source": "party_default",
		}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			party="CUST-001",
			user="sales@example.com",
		)
		self.assertFalse(result["locked"])
		self.assertTrue(result["can_select"])
		self.assertEqual(
			result["allowed_price_lists"],
			["Customer Retail", "Wholesale", "VIP Retail"],
		)

	@patch("retailedge.guided_pricing._branch_default_price_list", return_value="Branch Retail")
	@patch("retailedge.guided_pricing._price_context")
	@patch("retailedge.guided_pricing._resolve_default_price_list_candidate")
	@patch("retailedge.guided_pricing._assignment_price_list_scope")
	@patch("retailedge.guided_pricing._price_list_governance_policy")
	def test_selected_branch_assigned_alternative_is_revalidated_server_side(
		self, mock_policy, mock_assignment, mock_default, mock_context, _mock_branch
	):
		mock_policy.return_value = policy(allow_switch_from_branch_default=True)
		mock_assignment.return_value = {
			"names": ["Wholesale"],
			"restricted": True,
			"assignment_names": ["BA-1"],
		}
		mock_default.return_value = {
			"price_list": "Branch Retail",
			"source": "branch_default",
			"allow_rate_change": True,
		}
		mock_context.return_value = {
			"price_list": "Wholesale",
			"source": "user_selected",
		}
		result = uncached_price_list_resolver()(
			mode="selling",
			company="Demo Company",
			branch="Lagos",
			selected_price_list="Wholesale",
			user="sales@example.com",
		)
		self.assertEqual(result["price_list"], "Wholesale")
		self.assertEqual(result["source"], "user_selected")
		self.assertEqual(result["resolved_default"], "Branch Retail")

	@patch("retailedge.guided_pricing._resolve_default_price_list_candidate")
	@patch("retailedge.guided_pricing._assignment_price_list_scope")
	@patch("retailedge.guided_pricing._price_list_governance_policy")
	def test_selected_alternative_is_rejected_when_source_switching_is_disabled(
		self, mock_policy, mock_assignment, mock_default
	):
		mock_policy.return_value = policy(allow_switch_from_party_default=False)
		mock_assignment.return_value = {
			"names": ["Wholesale"],
			"restricted": True,
			"assignment_names": ["BA-1"],
		}
		mock_default.return_value = {
			"price_list": "Customer Retail",
			"source": "party_default",
			"allow_rate_change": True,
		}
		with self.assertRaises(frappe.PermissionError):
			uncached_price_list_resolver()(
				mode="selling",
				company="Demo Company",
				branch="Lagos",
				party="CUST-001",
				selected_price_list="Wholesale",
				user="sales@example.com",
			)

	@patch("retailedge.guided_pricing._resolve_default_price_list_candidate", return_value=None)
	@patch("retailedge.guided_pricing._assignment_price_list_scope")
	@patch("retailedge.guided_pricing._price_list_governance_policy")
	def test_multiple_assigned_lists_require_choice_when_no_default_exists(
		self, mock_policy, mock_assignment, _mock_default
	):
		mock_policy.return_value = policy()
		mock_assignment.return_value = {
			"names": ["Retail", "Wholesale"],
			"restricted": True,
			"assignment_names": ["BA-1"],
		}
		result = uncached_price_list_resolver()(
			mode="buying",
			company="Demo Company",
			branch="Lagos",
			user="buyer@example.com",
		)
		self.assertTrue(result["selection_required"])
		self.assertEqual(result["allowed_price_lists"], ["Retail", "Wholesale"])

	@patch("retailedge.guided_pricing.frappe.get_cached_value")
	@patch("retailedge.guided_pricing._erpnext_item_details", return_value=frappe._dict())
	@patch("retailedge.guided_pricing.resolve_price_list_context")
	@patch("retailedge.guided_pricing._assert_read_permission")
	def test_sales_falls_back_to_item_standard_rate(
		self, _mock_read, mock_context, _mock_details, mock_cached
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
		self, _mock_read, mock_context, _mock_details, mock_cached
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

	@patch("retailedge.guided_pricing.resolve_price_list_context")
	@patch("retailedge.guided_pricing.validate_user_branch_access")
	@patch("retailedge.guided_pricing._assert_read_permission")
	def test_whitelisted_price_context_revalidates_company_branch_and_party(
		self, mock_read, mock_branch_access, mock_resolve
	):
		mock_resolve.return_value = {"price_list": "Retail", "source": "party_default"}
		with patch.object(frappe, "session", frappe._dict(user="sales@example.com")):
			result = get_allowed_price_list_context(
				mode="selling",
				company="Demo Company",
				branch="Lagos",
				party="CUST-001",
			)
		self.assertEqual(result["price_list"], "Retail")
		mock_read.assert_any_call("Company", "Demo Company", user="sales@example.com")
		mock_read.assert_any_call("Branch", "Lagos", user="sales@example.com")
		mock_read.assert_any_call("Customer", "CUST-001", user="sales@example.com")
		mock_branch_access.assert_called_once_with(
			"Lagos",
			user="sales@example.com",
			company="Demo Company",
			throw=True,
		)

	def test_pricing_uses_erpnext_service_and_policy_governance(self):
		source = (APP_ROOT / "guided_pricing.py").read_text(encoding="utf-8")
		for contract in (
			"get_item_details",
			"get_pos_profile",
			"get_user_permissions",
			"get_retailedge_settings",
			"PRICE_SOURCE_KEYS",
			"DEFAULT_PRICE_PRECEDENCE",
			"_price_list_governance_policy",
			"_source_allows_switch",
			"selected_price_list",
			"get_branch_assignment_price_lists",
		):
			self.assertIn(contract, source)
		self.assertNotIn("ignore_permissions=True", source)

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
