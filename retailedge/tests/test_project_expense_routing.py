from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.project_expense_routing import get_project_expense_routes


class TestProjectExpenseRouting(unittest.TestCase):
	@patch("retailedge.project_expense_routing._assert_read")
	@patch("retailedge.project_expense_routing.frappe.get_doc")
	@patch("retailedge.project_expense_routing._can_create")
	@patch("retailedge.project_expense_routing._has_field")
	def test_routes_use_native_documents_and_parent_level_project_prefill_only(
		self,
		mock_has_field,
		mock_can_create,
		mock_get_doc,
		_mock_assert_read,
	):
		mock_get_doc.return_value = SimpleNamespace(
			name="PROJ-0001",
			company="Demo Company",
			cost_center="Projects - DC",
		)
		mock_can_create.side_effect = lambda doctype: doctype in {"Purchase Invoice", "Stock Entry", "Journal Entry"}
		mock_has_field.side_effect = lambda doctype, fieldname: {
			("Purchase Invoice", "company"),
			("Purchase Invoice", "cost_center"),
			("Purchase Invoice", "project"),
			("Stock Entry", "company"),
			("Stock Entry", "project"),
			("Journal Entry", "company"),
		}.__contains__((doctype, fieldname))

		result = get_project_expense_routes("PROJ-0001")
		routes = {row["key"]: row for row in result["routes"]}

		self.assertEqual(routes["purchase-invoice"]["doctype"], "Purchase Invoice")
		self.assertEqual(routes["purchase-invoice"]["defaults"]["project"], "PROJ-0001")
		self.assertEqual(routes["purchase-invoice"]["defaults"]["cost_center"], "Projects - DC")
		self.assertEqual(routes["stock-entry"]["defaults"]["project"], "PROJ-0001")
		self.assertNotIn("project", routes["journal-entry"]["defaults"])
		self.assertIn("does not maintain a generic project expense ledger", result["policy"])

	@patch("retailedge.project_expense_routing._assert_read")
	@patch("retailedge.project_expense_routing.frappe.get_doc")
	@patch("retailedge.project_expense_routing._can_create")
	@patch("retailedge.project_expense_routing._has_field")
	def test_expense_claim_is_optional_and_does_not_fake_parent_project_field(
		self,
		mock_has_field,
		mock_can_create,
		mock_get_doc,
		_mock_assert_read,
	):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company", cost_center="")
		mock_can_create.side_effect = lambda doctype: doctype == "Expense Claim"
		mock_has_field.side_effect = lambda doctype, fieldname: (doctype, fieldname) == ("Expense Claim", "company")

		result = get_project_expense_routes("PROJ-0001")

		self.assertEqual(len(result["routes"]), 1)
		self.assertEqual(result["routes"][0]["doctype"], "Expense Claim")
		self.assertFalse(result["routes"][0]["project_prefill"])
		self.assertNotIn("project", result["routes"][0]["defaults"])


if __name__ == "__main__":
	unittest.main()
