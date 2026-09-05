from __future__ import annotations

import json
import unittest
from pathlib import Path

from retailedge.edgesuite_ui import NAVIGATION_GROUPS
from retailedge.master_experience import (
	PAYMENT_MANAGEMENT_ITEM,
	PROFESSIONAL_PURCHASING_ITEM,
	PROFESSIONAL_SELLING_ITEM,
	PROMOTED_R4_PAGE_TARGETS,
	SETUP_HUB_ITEM,
	TRANSACTION_WORKSPACE_ITEM,
)
from retailedge.workspace_home import HOME_WORKSPACE_ITEMS


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


def _base_item(group_key: str, label: str) -> dict:
	group = next(group for group in NAVIGATION_GROUPS if group["key"] == group_key)
	return next(item for item in group["items"] if item["label"] == label)


def _fallback_item(label: str):
	return next(item for item in HOME_WORKSPACE_ITEMS if item.label == label)


def _page_definition(directory_name: str, filename: str) -> dict:
	return json.loads((APP_ROOT / "retailedge" / "page" / directory_name / filename).read_text())


class TestRIR2B1RoutePromotionMatrixContract(unittest.TestCase):
	def test_bank_matching_b1_decision_has_advanced_to_confirmed_page_route(self):
		base = _base_item("money", "Bank Matching")
		fallback = _fallback_item("Bank Matching")

		self.assertEqual((base["target_type"], base["target"]), ("Page", "bank-matching-reconciliation"))
		self.assertEqual((fallback.link_type, fallback.link_to), ("Page", "bank-matching-reconciliation"))

		page = _page_definition(
			"bank_matching_reconciliation",
			"bank_matching_reconciliation.json",
		)
		self.assertEqual(page["name"], "bank-matching-reconciliation")
		self.assertEqual(page["standard"], "Yes")

	def test_stock_movement_history_remains_query_report_until_parity_gate(self):
		base = _base_item("stock", "Stock Movement History")
		fallback = _fallback_item("Stock Movement History")

		self.assertEqual((base["target_type"], base["target"]), ("Report", "RetailEdge Stock Movement History"))
		self.assertEqual((fallback.link_type, fallback.link_to), ("Report", "RetailEdge Stock Movement History"))

	def test_existing_page_first_operational_routes_remain_frozen(self):
		expected = {
			("home", "Business Hub"): "retailedge-business-hub",
			("buy", "Purchase Register"): "purchase-register",
			("stock", "Stock Position"): "stock-position",
			("money", "Cash Movement"): "cash-movement",
			("expenses", "Expense Register"): "expense-register",
			("customers", "Customer Receivables"): "customer-receivables",
			("suppliers-payables", "Supplier Payables"): "supplier-payables",
			("insights", "Sales by Item"): "sales-by-item",
			("insights", "Sales Invoice Register"): "sales-invoice-register",
			("insights", "Salesperson Performance"): "salesperson-performance-dashboard",
			("insights", "Branch Performance"): "branch-performance-dashboard",
			("review-approvals", "Action Centre"): "action-center",
		}
		for (group_key, label), target in expected.items():
			with self.subTest(group=group_key, label=label):
				item = _base_item(group_key, label)
				self.assertEqual(item["target_type"], "Page")
				self.assertEqual(item["target"], target)

	def test_master_experience_dynamic_promotions_are_part_of_matrix(self):
		self.assertEqual(TRANSACTION_WORKSPACE_ITEM["target"], "transaction-workspace")
		self.assertEqual(PROFESSIONAL_SELLING_ITEM["target"], "professional-selling")
		self.assertEqual(PROFESSIONAL_PURCHASING_ITEM["target"], "professional-purchasing")
		self.assertEqual(PAYMENT_MANAGEMENT_ITEM["target"], "payment-management")
		self.assertEqual(SETUP_HUB_ITEM["target"], "retailedge-setup")
		self.assertEqual(
			PROMOTED_R4_PAGE_TARGETS,
			{
				"Cashier Expense Review": "expense-review",
				"Cash Shift Verification": "cash-shift-verification",
				"Daily Sales Audit": "daily-sales-audit",
			},
		)

	def test_review_only_pages_exist_without_becoming_b1_route_promotions(self):
		base_targets = {
			(item["target_type"], item["target"])
			for group in NAVIGATION_GROUPS
			for item in group["items"]
		}
		fallback_targets = {(item.link_type, item.link_to) for item in HOME_WORKSPACE_ITEMS}

		banking_readiness = _page_definition("banking_readiness", "banking_readiness.json")
		branch_assignments = _page_definition("branch_assignments", "branch_assignments.json")
		self.assertEqual(banking_readiness["name"], "banking-readiness")
		self.assertEqual(branch_assignments["name"], "branch-assignments")
		self.assertNotIn(("Page", "banking-readiness"), base_targets)
		self.assertNotIn(("Page", "banking-readiness"), fallback_targets)
		self.assertNotIn(("Page", "branch-assignments"), base_targets)
		self.assertNotIn(("Page", "branch-assignments"), fallback_targets)

	def test_rir2b1_document_preserves_historical_promotion_and_deferred_decisions(self):
		doc = (REPO_ROOT / "docs" / "retailedge_route_promotion_matrix.md").read_text()
		self.assertIn("RIR2B1 — current route/promotion matrix freeze", doc)
		self.assertIn("PROMOTE_B2", doc)
		self.assertIn("Page: bank-matching-reconciliation", doc)
		self.assertIn("Stock Movement History", doc)
		self.assertIn("DEFER_PARITY", doc)
		self.assertIn("Do not start B4B26", doc)


if __name__ == "__main__":
	unittest.main()
