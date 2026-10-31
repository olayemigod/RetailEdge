from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.navigation_visibility import filter_context_for_runtime_capabilities


class TestCashierNavigationProjection(unittest.TestCase):
	@patch("retailedge.navigation_visibility._page_is_functionally_available")
	def test_permission_authorized_cashier_surfaces_are_not_removed_by_persona_projection(
		self,
		page_available,
	):
		allowed_pages = {
			"cashier-my-work",
			"make-sale",
			"cashier-expenses",
			"expense-register",
			"reports-centre",
			"operating-context",
			"company-profile",
			"edge-printing",
			"document-output-sharing",
		}
		page_available.side_effect = lambda target, **_kwargs: target in allowed_pages
		context = {
			"context": {"company": "ACME", "branch": "Main"},
			"navigation_groups": [
				{
					"key": "home",
					"items": [
						{"label": "My Work", "target_type": "Page", "target": "cashier-my-work"},
					],
				},
				{
					"key": "point-of-sale",
					"items": [
						{"label": "Start POS", "target_type": "URL", "target": "/pos/"},
					],
				},
				{
					"key": "sales",
					"items": [
						{"label": "Make Sale", "target_type": "Page", "target": "make-sale"},
						{"label": "Sales Invoices", "target_type": "DocType", "target": "Sales Invoice"},
						{"label": "Document Output & Sharing", "target_type": "Page", "target": "document-output-sharing"},
						{"label": "Professional Selling", "target_type": "Page", "target": "professional-selling"},
					],
				},
				{
					"key": "expenses",
					"items": [
						{"label": "Cashier Expenses", "target_type": "Page", "target": "cashier-expenses"},
						{"label": "Expense Register", "target_type": "Page", "target": "expense-register"},
					],
				},
				{
					"key": "reports",
					"items": [
						{"label": "Reports Centre", "target_type": "Page", "target": "reports-centre"},
					],
				},
				{
					"key": "business-setup",
					"items": [
						{"label": "Operating Context", "target_type": "Page", "target": "operating-context"},
						{"label": "Company Profile", "target_type": "Page", "target": "company-profile"},
						{"label": "Devices & Printing", "target_type": "Page", "target": "edge-printing"},
					],
				},
			],
			"quick_actions": [
				{"label": "Quick Sale", "target_type": "DocType", "target": "Sales Invoice"},
			],
		}

		filtered = filter_context_for_runtime_capabilities(context)
		visible = {
			item["target"]
			for group in filtered["navigation_groups"]
			for item in group.get("items") or []
		}

		self.assertIn("cashier-my-work", visible)
		self.assertIn("/pos/", visible)
		self.assertIn("make-sale", visible)
		self.assertIn("Sales Invoice", visible)
		self.assertIn("document-output-sharing", visible)
		self.assertIn("cashier-expenses", visible)
		self.assertIn("expense-register", visible)
		self.assertIn("reports-centre", visible)
		self.assertIn("operating-context", visible)
		self.assertIn("company-profile", visible)
		self.assertIn("edge-printing", visible)
		# Professional Selling is still absent when its own Page boundary rejects the
		# cashier. Navigation presentation must not manufacture Quote/Order/Delivery
		# authority that the cashier role does not possess.
		self.assertNotIn("professional-selling", visible)
		self.assertEqual(filtered["quick_actions"][0]["target"], "Sales Invoice")

	@patch("retailedge.navigation_visibility._page_is_functionally_available")
	def test_page_capability_denial_still_removes_manager_only_surfaces(self, page_available):
		page_available.return_value = False
		context = {
			"context": {"company": "ACME", "branch": "Main"},
			"navigation_groups": [
				{
					"key": "management",
					"items": [
						{"label": "Assets", "target_type": "Page", "target": "assets-control"},
						{"label": "Warranty", "target_type": "Page", "target": "service-warranty-control"},
					],
				}
			],
			"quick_actions": [],
		}

		filtered = filter_context_for_runtime_capabilities(context)
		self.assertEqual(filtered["navigation_groups"], [])


if __name__ == "__main__":
	unittest.main()
