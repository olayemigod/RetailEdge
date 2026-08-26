from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import build_fuzzy_match_evidence


class BankFuzzyDirectionCasesTests(unittest.TestCase):
    def test_outflow_expense_can_receive_fuzzy_support(self):
        evidence = build_fuzzy_match_evidence(
            {
                "direction": "Outflow",
                "amount": 75000,
                "ledger_account": "Bank - PED",
                "transaction_date": "2026-08-18",
                "description": "NIP CHUKS OFFICE SUPPLIES",
                "reference": "EXP7788",
            },
            {
                "direction": "Outflow",
                "candidate_amount": 75000,
                "payment_account": "Bank - PED",
                "posting_date": "2026-08-18",
                "party": "Chuks Office Supplies Ltd",
                "reference_no": "EXP7788",
            },
        )
        self.assertTrue(evidence["eligible"])
        self.assertEqual(evidence["fuzzy_confidence"], "Strong Match")


if __name__ == "__main__":
    unittest.main()
