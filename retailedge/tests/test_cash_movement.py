from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.cash_movement import (
	MAX_DATE_RANGE_DAYS,
	MAX_EXPORT_ROWS,
	MAX_LINK_RESULTS,
	MAX_PAGE_SIZE,
	_build_sql_context,
	_build_where_sql,
	_resolve_branch_scope,
	get_cash_movement,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCashMovement(unittest.TestCase):
	@patch("retailedge.cash_movement._doctype_has_field")
	def test_sql_context_uses_trusted_voucher_tables_and_classifies_transfers(self, mock_has_field):
		mock_has_field.return_value = True
		context = _build_sql_context()
		self.assertIn("`tabPayment Entry` pe", context["joins"])
		self.assertIn("`tabSales Invoice` si", context["joins"])
		self.assertIn("`tabPOS Invoice` posi", context["joins"])
		self.assertIn("`tabPurchase Invoice` pi", context["joins"])
		self.assertIn("retailedge_branch", context["branch_expression"])
		self.assertIn("Internal Transfer", context["movement_expression"])
		self.assertIn("Journal Entry", context["movement_expression"])
		self.assertNotIn("tab'Payment Entry'", context["joins"])

	def test_non_global_user_without_permitted_branches_gets_empty_sql_scope(self):
		where_sql, values = _build_where_sql(
			company="Demo Company",
			from_date=None,
			to_date=None,
			account="",
			movement_type="",
			branch_scope={"global_access": False, "effective_branches": []},
			branch_expression="COALESCE(pe.retailedge_branch, '')",
			movement_expression="'Money In'",
		)
		self.assertIn("1 = 0", where_sql)
		self.assertEqual(values[:2], ["Demo Company", "Demo Company"])

	def test_branch_scope_is_bound_as_query_values(self):
		where_sql, values = _build_where_sql(
			company="Demo Company",
			from_date=None,
			to_date=None,
			account="",
			movement_type="",
			branch_scope={
				"global_access": False,
				"effective_branches": ["Lagos", "Abuja"],
			},
			branch_expression="COALESCE(pe.retailedge_branch, '')",
			movement_expression="'Money In'",
		)
		self.assertIn("IN (%s, %s)", where_sql)
		self.assertEqual(values[-2:], ["Lagos", "Abuja"])
		self.assertNotIn("Lagos", where_sql)
		self.assertNotIn("Abuja", where_sql)

	@patch("retailedge.cash_movement.get_user_allowed_branches")
	@patch("retailedge.cash_movement.user_has_global_branch_access", return_value=False)
	def test_non_global_scope_uses_only_permitted_branches(self, _mock_global, mock_allowed):
		mock_allowed.return_value = {"branches": ["Lagos", "Abuja"]}
		with patch.object(frappe.session, "user", "manager@example.com"):
			scope = _resolve_branch_scope(company="Demo Company", requested_branch="")
		self.assertFalse(scope["global_access"])
		self.assertEqual(scope["effective_branches"], ["Abuja", "Lagos"])

	@patch("retailedge.cash_movement._prepare_query")
	@patch("retailedge.cash_movement._query_summary")
	@patch("retailedge.cash_movement._query_rows")
	def test_page_size_is_clamped_to_one_hundred(self, mock_rows, mock_summary, mock_prepare):
		mock_prepare.return_value = {
			"company": "Demo Company",
			"requested_branch": "",
			"branch_scope_label": "Company-wide",
			"includes_unattributed": True,
			"currency": "NGN",
		}
		mock_summary.return_value = {
			"movement_count": 1,
			"money_in": 100,
			"money_out": 0,
			"net_change": 100,
		}
		mock_rows.return_value = []
		result = get_cash_movement(filters={}, page=1, page_size=500)
		self.assertEqual(result["pagination"]["page_size"], MAX_PAGE_SIZE)
		mock_rows.assert_called_once_with(mock_prepare.return_value, limit=MAX_PAGE_SIZE, offset=0)

	def test_limits_are_explicit(self):
		self.assertEqual(MAX_LINK_RESULTS, 20)
		self.assertEqual(MAX_PAGE_SIZE, 100)
		self.assertEqual(MAX_EXPORT_ROWS, 5000)
		self.assertEqual(MAX_DATE_RANGE_DAYS, 366)

	def test_backend_uses_posted_gl_truth_and_bounded_payloads(self):
		source = (APP_ROOT / "cash_movement.py").read_text()
		self.assertIn("FROM `tabGL Entry` gle", source)
		self.assertIn("acc.account_type IN ('Cash', 'Bank')", source)
		self.assertIn("MAX_EXPORT_ROWS + 1", source)
		self.assertIn("MAX_DATE_RANGE_DAYS", source)
		self.assertIn("LIMIT %s OFFSET %s", source)
		self.assertIn("get_user_allowed_branches", source)
		self.assertIn("validate_user_branch_access", source)
		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("ignore_permissions=True", source)
		self.assertNotIn("frappe.db.commit()", source)

	def test_transaction_payload_omits_party_and_internal_gl_fields(self):
		source = (APP_ROOT / "cash_movement.py").read_text()
		for sensitive in (
			"party_name",
			"party_type",
			"against_voucher",
			"remarks",
			"cost_center",
			"project",
		):
			self.assertNotIn(f'"{sensitive}"', source)


if __name__ == "__main__":
	unittest.main()
