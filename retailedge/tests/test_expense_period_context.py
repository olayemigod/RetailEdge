from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge import expense_period_context as context


class TestExpensePeriodContext(unittest.TestCase):
	@patch.object(context, "require_dashboard_action")
	@patch.object(context, "get_expense_register_export")
	@patch.object(context.frappe.defaults, "get_user_default", return_value="Demo Company")
	def test_mtd_and_calendar_ytd_anchor_to_selected_to_date(self, _default, export, _capability):
		export.side_effect = [
			{"rows": [{"expense_category": "Fuel", "amount": 100}, {"expense_category": "Fuel", "amount": 50}]},
			{"rows": [{"expense_category": "Fuel", "amount": 300}, {"expense_category": "Rent", "amount": 700}]},
		]
		result = context.get_expense_period_context(
			{"company": "Demo Company", "branch": "Lagos", "to_date": "2026-08-19", "expense_status": "Posted"}
		)
		self.assertEqual(result["mtd"]["from_date"], "2026-08-01")
		self.assertEqual(result["mtd"]["to_date"], "2026-08-19")
		self.assertEqual(result["mtd"]["total_expenses"], 150)
		self.assertEqual(result["ytd"]["from_date"], "2026-01-01")
		self.assertEqual(result["ytd"]["to_date"], "2026-08-19")
		self.assertEqual(result["ytd"]["total_expenses"], 1000)
		self.assertEqual(result["metadata"]["ytd_basis"], "calendar_year")
		for call in export.call_args_list:
			filters = call.args[0]
			self.assertEqual(filters["company"], "Demo Company")
			self.assertEqual(filters["branch"], "Lagos")
			self.assertEqual(filters["expense_status"], "Posted")

	def test_top_categories_are_ranked_and_bounded(self):
		rows = [
			{"expense_category": "Fuel", "amount": 30},
			{"expense_category": "Rent", "amount": 100},
			{"expense_category": "Fuel", "amount": 80},
		]
		result = context._top_categories(rows)
		self.assertEqual(result[0]["label"], "Fuel")
		self.assertEqual(result[0]["amount"], 110)
		self.assertEqual(result[0]["count"], 2)


if __name__ == "__main__":
	unittest.main()
