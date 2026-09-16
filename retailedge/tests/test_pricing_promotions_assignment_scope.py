from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPricingPromotionsAssignmentScope(TestCase):
	def test_price_lists_and_item_prices_are_scoped_to_assignments(self):
		source = (APP_ROOT / "pricing_promotions_workspace.py").read_text()

		for contract in (
			"get_user_permissions",
			"get_user_pos_profiles",
			"get_exact_branch_profile",
			"get_pos_profile",
			'"Selling Price List"',
			'"Buying Price List"',
			'"POS Profile User"',
			'"selling_price_list"',
			"def _resolve_price_list_scope(",
			"def _apply_price_list_scope(",
			'if doctype == "Price List":',
			'elif doctype == "Item Price"',
			'filters["price_list"] = ["in", allowed]',
		):
			self.assertIn(contract, source)

		self.assertIn('mode = "assigned"', source)
		self.assertIn("Showing price lists assigned to your account", source)

	def test_related_pricing_records_follow_company_and_price_list_scope(self):
		source = (APP_ROOT / "pricing_promotions_workspace.py").read_text()

		for contract in (
			'"for_price_list", "Price List"',
			'"fieldname": "for_price_list"',
			"def _allowed_pricing_rule_names(",
			"def _allowed_coupon_names(",
			"def _apply_related_pricing_scope(",
			'if doctype == "Pricing Rule":',
			'elif doctype == "Coupon Code":',
			'"company_scoped": True',
		):
			self.assertIn(contract, source)

		self.assertIn("price_list not in allowed_price_lists", source)
		self.assertIn("row_company != company", source)


	def test_item_price_filter_and_write_path_use_same_scope(self):
		source = (APP_ROOT / "pricing_promotions_workspace.py").read_text()
		hooks = (APP_ROOT / "hooks.py").read_text()
		client = (APP_ROOT / "public" / "js" / "cost_visibility_doctype.js").read_text()

		for contract in (
			"def allowed_price_list_query(",
			"def validate_item_price_assignment(",
			"You do not have access to the selected Price List.",
			"not assigned to your account or current operating setup",
		):
			self.assertIn(contract, source)

		self.assertIn(
			'"validate": "retailedge.pricing_promotions_workspace.validate_item_price_assignment"',
			hooks,
		)
		self.assertIn('frappe.ui.form.on("Item Price"', client)
		self.assertIn(
			'retailedge.pricing_promotions_workspace.allowed_price_list_query',
			client,
		)

	def test_pricing_workspace_uses_assignment_options_for_item_price_filter(self):
		source = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "pricing_promotions"
			/ "PricingPromotionsWorkspace.vue"
		).read_text()

		for contract in (
			"priceListScopeMessage",
			"priceListOptions",
			"priceListFilterOptions",
			"All accessible price lists",
			"filter.type === 'price_list'",
			"workspace.price_list_scope?.message",
			"workspace.price_list_options",
		):
			self.assertIn(contract, source)

		self.assertIn(
			'frappe.route_options = { price_list: this.priceListOptions[0].value }',
			source,
		)

	def test_legacy_generic_pricing_preview_is_closed(self):
		source = (APP_ROOT / "native_visual_workspaces.py").read_text()
		self.assertIn('if workspace == "pricing-promotions":', source)
		self.assertIn(
			"Pricing & Promotions is available through its dedicated managed workspace.",
			source,
		)


	def test_system_manager_and_administrator_keep_native_management_scope(self):
		source = (APP_ROOT / "pricing_promotions_workspace.py").read_text()
		self.assertIn('user == "Administrator"', source)
		self.assertIn('"System Manager" in set(frappe.get_roles(user) or [])', source)
		self.assertIn('mode = "native"', source)


if __name__ == "__main__":
	import unittest

	unittest.main()
