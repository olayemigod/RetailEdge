# Fuzzy matching direct integration TODO

- Import fuzzy candidate enrichment into `bank_transaction_matching.py`.
- Apply after existing candidate validity/direction/account/amount/duplicate guards.
- Preserve existing R5.11H scoring and only add bounded supporting score.
- Expose fuzzy evidence in candidate details for review/audit.
- Ensure exact reference remains stronger than narration similarity.
- Keep weak fuzzy-only matches in manual review.
