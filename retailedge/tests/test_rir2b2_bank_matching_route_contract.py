from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.edgesuite_ui import NAVIGATION_GROUPS, _get_permitted_navigation_groups
from retailedge.workspace_home import HOME_WORKSPACE_ITEMS


APP_ROOT = Path(__file__).resolve().parents[1]


def _base_item(group_key: str, label: str) -> dict:
	group = next(group for group in NAVIGATION_GROUPS if group["key"] == group_key)
	return next(item for item in group["items"] if item["label"] == label)


def _fallback_item(label: str):
	return next(item for item in HOME_WORKSPACE_ITEMS if item.label == label)


def _pos_capabilities() -> SimpleNamespace:
	return SimpleNamespace(
		provider="erpnext",
		start_link_type=None,
		start_target=None,
		start_url=None,
		opening_doctype=None,
		closing_doctype=None,
	)


class TestRIR2B2BankMatchingRouteContract(unittest.TestCase):
	def test_primary_and_compact_fallback_routes_use_reconciliation_page(self):
		base = _base_item("money", "Bank Matching")
		fallback = _fallback_item("Bank Matching")

		self.assertEqual((base["target_type"], base["target"]), ("Page", "bank-matching-reconciliation"))
		self.assertEqual((fallback.link_type, fallback.link_to), ("Page", "bank-matching-reconciliation"))

	def test_reconciliation_page_keeps_expected_operational_roles(self):
		path = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "bank_matching_reconciliation"
			/ "bank_matching_reconciliation.json"
		)
		page = json.loads(path.read_text())
		roles = {row["role"] for row in page.get("roles") or []}

		self.assertEqual(page["name"], "bank-matching-reconciliation")
		self.assertEqual(page["standard"], "Yes")
		self.assertTrue(
			{
				"Accounts Manager",
				"Accounts User",
				"RetailEdge Manager",
				"RetailEdge Branch Manager",
			}.issubset(roles)
		)

	def test_business_hub_includes_bank_matching_only_when_page_is_permitted(self):
		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=True),
			patch("retailedge.edgesuite_ui._has_permission", return_value=True),
			patch(
				"retailedge.edgesuite_ui._can_open_page",
				side_effect=lambda page_name: page_name == "bank-matching-reconciliation",
			),
			patch("retailedge.edgesuite_ui._can_open_report", return_value=True),
		):
			groups = _get_permitted_navigation_groups(
				{"Accounts User"},
				pos_capabilities=_pos_capabilities(),
			)

		money = next(group for group in groups if group["key"] == "money")
		bank_matching = next(item for item in money["items"] if item["label"] == "Bank Matching")
		self.assertEqual(bank_matching["target_type"], "Page")
		self.assertEqual(bank_matching["target"], "bank-matching-reconciliation")

	def test_business_hub_omits_bank_matching_when_page_permission_denies_access(self):
		with (
			patch("retailedge.edgesuite_ui._target_exists", return_value=True),
			patch("retailedge.edgesuite_ui._has_permission", return_value=True),
			patch("retailedge.edgesuite_ui._can_open_page", return_value=False),
			patch("retailedge.edgesuite_ui._can_open_report", return_value=True),
		):
			groups = _get_permitted_navigation_groups(
				{"Accounts User"},
				pos_capabilities=_pos_capabilities(),
			)

		money = next(group for group in groups if group["key"] == "money")
		self.assertNotIn("Bank Matching", {item["label"] for item in money["items"]})

	def test_legacy_matching_report_remains_available_as_advanced_fallback_asset(self):
		path = (
			APP_ROOT
			/ "retailedge"
			/ "report"
			/ "retailedge_bank_transaction_matching"
			/ "retailedge_bank_transaction_matching.json"
		)
		report = json.loads(path.read_text())
		self.assertEqual(report["name"], "RetailEdge Bank Transaction Matching")
		self.assertEqual(report["report_type"], "Script Report")

	def test_stock_movement_history_is_not_promoted_by_b2(self):
		base = _base_item("stock", "Stock Movement History")
		fallback = _fallback_item("Stock Movement History")
		self.assertEqual((base["target_type"], base["target"]), ("Report", "RetailEdge Stock Movement History"))
		self.assertEqual((fallback.link_type, fallback.link_to), ("Report", "RetailEdge Stock Movement History"))


if __name__ == "__main__":
	unittest.main()
