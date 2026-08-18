from __future__ import annotations

from typing import Any

from frappe.utils import cstr

from retailedge.bank_fuzzy_matching import build_fuzzy_match_evidence


def enrich_candidate_with_fuzzy_evidence(
    bank_transaction: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    row = dict(candidate or {})
    evidence = build_fuzzy_match_evidence(bank_transaction, row)
    row["fuzzy_evidence"] = evidence
    row["fuzzy_score"] = evidence.get("fuzzy_score", 0)
    row["fuzzy_confidence"] = evidence.get("fuzzy_confidence", "No Match")
    row["fuzzy_reference_similarity"] = evidence.get("reference_similarity", 0)
    row["fuzzy_narration_similarity"] = evidence.get("narration_similarity", 0)
    row["fuzzy_exact_reference"] = evidence.get("exact_reference", False)
    if not evidence.get("eligible"):
        row["fuzzy_block_reason"] = cstr(evidence.get("reason")).strip()
    return row


def apply_fuzzy_score_boost(candidate: dict[str, Any]) -> dict[str, Any]:
    row = dict(candidate or {})
    score = int(row.get("match_score") or 0)
    fuzzy_score = int(row.get("fuzzy_score") or 0)
    confidence = cstr(row.get("fuzzy_confidence")).strip()

    if confidence == "Strong Match":
        score += 12
    elif confidence == "Possible Match":
        score += 7
    elif confidence == "Weak Match":
        score += 3

    # Exact reference remains stronger than fuzzy narration, but never alone creates
    # eligibility because hard direction/account/amount guards ran first.
    if row.get("fuzzy_exact_reference"):
        score += 8

    row["match_score"] = min(score, 100)
    row["fuzzy_score_applied"] = fuzzy_score
    return row
