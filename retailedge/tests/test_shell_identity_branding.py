from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.company_profile import get_shell_identity


class TestRetailEdgeShellIdentityBranding(unittest.TestCase):
	@patch("retailedge.company_profile.can_use_company_wide_branch_view", return_value=False)
	@patch("retailedge.company_profile.get_allowed_operating_branches", return_value=["Ketu"])
	@patch(
		"retailedge.company_profile.resolve_company_profile",
		return_value={
			"label": "RetailEdge Consulting Limited",
			"logo": "/files/retailedge-consulting-logo.png",
		},
	)
	@patch(
		"retailedge.company_profile.get_operating_context",
		return_value={"company": "RetailEdge Consulting Limited", "branch": "Ketu"},
	)
	def test_shell_identity_separates_product_and_company_branding(
		self,
		_operating_context,
		_profile,
		_branches,
		_company_wide,
	):
		identity = get_shell_identity()

		self.assertEqual(identity["product_name"], "ProcessEdge Retail")
		self.assertEqual(
			identity["product_logo"],
			"/assets/retailedge/images/processedge_retail/processedge-retail-mark.svg",
		)
		self.assertEqual(identity["tenant_name"], "RetailEdge Consulting Limited")
		self.assertEqual(identity["tenant_logo"], "/files/retailedge-consulting-logo.png")
		self.assertEqual(
			identity["companies"],
			{
				"RetailEdge Consulting Limited": {
					"label": "RetailEdge Consulting Limited",
					"logo": "/files/retailedge-consulting-logo.png",
				}
			},
		)


if __name__ == "__main__":
	unittest.main()
