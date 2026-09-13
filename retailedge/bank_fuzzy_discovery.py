from __future__ import annotations

from typing import Any, Callable

from frappe.utils import cstr

from retailedge.bank_fuzzy_candidate_adapter import (
    apply_fuzzy_score_boost,
    enrich_candidate_with_fuzzy_evidence,
)


def enrich_ranked_candidates(
    bank_transaction: dict[str, Any],
    candidates: list[dict[str, Any]],
    hard_eligibility: Callable[[dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Add fuzzy evidence after the existing hard matcher has decided eligibility.

    `match_score` remains the hard accounting score. `ranking_score` is presentation-only.
    """
    output = []
    for candidate in candidates or []:
        row = dict(candidate)
        if hard_eligibility and not hard_eligibility(row):
            continue
        row = enrich_candidate_with_fuzzy_evidence(bank_transaction, row)
        row = apply_fuzzy_score_boost(row)
        output.append(row)

    output.sort(
        key=lambda row: (
            -int(row.get("ranking_score") or row.get("match_score") or 0),
            -int(row.get("hard_match_score") or row.get("match_score") or 0),
            -int(row.get("fuzzy_score") or 0),
            cstr(row.get("document_name") or row.get("suggested_document")),
        )
    )
    return output
