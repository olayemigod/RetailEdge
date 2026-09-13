# Bank Fuzzy Matching Integration Notes

This temporary implementation note documents the intended integration boundary for the bank matching engine while PR #24 is in development.

Fuzzy evidence is supplemental. Candidate discovery must first enforce direction, bank-account compatibility, amount compatibility, document validity, active-match conflict checks, and accounting safety. Only candidates surviving those guards may receive fuzzy narration, party, reference, or identifier scoring.

The fuzzy layer is intended to support noisy Nigerian bank narrations such as NIP transfer prefixes, abbreviated customer/supplier names, truncated references, inconsistent spacing, and invoice references embedded inside narration. Exact references remain stronger evidence than fuzzy text.

The integration target is the existing RetailEdge candidate-building/scoring path in `bank_transaction_matching.py`; the standalone scorer and adapter should not become a parallel matcher.
