from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import build_fuzzy_match_evidence


class BankFuzzyPartialAmountSafetyTests(unittest.TestCase):
    def test_material_amount_difference_does_not_remove_existing_manual_candidate(self):
        evidence = build_fuzzy_match_evidence(
            {
                "direction": "Inflow",
                "amount": 100000,
                "ledger_account": "Bank - PED",
                "transaction_date": "2026-08-18",
                "description": "ADEBAYO JOHN INV 22",
                "reference": "REF22",
            },
            {
                "direction": "Inflow",
                "candidate_amount": 90000,
                "payment_account": "Bank - PED",
                "posting_date": "2026-08-18",
                "party": "Adebayo John",
                "reference_no": "REF22",
            },
        )
        self.assertTrue(evidence["eligible"])
        self.assertFalse(evidence["amount_compatible"])
        self.assertIn("no amount similarity boost", evidence["reason"].lower())


if __name__ == "__main__":
    unittest.main()
