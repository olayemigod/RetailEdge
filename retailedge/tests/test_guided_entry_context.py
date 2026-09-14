from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.guided_entry_context import (
    get_guided_branch_names,
    get_guided_warehouse_search_filters,
    resolve_guided_branch,
    resolve_guided_company,
)


class TestGuidedEntryContext(unittest.TestCase):
    @patch("retailedge.guided_entry_context.get_operating_context", return_value={"company": "RetailEdge Consulting", "branch": "Ketu"})
    def test_active_operating_company_is_authoritative(self, _mock_context):
        self.assertEqual(resolve_guided_company(""), "RetailEdge Consulting")
        with self.assertRaises(frappe.PermissionError):
            resolve_guided_company("Other Company")

    @patch(
        "retailedge.guided_entry_context.get_operational_branch_scope",
        return_value={"restricted": True, "allowed_branches": ["Ketu", "Ikeja"]},
    )
    @patch(
        "retailedge.guided_entry_context.get_enabled_branch_profiles",
        return_value=[
            {"company": "RetailEdge Consulting", "branch": "Ketu", "enabled": 1},
            {"company": "RetailEdge Consulting", "branch": "Lekki", "enabled": 1},
        ],
    )
    def test_branch_choices_are_enabled_setup_intersected_with_operational_scope(
        self,
        _mock_profiles,
        _mock_scope,
    ):
        self.assertEqual(
            get_guided_branch_names("RetailEdge Consulting", user="retail@example.com"),
            ["Ketu"],
        )

    @patch(
        "retailedge.guided_entry_context.get_operational_branch_scope",
        return_value={"restricted": False, "allowed_branches": []},
    )
    @patch(
        "retailedge.guided_entry_context.get_enabled_branch_profiles",
        return_value=[{"company": "RetailEdge Consulting", "branch": "Ketu", "enabled": 1}],
    )
    def test_unconfigured_branch_is_rejected_even_for_unrestricted_user(
        self,
        _mock_profiles,
        _mock_scope,
    ):
        with self.assertRaises(frappe.ValidationError):
            resolve_guided_branch(
                "RetailEdge Consulting",
                "Ketu 2",
                user="manager@example.com",
            )

    @patch("retailedge.guided_entry_context.has_field", return_value=True)
    @patch(
        "retailedge.guided_entry_context.get_guided_branch_names",
        return_value=["Ketu", "Ikeja"],
    )
    def test_warehouse_search_stays_closed_until_branch_is_selected(
        self,
        _mock_branches,
        _mock_has_field,
    ):
        self.assertIsNone(
            get_guided_warehouse_search_filters(
                "RetailEdge Consulting",
                "",
                user="manager@example.com",
            )
        )

    @patch(
        "retailedge.guided_entry_context.get_first_existing_field",
        return_value="branch",
    )
    @patch("retailedge.guided_entry_context.has_field", return_value=True)
    @patch(
        "retailedge.guided_entry_context.resolve_guided_branch",
        return_value="Ketu",
    )
    @patch(
        "retailedge.guided_entry_context.get_guided_branch_names",
        return_value=["Ketu"],
    )
    def test_warehouse_filters_include_company_and_selected_branch(
        self,
        _mock_branches,
        _mock_resolve,
        _mock_has_field,
        _mock_branch_field,
    ):
        filters = get_guided_warehouse_search_filters(
            "RetailEdge Consulting",
            "Ketu",
            user="manager@example.com",
        )
        self.assertEqual(filters["company"], "RetailEdge Consulting")
        self.assertEqual(filters["branch"], "Ketu")
        self.assertEqual(filters["is_group"], 0)
        self.assertEqual(filters["disabled"], 0)


if __name__ == "__main__":
    unittest.main()
