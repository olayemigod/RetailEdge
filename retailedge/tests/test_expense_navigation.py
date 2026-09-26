from __future__ import annotations

import unittest

from retailedge.edgesuite_ui import NAVIGATION_GROUPS


class TestExpenseNavigation(unittest.TestCase):
	def test_expenses_group_owns_business_register_cashier_expenses_and_categories(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		expense_items = [(item["label"], item["target_type"], item["target"]) for item in groups["expenses"]["items"]]
		self.assertEqual(
			expense_items,
			[
				("Business Expenses", "Page", "business-expenses"),
				("Expense Register", "Page", "expense-register"),
				("Cashier Expenses", "Page", "cashier-expenses"),
				("Expense Categories", "DocType", "RetailEdge Expense Category"),
			],
		)

	def test_cashier_expenses_and_review_are_edgesuite_pages(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		expenses = {item["label"]: item for item in groups["expenses"]["items"]}
		reviews = {item["label"]: item for item in groups["review-approvals"]["items"]}
		self.assertEqual(expenses["Cashier Expenses"]["target_type"], "Page")
		self.assertEqual(expenses["Cashier Expenses"]["target"], "cashier-expenses")
		self.assertEqual(reviews["Cashier Expense Review"]["target_type"], "Page")
		self.assertEqual(reviews["Cashier Expense Review"]["target"], "expense-review")

	def test_expense_categories_are_not_duplicated_in_setup(self):
		groups = {group["key"]: group for group in NAVIGATION_GROUPS}
		setup_targets = {item["target"] for item in groups["setup"]["items"]}
		self.assertNotIn("RetailEdge Expense Category", setup_targets)


if __name__ == "__main__":
	unittest.main()
