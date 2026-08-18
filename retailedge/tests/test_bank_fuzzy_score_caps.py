from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_candidate_adapter import apply_fuzzy_score_boost


class BankFuzzyScoreCapTests(unittest.TestCase):
    def test_fuzzy_boost_never_exceeds_100(self):
        row = apply_fuzzy_score_boost(
            {
                "match_score": 99,
                "fuzzy_score": 100,
                "fuzzy_confidence": "Strong Match",
                "fuzzy_exact_reference": True,
            }
        )
        self.assertEqual(row["match_score"], 100)


if __name__ == "__main__":
    unittest.main()
