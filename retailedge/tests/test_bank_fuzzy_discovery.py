from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_discovery import enrich_ranked_candidates


class BankFuzzyDiscoveryTests(unittest.TestCase):
    def _bank(self):
        return {
            "direction": "Inflow",
            "amount": 100000,
            "ledger_account": "Bank - PED",
            "transaction_date": "2026-08-18",
            "description": "NIP FROM JOHN ADEBAYO INV 22",
            "reference": "REF-22",
        }

    def test_existing_hard_eligibility_runs_before_fuzzy_scoring(self):
        rows = enrich_ranked_candidates(
            self._bank(),
            [
                {
                    "document_name": "PE-1",
                    "direction": "Inflow",
                    "candidate_amount": 100000,
                    "payment_account": "Bank - PED",
                    "posting_date": "2026-08-18",
                    "party": "John Adebayo",
                    "match_score": 70,
                },
                {
                    "document_name": "PE-BLOCK",
                    "direction": "Inflow",
                    "candidate_amount": 100000,
                    "payment_account": "Bank - PED",
                    "posting_date": "2026-08-18",
                    "party": "John Adebayo",
                    "match_score": 99,
                    "blocked": True,
                },
            ],
            hard_eligibility=lambda row: not row.get("blocked"),
        )
        self.assertEqual([row["document_name"] for row in rows], ["PE-1"])

    def test_fuzzy_signal_reorders_candidates_with_same_base_score(self):
        rows = enrich_ranked_candidates(
            self._bank(),
            [
                {
                    "document_name": "PE-OTHER",
                    "direction": "Inflow",
                    "candidate_amount": 100000,
                    "payment_account": "Bank - PED",
                    "posting_date": "2026-08-18",
                    "party": "Unknown Limited",
                    "reference_no": "OTHER",
                    "match_score": 60,
                },
                {
                    "document_name": "PE-JOHN",
                    "direction": "Inflow",
                    "candidate_amount": 100000,
                    "payment_account": "Bank - PED",
                    "posting_date": "2026-08-18",
                    "party": "John Adebayo",
                    "reference_no": "REF-22",
                    "match_score": 60,
                },
            ],
        )
        self.assertEqual(rows[0]["document_name"], "PE-JOHN")
        self.assertGreater(rows[0]["fuzzy_score"], rows[1]["fuzzy_score"])


if __name__ == "__main__":
    unittest.main()
