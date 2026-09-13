from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_matching import fuzzy_text_similarity


class BankFuzzyNarrationCasesTests(unittest.TestCase):
    def test_nip_prefix_does_not_destroy_party_similarity(self):
        self.assertGreater(
            fuzzy_text_similarity("NIP/GTB/ADEBAYO JOHN", "Adebayo John"),
            0.5,
        )

    def test_invoice_reference_embedded_in_narration_is_detectable(self):
        self.assertGreater(
            fuzzy_text_similarity("TRF INV 1045 JOHN ADEBAYO", "Invoice 1045 Adebayo John"),
            0.5,
        )

    def test_unrelated_names_have_low_similarity(self):
        self.assertLess(
            fuzzy_text_similarity("CHUKS OFFICE SUPPLIES", "Adebayo John Enterprises"),
            0.6,
        )


if __name__ == "__main__":
    unittest.main()
