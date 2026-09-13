from __future__ import annotations

import unittest
from unittest.mock import patch

from retailedge.banking_workspace_fuzzy import (
    _expanded_date_bounds,
    fuzzy_workspace_search_score,
    get_fuzzy_banking_workspace_rows,
)


class BankingWorkspaceFuzzyTests(unittest.TestCase):
    def test_date_bounds_expand_symmetrically_without_changing_accounting_logic(self):
        start, end = _expanded_date_bounds("2026-08-20", "2026-08-24", 3)
        self.assertEqual(str(start), "2026-08-17")
        self.assertEqual(str(end), "2026-08-27")

    def test_fuzzy_search_accepts_minor_spelling_error(self):
        row = {
            "description": "Supplier payment for veterinary consumables",
            "suggested_document": "ACC-PAY-2026-00001",
            "bank_amount": 185000,
        }
        self.assertGreaterEqual(fuzzy_workspace_search_score(row, "suplier payment"), 0.62)

    def test_fuzzy_search_does_not_accept_unrelated_text(self):
        row = {
            "description": "Supplier payment for veterinary consumables",
            "suggested_document": "ACC-PAY-2026-00001",
            "bank_amount": 185000,
        }
        self.assertLess(fuzzy_workspace_search_score(row, "customer refund lagos"), 0.62)

    def test_exact_amount_search_is_preserved(self):
        row = {
            "description": "Internal transfer",
            "bank_amount": 620000,
        }
        self.assertEqual(fuzzy_workspace_search_score(row, "620000"), 1.0)

    @patch("retailedge.banking_workspace_fuzzy.get_exact_banking_workspace_rows")
    def test_endpoint_delegates_permission_safe_filters_then_fuzzy_ranks(self, exact_rows):
        exact_rows.return_value = {
            "direction": "All",
            "queue": "To Match",
            "rows": [
                {
                    "bank_transaction": "BT-1",
                    "transaction_date": "2026-08-24",
                    "description": "Supplier payment for stock",
                    "company": "Demo",
                },
                {
                    "bank_transaction": "BT-2",
                    "transaction_date": "2026-08-23",
                    "description": "Customer receipt",
                    "company": "Demo",
                },
            ],
            "count": 2,
            "skipped_count": 0,
        }

        payload = get_fuzzy_banking_workspace_rows(
            direction="Outflow",
            queue="To Match",
            limit=100,
            company="Demo",
            bank_account="BANK-1",
            from_date="2026-08-24",
            to_date="2026-08-24",
            search="suplier paymnt",
            date_tolerance_days=3,
        )

        kwargs = exact_rows.call_args.kwargs
        self.assertEqual(kwargs["company"], "Demo")
        self.assertEqual(kwargs["bank_account"], "BANK-1")
        self.assertEqual(str(kwargs["from_date"]), "2026-08-21")
        self.assertEqual(str(kwargs["to_date"]), "2026-08-27")
        self.assertIsNone(kwargs["search"])
        self.assertEqual([row["bank_transaction"] for row in payload["rows"]], ["BT-1"])
        self.assertTrue(payload["fuzzy_search"])
        self.assertEqual(payload["date_tolerance_days"], 3)


if __name__ == "__main__":
    unittest.main()
