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
	def test_routes_cover_native_project_procurement_material_and_cost_lifecycle(
		self,
		mock_has_field,
		mock_can_create,
		mock_get_doc,
		_mock_assert_read,
	):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company", cost_center="Projects - DC")
		allowed = {"Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Stock Entry", "Journal Entry"}
		mock_can_create.side_effect = lambda doctype: doctype in allowed
		parent_project_doctypes = {"Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice", "Stock Entry"}
		mock_has_field.side_effect = lambda doctype, fieldname: (
			fieldname == "company"
			or (fieldname == "cost_center" and doctype in {"Purchase Invoice", "Purchase Order"})
			or (fieldname == "project" and doctype in parent_project_doctypes)
		)

		result = get_project_expense_routes("PROJ-0001")
		routes = {row["key"]: row for row in result["routes"]}

		self.assertEqual(routes["material-request"]["kind"], "procurement-planning")
		self.assertEqual(routes["purchase-order"]["kind"], "procurement-order")
		self.assertEqual(routes["purchase-receipt"]["kind"], "procurement-receipt")
		self.assertEqual(routes["purchase-invoice"]["kind"], "expense")
		self.assertEqual(routes["stock-entry"]["kind"], "stock")
		for key in ("material-request", "purchase-order", "purchase-receipt", "purchase-invoice", "stock-entry"):
			self.assertEqual(routes[key]["defaults"]["project"], "PROJ-0001")
			self.assertEqual(routes[key]["project_link_scope"], "parent")
		self.assertNotIn("project", routes["journal-entry"]["defaults"])
		self.assertEqual(routes["journal-entry"]["project_link_scope"], "native-document")
		self.assertIn("does not maintain a generic project expense or procurement ledger", result["policy"])

	@patch("retailedge.project_expense_routing._assert_read")
	@patch("retailedge.project_expense_routing.frappe.get_doc")
	@patch("retailedge.project_expense_routing._can_create")
	@patch("retailedge.project_expense_routing._has_field")
	def test_unavailable_or_unpermitted_native_routes_are_not_exposed(
		self,
		mock_has_field,
		mock_can_create,
		mock_get_doc,
		_mock_assert_read,
	):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company", cost_center="")
		mock_can_create.side_effect = lambda doctype: doctype in {"Purchase Order", "Stock Entry"}
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname in {"company", "project"}

		result = get_project_expense_routes("PROJ-0001")
		doctypes = [row["doctype"] for row in result["routes"]]

		self.assertEqual(doctypes, ["Purchase Order", "Stock Entry"])
		self.assertNotIn("Material Request", doctypes)
		self.assertNotIn("Purchase Invoice", doctypes)

	@patch("retailedge.project_expense_routing._assert_read")
	@patch("retailedge.project_expense_routing.frappe.get_doc")
	@patch("retailedge.project_expense_routing._can_create")
	@patch("retailedge.project_expense_routing._has_field")
	def test_missing_parent_project_field_does_not_fake_project_prefill(
		self,
		mock_has_field,
		mock_can_create,
		mock_get_doc,
		_mock_assert_read,
	):
		mock_get_doc.return_value = SimpleNamespace(name="PROJ-0001", company="Demo Company", cost_center="")
		mock_can_create.side_effect = lambda doctype: doctype == "Purchase Receipt"
		mock_has_field.side_effect = lambda doctype, fieldname: fieldname == "company"

		result = get_project_expense_routes("PROJ-0001")
		route = result["routes"][0]

		self.assertFalse(route["project_prefill"])
		self.assertEqual(route["project_link_scope"], "native-document")
		self.assertNotIn("project", route["defaults"])

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

	def test_router_never_posts_or_bypasses_native_permissions(self):
		source = __import__("pathlib").Path(__file__).resolve().parents[1] / "project_expense_routing.py"
		text = source.read_text()
		self.assertNotIn("frappe.new_doc(", text)
		self.assertNotIn(".insert(", text)
		self.assertNotIn(".submit(", text)
		self.assertNotIn("ignore_permissions=True", text)


if __name__ == "__main__":
	unittest.main()
