from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from frappe.utils import cstr, flt, getdate

from retailedge.bank_transaction_bridge import normalize_statement_text

FUZZY_STRONG = 0.86
FUZZY_POSSIBLE = 0.72
FUZZY_WEAK = 0.58


def _tokens(value: Any) -> list[str]:
    normalized = normalize_statement_text(value)
    if not normalized:
        return []
    raw = cstr(value).upper().replace("/", " ").replace("-", " ").replace("_", " ")
    return [token for token in raw.split() if len(token) >= 3]


def fuzzy_text_similarity(left: Any, right: Any) -> float:
    left_text = cstr(left).strip()
    right_text = cstr(right).strip()
    if not left_text or not right_text:
        return 0.0

    left_norm = normalize_statement_text(left_text)
    right_norm = normalize_statement_text(right_text)
    if left_norm == right_norm:
        return 1.0

    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = set(_tokens(left_text))
    right_tokens = set(_tokens(right_text))
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))

    containment = 0.0
    if left_norm in right_norm or right_norm in left_norm:
        containment = min(len(left_norm), len(right_norm)) / max(len(left_norm), len(right_norm))

    return max(sequence, token_score, containment)


def _days_apart(left: Any, right: Any) -> int | None:
    if not left or not right:
        return None
    try:
        return abs((getdate(left) - getdate(right)).days)
    except Exception:
        return None


def _amount_compatible(bank_amount: Any, candidate_amount: Any, tolerance: float = 0.01) -> bool:
    bank_amount = flt(bank_amount)
    candidate_amount = flt(candidate_amount)
    if bank_amount <= 0 or candidate_amount <= 0:
        return False
    return abs(bank_amount - candidate_amount) <= max(tolerance, abs(bank_amount) * 0.001)


def _fuzzy_confidence_from_percentage(score_percentage: int) -> str:
    """Return the operator-facing confidence label for the displayed fuzzy score.

    Confidence intentionally uses the same rounded percentage shown in the UI so a visible
    score of 72 cannot be labelled Weak while the published Possible threshold is 72%.
    This remains supplemental evidence only and never changes accounting eligibility.
    """
    strong_threshold = round(FUZZY_STRONG * 100)
    possible_threshold = round(FUZZY_POSSIBLE * 100)
    weak_threshold = round(FUZZY_WEAK * 100)
    if score_percentage >= strong_threshold:
        return "Strong Match"
    if score_percentage >= possible_threshold:
        return "Possible Match"
    if score_percentage >= weak_threshold:
        return "Weak Match"
    return "No Match"


def build_fuzzy_match_evidence(
    bank_transaction: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Return supplemental text/date evidence for an already-eligible accounting candidate.

    Candidate eligibility belongs to the mature RetailEdge matching engine. This helper never
    rejects a candidate for raw bank-account-string or amount differences because those values
    may represent Bank Account links vs GL Accounts, or legitimate partial/variance scenarios.
    """
    bank_direction = cstr(bank_transaction.get("direction")).strip()
    candidate_direction = cstr(candidate.get("direction") or candidate.get("expected_direction")).strip()
    if candidate_direction and bank_direction and candidate_direction != bank_direction:
        return {
            "eligible": True,
            "reason": "Direction differs; no fuzzy boost applied. Accounting eligibility remains authoritative.",
            "fuzzy_score": 0,
            "fuzzy_confidence": "No Match",
            "reference_similarity": 0,
            "narration_similarity": 0,
            "date_score": 0,
            "exact_reference": False,
        }

    bank_amount = bank_transaction.get("amount")
    candidate_amount = candidate.get("candidate_amount") or candidate.get("amount")
    amount_compatible = _amount_compatible(bank_amount, candidate_amount)

    bank_reference = bank_transaction.get("reference") or bank_transaction.get("transaction_id")
    candidate_reference = (
        candidate.get("reference")
        or candidate.get("reference_no")
        or candidate.get("transaction_id")
        or candidate.get("document_name")
    )
    reference_similarity = fuzzy_text_similarity(bank_reference, candidate_reference)

    bank_narration = bank_transaction.get("description") or bank_transaction.get("narration")
    candidate_party = candidate.get("party") or candidate.get("customer") or candidate.get("supplier")
    candidate_text = " ".join(
        part
        for part in [
            cstr(candidate_party).strip(),
            cstr(candidate.get("remarks")).strip(),
            cstr(candidate.get("description")).strip(),
            cstr(candidate_reference).strip(),
        ]
        if part
    )
    narration_similarity = fuzzy_text_similarity(bank_narration, candidate_text)

    days = _days_apart(
        bank_transaction.get("transaction_date"),
        candidate.get("posting_date") or candidate.get("date"),
    )
    date_score = (
        1.0
        if days == 0
        else 0.8
        if days == 1
        else 0.6
        if days is not None and days <= 3
        else 0.3
        if days is not None and days <= 7
        else 0.0
    )

    exact_reference = bool(reference_similarity == 1.0 and bank_reference and candidate_reference)
    text_score = max(reference_similarity, narration_similarity)
    amount_component = 0.20 if amount_compatible else 0.0
    score = amount_component + (0.25 * date_score) + (0.45 * text_score) + (0.10 if exact_reference else 0.0)
    score = min(score, 1.0)
    score_percentage = round(score * 100)
    confidence = _fuzzy_confidence_from_percentage(score_percentage)

    note = "Supplemental fuzzy evidence only; accounting eligibility and hard match score were not changed."
    if not amount_compatible:
        note += " Amount differs, so no amount similarity boost was applied."

    return {
        "eligible": True,
        "reason": note,
        "fuzzy_score": score_percentage,
        "fuzzy_confidence": confidence,
        "reference_similarity": round(reference_similarity, 4),
        "narration_similarity": round(narration_similarity, 4),
        "date_score": round(date_score, 4),
        "amount_compatible": amount_compatible,
        "exact_reference": exact_reference,
    }


def rank_fuzzy_candidates(
    bank_transaction: dict[str, Any], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ranked = []
    for candidate in candidates or []:
        evidence = build_fuzzy_match_evidence(bank_transaction, candidate)
        row = dict(candidate)
        row["fuzzy_evidence"] = evidence
        row["fuzzy_score"] = evidence.get("fuzzy_score")
        row["fuzzy_confidence"] = evidence.get("fuzzy_confidence")
        ranked.append(row)
    ranked.sort(
        key=lambda row: (-int(row.get("fuzzy_score") or 0), cstr(row.get("document_name")))
    )
    return ranked
