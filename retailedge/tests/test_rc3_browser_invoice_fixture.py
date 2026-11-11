"""Contract tests for isolated browser Sales Invoice fixture stock attribution."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retailedge.tests.rc3_browser_fixture import _sales_invoice_values
from retailedge.tests.upgrade_validation_fixture import COMPANY


class TestRc3BrowserInvoiceFixture(unittest.TestCase):
    @patch("retailedge.tests.rc3_browser_fixture.frappe.db.get_value")
    @patch("retailedge.tests.rc3_browser_fixture._first_cost_center", return_value="Main - REU")
    @patch("retailedge.tests.rc3_browser_fixture._first_leaf_account", side_effect=["Debtors - REU", "Sales - REU"])
    @patch("retailedge.tests.rc3_browser_fixture.frappe.get_doc", return_value=SimpleNamespace(default_currency="NGN"))
    def test_saved_sale_uses_exact_branch_warehouse_on_header_and_lines(
        self, _company, _accounts, _cost_center, get_value
    ):
        get_value.return_value = "RetailEdge RC3 Lagos Stock - REU"

        payload = _sales_invoice_values("RetailEdge RC3 Lagos", "draft fixture")

        self.assertEqual(payload["set_warehouse"], "RetailEdge RC3 Lagos Stock - REU")
        self.assertEqual(payload["items"][0]["warehouse"], payload["set_warehouse"])
        self.assertEqual(payload["retailedge_branch"], "RetailEdge RC3 Lagos")
        get_value.assert_called_once_with(
            "Warehouse",
            {
                "warehouse_name": "RetailEdge RC3 Lagos Stock",
                "company": COMPANY,
                "is_group": 0,
            },
            "name",
        )

    @patch("retailedge.tests.rc3_browser_fixture.frappe.db.get_value", return_value=None)
    @patch("retailedge.tests.rc3_browser_fixture._first_cost_center", return_value="Main - REU")
    @patch("retailedge.tests.rc3_browser_fixture._first_leaf_account", side_effect=["Debtors - REU", "Sales - REU"])
    @patch("retailedge.tests.rc3_browser_fixture.frappe.get_doc", return_value=SimpleNamespace(default_currency="NGN"))
    def test_missing_branch_warehouse_fails_instead_of_using_company_stores(
        self, _company, _accounts, _cost_center, _get_value
    ):
        with self.assertRaises(frappe.ValidationError):
            _sales_invoice_values("RetailEdge RC3 Lagos", "draft fixture")
