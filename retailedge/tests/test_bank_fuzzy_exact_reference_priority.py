from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import build_fuzzy_match_evidence


class BankFuzzyExactReferencePriorityTests(unittest.TestCase):
    def test_exact_reference_is_recorded_as_distinct_strong_evidence(self):
        evidence = build_fuzzy_match_evidence(
            {
                "direction": "Inflow",
                "amount": 10000,
                "ledger_account": "Bank - PED",
                "transaction_date": "2026-08-18",
                "description": "NIP TRANSFER",
                "reference": "TXN778899",
            },
            {
                "direction": "Inflow",
                "candidate_amount": 10000,
                "payment_account": "Bank - PED",
                "posting_date": "2026-08-18",
                "party": "Unknown Customer",
                "reference_no": "TXN778899",
            },
        )
        self.assertTrue(evidence["exact_reference"])
        self.assertGreaterEqual(evidence["reference_similarity"], 1.0)


if __name__ == "__main__":
    unittest.main()
