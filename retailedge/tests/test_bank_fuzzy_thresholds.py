from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import FUZZY_POSSIBLE, FUZZY_STRONG, FUZZY_WEAK


class BankFuzzyThresholdTests(unittest.TestCase):
    def test_thresholds_are_ordered_conservatively(self):
        self.assertGreater(FUZZY_STRONG, FUZZY_POSSIBLE)
        self.assertGreater(FUZZY_POSSIBLE, FUZZY_WEAK)
        self.assertGreaterEqual(FUZZY_WEAK, 0.5)


if __name__ == "__main__":
    unittest.main()
