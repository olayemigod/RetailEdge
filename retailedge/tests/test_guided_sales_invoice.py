from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.guided_sales_invoice import (
	MAX_ITEMS,
	MAX_LINK_RESULTS,
	_normalise_items,
	_validate_branch_warehouse,
	_warehouse_search_filters,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestGuidedSalesInvoice(unittest.TestCase):
	def test_normalise_items_keeps_rate_optional(self):
		rows = _normalise_items(
			[
				{"item_code": "ITEM-001", "qty": 2, "rate": ""},
				{"item_code": "ITEM-002", "qty": "3", "rate": "1500"},
			]
		)
		self.assertEqual(rows[0], {"item_code": "ITEM-001", "qty": 2.0, "rate": None})
		self.assertEqual(rows[1], {"item_code": "ITEM-002", "qty": 3.0, "rate": 1500.0})

	def test_normalise_items_rejects_invalid_business_rows(self):
		for rows in (
			[],
			[{"item_code": "", "qty": 1}],
			[{"item_code": "ITEM-001", "qty": 0}],
			[{"item_code": "ITEM-001", "qty": 1, "rate": -1}],
			[{"item_code": "ITEM-001", "qty": 1}] * (MAX_ITEMS + 1),
		):
			with self.subTest(rows=len(rows)):
				with self.assertRaises(frappe.ValidationError):
					_normalise_items(rows)

	@patch("retailedge.guided_sales_invoice.validate_user_branch_access")
	@patch("retailedge.guided_sales_invoice.get_first_existing_field", return_value="branch")
	@patch("retailedge.guided_sales_invoice.has_field", return_value=True)
	def test_warehouse_search_filters_company_and_branch_without_loading_all_rows(
		self, _mock_has_field, _mock_branch_field, mock_validate_access
	):
		filters = _warehouse_search_filters(
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
		)
		self.assertEqual(filters["company"], "Demo Company")
		self.assertEqual(filters["branch"], "Lagos")
		self.assertEqual(filters["is_group"], 0)
		mock_validate_access.assert_called_once()

	@patch("retailedge.guided_sales_invoice.get_branch_profile")
	@patch("retailedge.guided_sales_invoice.resolve_branch_from_warehouse")
	def test_branch_warehouse_mismatch_is_blocked(self, mock_resolve, mock_profile):
		mock_resolve.return_value = {"branch": "Abuja"}
		mock_profile.return_value = None
		with self.assertRaises(frappe.ValidationError):
			_validate_branch_warehouse(
				branch="Lagos",
				warehouse="Abuja Store",
				company="Demo Company",
				user="sales@example.com",
			)

	def test_adapter_uses_permission_aware_bounded_search_and_draft_insert(self):
		source = (APP_ROOT / "guided_sales_invoice.py").read_text()
		self.assertIn("search_link(", source)
		self.assertIn("MAX_LINK_RESULTS = 20", source)
		self.assertIn("min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS)", source)
		self.assertIn('query="erpnext.controllers.queries.item_query"', source)
		self.assertIn('filters: dict[str, Any] = {"is_sales_item": 1}', source)
		self.assertIn('@frappe.whitelist(methods=["POST"])', source)
		self.assertIn("doc.insert()", source)
		self.assertIn("doc.branch = branch", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("doc.submit()", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_adapter_leaves_erpnext_in_charge_of_pricing_and_accounting(self):
		source = (APP_ROOT / "guided_sales_invoice.py").read_text()
		self.assertNotIn("calculate_taxes_and_totals()", source)
		self.assertNotIn("debit_to =", source)
		self.assertNotIn("income_account", source)
		self.assertNotIn("taxes_and_charges =", source)
		self.assertNotIn("payment_schedule", source)
		self.assertIn("pricing rules, taxes, totals, due date/payment schedule, and accounts", source)

	def test_limits_are_deliberately_small_for_guided_entry(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_ITEMS, 50)


if __name__ == "__main__":
	unittest.main()
