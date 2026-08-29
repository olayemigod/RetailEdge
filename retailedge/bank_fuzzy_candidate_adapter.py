from __future__ import annotations

from typing import Any

from retailedge.bank_fuzzy_matching import build_fuzzy_match_evidence


def enrich_candidate_with_fuzzy_evidence(
    bank_transaction: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    row = dict(candidate or {})
    row.setdefault("hard_match_score", int(row.get("match_score") or 0))
    evidence = build_fuzzy_match_evidence(bank_transaction, row)
    row["fuzzy_evidence"] = evidence
    row["fuzzy_score"] = evidence.get("fuzzy_score", 0)
    row["fuzzy_confidence"] = evidence.get("fuzzy_confidence", "No Match")
    row["fuzzy_reference_similarity"] = evidence.get("reference_similarity", 0)
    row["fuzzy_narration_similarity"] = evidence.get("narration_similarity", 0)
    row["fuzzy_exact_reference"] = evidence.get("exact_reference", False)
    row["fuzzy_note"] = evidence.get("reason")
    return row


def apply_fuzzy_score_boost(candidate: dict[str, Any]) -> dict[str, Any]:
    """Build a display/ranking score without changing the accounting match score.

    `match_score` remains the existing hard accounting score used by RetailEdge safety and
    auto-match rules. Fuzzy evidence can reorder candidates for an operator, but can never
    make a candidate auto-confirmable.
    """
    row = dict(candidate or {})
    hard_score = int(row.get("hard_match_score") or row.get("match_score") or 0)
    fuzzy_score = int(row.get("fuzzy_score") or 0)
    confidence = str(row.get("fuzzy_confidence") or "")

    boost = 0
    if confidence == "Strong Match":
        boost = 12
    elif confidence == "Possible Match":
        boost = 7
    elif confidence == "Weak Match":
        boost = 3
    if row.get("fuzzy_exact_reference"):
        boost += 8

    row["hard_match_score"] = hard_score
    row["match_score"] = hard_score
    row["ranking_score"] = min(hard_score + boost, 100)
    row["fuzzy_score_applied"] = fuzzy_score
    return row
