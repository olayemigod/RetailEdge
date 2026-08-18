from __future__ import annotations

import unittest

from retailedge.bank_fuzzy_candidate_adapter import enrich_candidate_with_fuzzy_evidence


class BankFuzzyAuditPayloadTests(unittest.TestCase):
    def test_candidate_exposes_fuzzy_evidence_for_review_audit(self):
        row = enrich_candidate_with_fuzzy_evidence(
            {
                "direction": "Inflow",
                "amount": 50000,
                "ledger_account": "Bank - PED",
                "transaction_date": "2026-08-18",
                "description": "NIP FROM ADEBAYO JOHN",
                "reference": "ABC1234",
            },
            {
                "document_name": "PE-1",
                "direction": "Inflow",
                "candidate_amount": 50000,
                "payment_account": "Bank - PED",
                "posting_date": "2026-08-18",
                "party": "Adebayo John",
                "reference_no": "ABC1234",
            },
        )
        self.assertIn("fuzzy_evidence", row)
        self.assertIn("reference_similarity", row["fuzzy_evidence"])
        self.assertIn("narration_similarity", row["fuzzy_evidence"])


if __name__ == "__main__":
    unittest.main()
