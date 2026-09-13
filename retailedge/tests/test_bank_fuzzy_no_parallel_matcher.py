from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_discovery import enrich_ranked_candidates


class BankFuzzyNoParallelMatcherTests(unittest.TestCase):
    def test_helper_only_enriches_supplied_candidates(self):
        rows = enrich_ranked_candidates(
            {
                "direction": "Inflow",
                "amount": 1000,
                "ledger_account": "Bank - PED",
                "transaction_date": "2026-08-18",
                "description": "TEST",
            },
            [],
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
