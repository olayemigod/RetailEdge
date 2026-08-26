from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from retailedge.banking_link_search import search_banking_branches


class BankingLinkSearchTests(unittest.TestCase):
	@patch("retailedge.banking_link_search.frappe.get_all")
	@patch("retailedge.banking_link_search.frappe.get_list")
	@patch("retailedge.banking_link_search.frappe.get_doc")
	def test_branch_search_keeps_company_boundary_without_filtering_restricted_field(
		self, mock_get_doc, mock_get_list, mock_get_all
	):
		company_doc = Mock()
		mock_get_doc.return_value = company_doc
		mock_get_list.return_value = [
			SimpleNamespace(name="Abuja Branch"),
			SimpleNamespace(name="Ketu Branch"),
			SimpleNamespace(name="Lagos Branch"),
		]
		mock_get_all.return_value = [
			SimpleNamespace(name="Ketu Branch"),
			SimpleNamespace(name="Lagos Branch"),
		]

		rows = search_banking_branches(txt="br", company="RetailEdge Consulting", limit=100)

		mock_get_doc.assert_called_once_with("Company", "RetailEdge Consulting")
		company_doc.check_permission.assert_called_once_with("read")
		mock_get_list.assert_called_once_with(
			"Branch",
			filters={"name": ["like", "%br%"]},
			fields=["name"],
			order_by="name asc",
			limit_start=0,
			limit_page_length=100,
		)
		mock_get_all.assert_called_once_with(
			"Branch",
			filters={
				"name": ["in", ["Abuja Branch", "Ketu Branch", "Lagos Branch"]],
				"company": "RetailEdge Consulting",
			},
			fields=["name"],
		)
		self.assertEqual(
			rows,
			[
				{"value": "Ketu Branch", "label": "Ketu Branch", "description": "RetailEdge Consulting"},
				{"value": "Lagos Branch", "label": "Lagos Branch", "description": "RetailEdge Consulting"},
			],
		)

	@patch("retailedge.banking_link_search.frappe.get_all")
	@patch("retailedge.banking_link_search.frappe.get_list")
	@patch("retailedge.banking_link_search.frappe.get_doc")
	def test_blank_company_returns_no_branch_options(self, mock_get_doc, mock_get_list, mock_get_all):
		self.assertEqual(search_banking_branches(txt="branch", company=""), [])
		mock_get_doc.assert_not_called()
		mock_get_list.assert_not_called()
		mock_get_all.assert_not_called()


if __name__ == "__main__":
	unittest.main()
