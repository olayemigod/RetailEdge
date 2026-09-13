from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import (
    build_fuzzy_match_evidence,
    fuzzy_text_similarity,
    rank_fuzzy_candidates,
)


class BankFuzzyMatchingTests(unittest.TestCase):
    def _bank(self, **overrides):
        row = {
            "direction": "Inflow",
            "amount": 120000,
            "ledger_account": "Moniepoint - PED",
            "transaction_date": "2026-08-18",
            "reference": "NIP123456789",
            "description": "TRF FROM ADEBAYO JOHN INV 1045",
        }
        row.update(overrides)
        return row

    def _candidate(self, **overrides):
        row = {
            "document_name": "ACC-PAY-2026-0012",
            "direction": "Inflow",
            "candidate_amount": 120000,
            "payment_account": "Moniepoint - PED",
            "posting_date": "2026-08-18",
            "reference_no": "NIP123456789",
            "party": "Adebayo John Enterprises",
            "remarks": "Payment for invoice 1045",
        }
        row.update(overrides)
        return row

    def test_fuzzy_similarity_handles_bank_narration_noise(self):
        score = fuzzy_text_similarity(
            "TRF FROM ADEBAYO JOHN INV 1045",
            "Adebayo John Enterprises payment for invoice 1045",
        )
        self.assertGreater(score, 0.5)

    def test_exact_reference_and_matching_context_produce_strong_match(self):
        evidence = build_fuzzy_match_evidence(self._bank(), self._candidate())
        self.assertTrue(evidence["eligible"])
        self.assertEqual(evidence["fuzzy_confidence"], "Strong Match")
        self.assertTrue(evidence["exact_reference"])

    def test_direction_difference_removes_fuzzy_boost_without_rejecting_accounting_candidate(self):
        evidence = build_fuzzy_match_evidence(self._bank(), self._candidate(direction="Outflow"))
        self.assertTrue(evidence["eligible"])
        self.assertEqual(evidence["fuzzy_score"], 0)
        self.assertEqual(evidence["fuzzy_confidence"], "No Match")

    def test_raw_bank_account_identifier_difference_does_not_block_fuzzy_evidence(self):
        evidence = build_fuzzy_match_evidence(
            self._bank(), self._candidate(payment_account="GTBank - PED")
        )
        self.assertTrue(evidence["eligible"])
        self.assertGreater(evidence["fuzzy_score"], 0)

    def test_amount_difference_removes_amount_boost_but_preserves_candidate(self):
        evidence = build_fuzzy_match_evidence(
            self._bank(), self._candidate(candidate_amount=90000)
        )
        self.assertTrue(evidence["eligible"])
        self.assertFalse(evidence["amount_compatible"])

    def test_fuzzy_party_match_can_surface_possible_match_without_exact_reference(self):
        evidence = build_fuzzy_match_evidence(
            self._bank(reference=""),
            self._candidate(reference_no="", party="Adebayo John", remarks="Invoice 1045"),
        )
        self.assertTrue(evidence["eligible"])
        self.assertIn(evidence["fuzzy_confidence"], {"Strong Match", "Possible Match"})
        self.assertFalse(evidence["exact_reference"])

    def test_rank_candidates_preserves_manual_candidates_and_orders_best_text_first(self):
        ranked = rank_fuzzy_candidates(
            self._bank(),
            [
                self._candidate(document_name="PE-WEAK", reference_no="OTHER", party="Unknown Person"),
                self._candidate(document_name="PE-BEST"),
                self._candidate(document_name="PE-PARTIAL", candidate_amount=1000),
            ],
        )
        self.assertEqual(ranked[0]["document_name"], "PE-BEST")
        self.assertIn("PE-PARTIAL", [row["document_name"] for row in ranked])


if __name__ == "__main__":
    unittest.main()
