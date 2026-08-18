from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_candidate_adapter import apply_fuzzy_score_boost


class BankFuzzyCandidateAdapterTests(unittest.TestCase):
    def test_strong_fuzzy_evidence_boosts_existing_score_without_exceeding_100(self):
        row = apply_fuzzy_score_boost(
            {
                "match_score": 85,
                "fuzzy_score": 92,
                "fuzzy_confidence": "Strong Match",
                "fuzzy_exact_reference": True,
            }
        )
        self.assertEqual(row["match_score"], 100)

    def test_weak_fuzzy_evidence_only_adds_small_supporting_weight(self):
        row = apply_fuzzy_score_boost(
            {
                "match_score": 60,
                "fuzzy_score": 61,
                "fuzzy_confidence": "Weak Match",
                "fuzzy_exact_reference": False,
            }
        )
        self.assertEqual(row["match_score"], 63)

    def test_no_match_does_not_inflate_score(self):
        row = apply_fuzzy_score_boost(
            {
                "match_score": 40,
                "fuzzy_score": 20,
                "fuzzy_confidence": "No Match",
            }
        )
        self.assertEqual(row["match_score"], 40)


if __name__ == "__main__":
    unittest.main()
