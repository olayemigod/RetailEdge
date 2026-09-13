from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge import guided_purchase_invoice as purchase
from retailedge import guided_sales_invoice as sales

APP_ROOT = Path(__file__).resolve().parents[1]


class TestPrereportingInvoiceOperationalBranchScope(unittest.TestCase):
	def test_sales_blank_branch_write_resolves_through_shared_guided_scope(self):
		with (
			patch.object(sales, "resolve_guided_company", return_value="Demo Company"),
			patch.object(sales, "resolve_guided_branch", return_value="Lagos") as mock_resolve,
			patch.object(sales, "get_guided_branch_names", return_value=["Lagos"]),
			patch.object(sales, "_assert_read_permission"),
		):
			company, branch, warehouse = sales._validate_transaction_context(
				{"company": "Demo Company"},
				user="sales@example.com",
			)
		self.assertEqual((company, branch, warehouse), ("Demo Company", "Lagos", ""))
		mock_resolve.assert_called_once_with(
			"Demo Company", "", user="sales@example.com"
		)

	def test_purchase_blank_branch_write_resolves_through_shared_guided_scope(self):
		with (
			patch.object(purchase, "resolve_guided_company", return_value="Demo Company"),
			patch.object(purchase, "resolve_guided_branch", return_value="Lagos") as mock_resolve,
			patch.object(purchase, "get_guided_branch_names", return_value=["Lagos"]),
			patch.object(purchase, "_assert_read_permission"),
		):
			company, branch, warehouse = purchase._validate_transaction_context(
				{"company": "Demo Company"},
				user="buyer@example.com",
			)
		self.assertEqual((company, branch, warehouse), ("Demo Company", "Lagos", ""))
		mock_resolve.assert_called_once_with(
			"Demo Company", "", user="buyer@example.com"
		)

	def test_sales_multi_branch_warehouse_search_waits_for_branch(self):
		with patch.object(
			sales,
			"get_guided_warehouse_search_filters",
			return_value=None,
		) as mock_filters:
			self.assertIsNone(
				sales._warehouse_search_filters(
					company="Demo Company",
					branch="",
					user="sales@example.com",
				)
			)
		mock_filters.assert_called_once_with(
			"Demo Company", "", user="sales@example.com"
		)

	def test_purchase_multi_branch_warehouse_search_waits_for_branch(self):
		with patch.object(
			purchase,
			"get_guided_warehouse_search_filters",
			return_value=None,
		) as mock_filters:
			self.assertIsNone(
				purchase._warehouse_search_filters(
					company="Demo Company",
					branch="",
					user="buyer@example.com",
				)
			)
		mock_filters.assert_called_once_with(
			"Demo Company", "", user="buyer@example.com"
		)

	def test_sales_zero_branch_options_fail_closed(self):
		with patch.object(
			sales,
			"get_guided_branch_search_filters",
			return_value={"name": "__never__"},
		) as mock_filters:
			filters = sales._branch_search_filters("Demo Company", "sales@example.com")
		self.assertEqual(filters["name"], "__never__")
		mock_filters.assert_called_once_with(
			"Demo Company", user="sales@example.com"
		)

	def test_purchase_zero_branch_options_fail_closed(self):
		with patch.object(
			purchase,
			"get_guided_branch_search_filters",
			return_value={"name": "__never__"},
		) as mock_filters:
			filters = purchase._branch_search_filters("Demo Company", "buyer@example.com")
		self.assertEqual(filters["name"], "__never__")
		mock_filters.assert_called_once_with(
			"Demo Company", user="buyer@example.com"
		)

	def test_sales_explicit_branch_delegates_to_shared_guided_resolver(self):
		with patch.object(sales, "resolve_guided_branch", return_value="Lagos") as mock_resolve:
			branch = sales._resolve_guided_branch(
				company="Demo Company",
				branch="Lagos",
				user="sales@example.com",
			)
		self.assertEqual(branch, "Lagos")
		mock_resolve.assert_called_once_with(
			"Demo Company", "Lagos", user="sales@example.com"
		)

	def test_purchase_explicit_branch_delegates_to_shared_guided_resolver(self):
		with patch.object(purchase, "resolve_guided_branch", return_value="Lagos") as mock_resolve:
			branch = purchase._resolve_guided_branch(
				company="Demo Company",
				branch="Lagos",
				user="buyer@example.com",
			)
		self.assertEqual(branch, "Lagos")
		mock_resolve.assert_called_once_with(
			"Demo Company", "Lagos", user="buyer@example.com"
		)

	def test_invoice_adapters_share_the_guided_operational_scope_contract(self):
		for path in ("guided_sales_invoice.py", "guided_purchase_invoice.py"):
			source = (APP_ROOT / path).read_text()
			for contract in (
				"resolve_guided_company",
				"resolve_guided_branch",
				"get_guided_branch_names",
				"get_guided_branch_search_filters",
				"get_guided_warehouse_search_filters",
				"validate_guided_branch_warehouse",
			):
				self.assertIn(contract, source)
			self.assertNotIn("ignore_permissions=True", source)
			self.assertNotIn("doc.submit()", source)
			self.assertNotIn("frappe.db.commit()", source)

		shared = (APP_ROOT / "guided_entry_context.py").read_text()
		for contract in (
			"get_operational_branch_scope",
			"resolve_operational_branch",
			"get_enabled_branch_profiles",
			"resolve_guided_company",
		):
			self.assertIn(contract, shared)


if __name__ == "__main__":
	unittest.main()
