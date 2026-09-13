from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge import guided_purchase_invoice as purchase
from retailedge import guided_sales_invoice as sales

APP_ROOT = Path(__file__).resolve().parents[1]


class TestPrereportingInvoiceOperationalBranchScope(unittest.TestCase):
	@patch("retailedge.guided_sales_invoice._assert_read_permission")
	@patch(
		"retailedge.guided_sales_invoice.resolve_operational_branch",
		return_value={"branch": "Lagos"},
	)
	def test_sales_blank_branch_write_resolves_through_operational_scope(
		self, mock_resolve, _mock_read
	):
		company, branch, warehouse = sales._validate_transaction_context(
			{"company": "Demo Company"},
			user="sales@example.com",
		)
		self.assertEqual((company, branch, warehouse), ("Demo Company", "Lagos", ""))
		mock_resolve.assert_called_once_with(
			"Demo Company", "", user="sales@example.com"
		)

	@patch("retailedge.guided_purchase_invoice._assert_read_permission")
	@patch(
		"retailedge.guided_purchase_invoice.resolve_operational_branch",
		return_value={"branch": "Lagos"},
	)
	def test_purchase_blank_branch_write_resolves_through_operational_scope(
		self, mock_resolve, _mock_read
	):
		company, branch, warehouse = purchase._validate_transaction_context(
			{"company": "Demo Company"},
			user="buyer@example.com",
		)
		self.assertEqual((company, branch, warehouse), ("Demo Company", "Lagos", ""))
		mock_resolve.assert_called_once_with(
			"Demo Company", "", user="buyer@example.com"
		)

	@patch("retailedge.guided_sales_invoice.has_field", return_value=True)
	@patch(
		"retailedge.guided_sales_invoice.get_operational_branch_scope",
		return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": ["Lagos", "Abuja"],
			"source": "branch_assignment",
		},
	)
	def test_sales_multi_branch_warehouse_search_waits_for_branch(
		self, _mock_scope, _mock_has_field
	):
		self.assertIsNone(
			sales._warehouse_search_filters(
				company="Demo Company",
				branch="",
				user="sales@example.com",
			)
		)

	@patch("retailedge.guided_purchase_invoice.has_field", return_value=True)
	@patch(
		"retailedge.guided_purchase_invoice.get_operational_branch_scope",
		return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": ["Lagos", "Abuja"],
			"source": "branch_assignment",
		},
	)
	def test_purchase_multi_branch_warehouse_search_waits_for_branch(
		self, _mock_scope, _mock_has_field
	):
		self.assertIsNone(
			purchase._warehouse_search_filters(
				company="Demo Company",
				branch="",
				user="buyer@example.com",
			)
		)

	@patch("retailedge.guided_sales_invoice.has_field", return_value=True)
	@patch(
		"retailedge.guided_sales_invoice.get_operational_branch_scope",
		return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": [],
			"source": "branch_assignment",
		},
	)
	def test_sales_zero_branch_options_fail_closed(self, _mock_scope, _mock_has_field):
		filters = sales._branch_search_filters("Demo Company", "sales@example.com")
		self.assertEqual(filters["name"], "__never__")

	@patch("retailedge.guided_purchase_invoice.has_field", return_value=True)
	@patch(
		"retailedge.guided_purchase_invoice.get_operational_branch_scope",
		return_value={
			"company": "Demo Company",
			"restricted": True,
			"allowed_branches": [],
			"source": "branch_assignment",
		},
	)
	def test_purchase_zero_branch_options_fail_closed(self, _mock_scope, _mock_has_field):
		filters = purchase._branch_search_filters("Demo Company", "buyer@example.com")
		self.assertEqual(filters["name"], "__never__")

	@patch("retailedge.guided_sales_invoice.validate_user_branch_access")
	@patch("retailedge.guided_sales_invoice.has_branch_assignments", return_value=True)
	@patch(
		"retailedge.guided_sales_invoice.resolve_operational_branch",
		return_value={"branch": "Lagos"},
	)
	def test_sales_assignment_branch_skips_legacy_validator(
		self, mock_resolve, _mock_assignments, mock_legacy
	):
		branch = sales._resolve_guided_branch(
			company="Demo Company",
			branch="Lagos",
			user="sales@example.com",
		)
		self.assertEqual(branch, "Lagos")
		mock_resolve.assert_called_once_with(
			"Demo Company", "Lagos", user="sales@example.com"
		)
		mock_legacy.assert_not_called()

	@patch("retailedge.guided_purchase_invoice.validate_user_branch_access")
	@patch("retailedge.guided_purchase_invoice.has_branch_assignments", return_value=True)
	@patch(
		"retailedge.guided_purchase_invoice.resolve_operational_branch",
		return_value={"branch": "Lagos"},
	)
	def test_purchase_assignment_branch_skips_legacy_validator(
		self, mock_resolve, _mock_assignments, mock_legacy
	):
		branch = purchase._resolve_guided_branch(
			company="Demo Company",
			branch="Lagos",
			user="buyer@example.com",
		)
		self.assertEqual(branch, "Lagos")
		mock_resolve.assert_called_once_with(
			"Demo Company", "Lagos", user="buyer@example.com"
		)
		mock_legacy.assert_not_called()

	def test_invoice_adapters_share_the_operational_scope_contract(self):
		for path in ("guided_sales_invoice.py", "guided_purchase_invoice.py"):
			source = (APP_ROOT / path).read_text()
			self.assertIn("get_operational_branch_scope", source)
			self.assertIn("resolve_operational_branch", source)
			self.assertIn("has_branch_assignments", source)
			self.assertNotIn("ignore_permissions=True", source)
			self.assertNotIn("doc.submit()", source)
			self.assertNotIn("frappe.db.commit()", source)


if __name__ == "__main__":
	unittest.main()
