from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.banking_link_search import search_banking_branches


class BankingLinkSearchTests(unittest.TestCase):
	@patch("retailedge.banking_link_search.get_allowed_operating_contexts")
	def test_branch_search_reuses_canonical_operating_context(self, mock_allowed):
		mock_allowed.return_value = {
			"branches": ["Abuja Branch", "Ketu Branch", "Lagos Branch"]
		}

		rows = search_banking_branches(
			txt="branch",
			company="RetailEdge Consulting",
			limit=2,
		)

		mock_allowed.assert_called_once_with(company="RetailEdge Consulting")
		self.assertEqual(
			rows,
			[
				{
					"value": "Abuja Branch",
					"label": "Abuja Branch",
					"description": "RetailEdge Consulting",
				},
				{
					"value": "Ketu Branch",
					"label": "Ketu Branch",
					"description": "RetailEdge Consulting",
				},
			],
		)

	@patch("retailedge.banking_link_search.get_allowed_operating_contexts")
	def test_branch_search_filters_text_without_assuming_branch_company_field(self, mock_allowed):
		mock_allowed.return_value = {
			"branches": ["Abuja Branch", "Ketu Branch", "Lagos Branch"]
		}

		rows = search_banking_branches(
			txt="ketu",
			company="RetailEdge Consulting",
			limit=20,
		)

		self.assertEqual(
			rows,
			[
				{
					"value": "Ketu Branch",
					"label": "Ketu Branch",
					"description": "RetailEdge Consulting",
				}
			],
		)

	@patch("retailedge.banking_link_search.get_allowed_operating_contexts")
	def test_blank_company_returns_no_branch_options(self, mock_allowed):
		self.assertEqual(search_banking_branches(txt="branch", company=""), [])
		mock_allowed.assert_not_called()


if __name__ == "__main__":
	unittest.main()
