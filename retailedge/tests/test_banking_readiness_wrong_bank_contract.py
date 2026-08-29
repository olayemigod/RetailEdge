from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from retailedge import banking_readiness


class BankingReadinessWrongBankContractTests(IntegrationTestCase):
    @patch.object(banking_readiness, "has_doctype", return_value=True)
    @patch.object(banking_readiness, "has_field", return_value=False)
    @patch.object(banking_readiness, "_mode_of_payment_context")
    @patch.object(banking_readiness, "_read_row")
    @patch.object(banking_readiness.frappe.db, "count", return_value=1)
    def test_valid_direct_bank_mapping_is_not_blocked_by_missing_mode_or_branch(
        self,
        _count,
        read_row,
        mop,
        _has_field,
        _has_doctype,
    ):
        read_row.side_effect = [
            frappe._dict(
                {
                    "name": "Access Bank Ketu - Access Bank",
                    "bank": "Access Bank",
                    "account": "Bank - RC",
                    "company": "Retail Company",
                }
            ),
            frappe._dict(
                {
                    "name": "Bank - RC",
                    "company": "Retail Company",
                    "account_type": "Bank",
                    "is_group": 0,
                }
            ),
        ]
        mop.return_value = {"configured": False, "modes": [], "conflicts": []}

        result = banking_readiness.evaluate_bank_account_readiness(
            "Access Bank Ketu - Access Bank",
            company="Retail Company",
        )

        self.assertEqual(result.get("readiness"), "Warning")
        self.assertTrue(result.get("can_reconcile"))
        warning_codes = {row.get("code") for row in result.get("warnings") or []}
        self.assertIn("mode_of_payment_default_missing", warning_codes)
        self.assertIn("branch_not_restricted", warning_codes)

    @patch.object(banking_readiness, "has_doctype", return_value=True)
    @patch.object(banking_readiness, "has_field", return_value=False)
    @patch.object(banking_readiness, "_mode_of_payment_context")
    @patch.object(banking_readiness, "_read_row")
    @patch.object(banking_readiness.frappe.db, "count", return_value=1)
    def test_wrong_company_gl_is_blocked_even_when_bank_account_exists(
        self,
        _count,
        read_row,
        mop,
        _has_field,
        _has_doctype,
    ):
        read_row.side_effect = [
            frappe._dict(
                {
                    "name": "Access Bank Ketu - Access Bank",
                    "bank": "Access Bank",
                    "account": "Bank - RC",
                    "company": "Retail Company",
                }
            ),
            frappe._dict(
                {
                    "name": "Bank - RC",
                    "company": "Another Company",
                    "account_type": "Bank",
                    "is_group": 0,
                }
            ),
        ]
        mop.return_value = {"configured": True, "modes": ["Bank Transfer"], "conflicts": []}

        result = banking_readiness.evaluate_bank_account_readiness(
            "Access Bank Ketu - Access Bank",
            company="Retail Company",
        )

        self.assertEqual(result.get("readiness"), "Blocked")
        self.assertFalse(result.get("can_reconcile"))
        issue_codes = {row.get("code") for row in result.get("issues") or []}
        self.assertIn("gl_company_mismatch", issue_codes)
        self.assertIn("requested_company_gl_mismatch", issue_codes)

    @patch.object(banking_readiness, "has_doctype", return_value=True)
    @patch.object(banking_readiness, "has_field", return_value=False)
    @patch.object(banking_readiness, "_mode_of_payment_context")
    @patch.object(banking_readiness, "_read_row")
    @patch.object(banking_readiness.frappe.db, "count", return_value=2)
    def test_ambiguous_bank_account_to_gl_mapping_is_blocked(
        self,
        _count,
        read_row,
        mop,
        _has_field,
        _has_doctype,
    ):
        read_row.side_effect = [
            frappe._dict(
                {
                    "name": "Access Bank Ketu - Access Bank",
                    "bank": "Access Bank",
                    "account": "Bank - RC",
                    "company": "Retail Company",
                }
            ),
            frappe._dict(
                {
                    "name": "Bank - RC",
                    "company": "Retail Company",
                    "account_type": "Bank",
                    "is_group": 0,
                }
            ),
        ]
        mop.return_value = {"configured": True, "modes": ["Bank Transfer"], "conflicts": []}

        result = banking_readiness.evaluate_bank_account_readiness(
            "Access Bank Ketu - Access Bank",
            company="Retail Company",
        )

        self.assertEqual(result.get("readiness"), "Blocked")
        issue_codes = {row.get("code") for row in result.get("issues") or []}
        self.assertIn("ambiguous_bank_account_mapping", issue_codes)
