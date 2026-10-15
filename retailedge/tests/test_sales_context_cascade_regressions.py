from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from retailedge.guided_link_search import CANDIDATE_LIMIT, _sales_candidates
from retailedge.guided_pricing import _resolve_user_pos_profile


class TestSalesContextCascadeRegressions(unittest.TestCase):
	@patch("retailedge.guided_link_search.guided_sales_invoice.search_simple_sales_invoice_options")
	def test_shared_sales_search_preserves_governed_commercial_fields(self, mock_search):
		values = {
			"company": "RetailEdge Consulting",
			"branch": "Lagos Island",
			"customer": "CUST-001",
			"tax_category": "VAT",
		}
		mock_search.return_value = [{"value": "Standard VAT", "label": "Standard VAT"}]

		for fieldname in ("coupon_code", "tax_category", "taxes_and_charges"):
			with self.subTest(fieldname=fieldname):
				mock_search.reset_mock()
				result = _sales_candidates(fieldname, values, "vat")
				self.assertEqual(result, mock_search.return_value)
				mock_search.assert_called_once_with(
					fieldname,
					"vat",
					values,
					CANDIDATE_LIMIT,
				)

	@patch("retailedge.guided_pricing.get_pos_profile")
	@patch("retailedge.guided_pricing._permitted_pos_profile")
	@patch("retailedge.guided_pricing.get_exact_branch_profile")
	def test_selected_branch_uses_only_its_exact_pos_profile(
		self,
		mock_exact_profile,
		mock_permitted_pos,
		mock_global_pos,
	):
		mock_exact_profile.return_value = frappe._dict(default_pos_profile="Lagos Island POS")
		mock_permitted_pos.return_value = frappe._dict(
			name="Lagos Island POS",
			selling_price_list="Standard Selling",
			allow_rate_change=1,
		)

		result = _resolve_user_pos_profile(
			company="RetailEdge Consulting",
			branch="Lagos Island",
			user="sales@example.com",
		)

		self.assertEqual(result.name, "Lagos Island POS")
		mock_exact_profile.assert_called_once_with(
			company="RetailEdge Consulting",
			branch="Lagos Island",
			active_only=True,
		)
		mock_permitted_pos.assert_called_once_with(
			"Lagos Island POS",
			company="RetailEdge Consulting",
			user="sales@example.com",
		)
		mock_global_pos.assert_not_called()

	@patch("retailedge.guided_pricing.get_pos_profile")
	@patch("retailedge.guided_pricing.get_exact_branch_profile")
	def test_selected_branch_never_falls_back_to_another_pos_profile(
		self,
		mock_exact_profile,
		mock_global_pos,
	):
		mock_exact_profile.return_value = frappe._dict(default_pos_profile="")
		mock_global_pos.return_value = frappe._dict(name="Ketu POS Profile")

		result = _resolve_user_pos_profile(
			company="RetailEdge Consulting",
			branch="Lagos Island",
			user="sales@example.com",
		)

		self.assertIsNone(result)
		mock_global_pos.assert_not_called()

	@patch("retailedge.guided_pricing._permitted_pos_profile")
	@patch("retailedge.guided_pricing.get_pos_profile")
	@patch("retailedge.guided_pricing.frappe.has_permission", return_value=True)
	def test_branchless_pricing_retains_erpnext_pos_profile_fallback(
		self,
		_mock_permission,
		mock_global_pos,
		mock_permitted_pos,
	):
		mock_global_pos.return_value = frappe._dict(name="Ketu POS Profile")
		mock_permitted_pos.return_value = frappe._dict(name="Ketu POS Profile")

		result = _resolve_user_pos_profile(
			company="RetailEdge Consulting",
			branch="",
			user="sales@example.com",
		)

		self.assertEqual(result.name, "Ketu POS Profile")
		mock_global_pos.assert_called_once_with("RetailEdge Consulting", user="sales@example.com")
		mock_permitted_pos.assert_called_once_with(
			"Ketu POS Profile",
			company="RetailEdge Consulting",
			user="sales@example.com",
		)


if __name__ == "__main__":
	unittest.main()
