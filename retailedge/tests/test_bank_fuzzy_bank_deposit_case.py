from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import build_fuzzy_match_evidence


class BankFuzzyDepositCaseTests(unittest.TestCase):
    def test_deposit_to_bank_inflow_can_receive_fuzzy_support(self):
        evidence = build_fuzzy_match_evidence(
            {
                "direction": "Inflow",
                "amount": 450000,
                "ledger_account": "Bank - PED",
                "transaction_date": "2026-08-18",
                "description": "CASH DEPOSIT IKORODU BRANCH",
                "reference": "DEP450",
            },
            {
                "direction": "Inflow",
                "candidate_amount": 450000,
                "payment_account": "Bank - PED",
                "posting_date": "2026-08-18",
                "description": "Deposit to bank from Ikorodu branch",
                "reference_no": "DEP450",
            },
        )
        self.assertTrue(evidence["eligible"])
        self.assertEqual(evidence["fuzzy_confidence"], "Strong Match")


if __name__ == "__main__":
    unittest.main()
