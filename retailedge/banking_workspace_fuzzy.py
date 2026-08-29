from __future__ import annotations

from datetime import timedelta
import re
from typing import Any

import frappe
from frappe.utils import cint, cstr, getdate

from retailedge.bank_fuzzy_matching import fuzzy_text_similarity
from retailedge.banking_workspace import get_banking_workspace_rows as get_exact_banking_workspace_rows

DEFAULT_DATE_TOLERANCE_DAYS = 3
MAX_DATE_TOLERANCE_DAYS = 7
MAX_WORKSPACE_SCAN_ROWS = 500
FUZZY_SEARCH_THRESHOLD = 0.62
FUZZY_TOKEN_FLOOR = 0.56

SEARCH_FIELDS = (
    "bank_transaction",
    "description",
    "reference",
    "party",
    "suggested_document",
    "suggested_document_type",
    "transaction_category",
    "operational_status",
    "bank_account",
    "branch",
    "company",
    "bank_amount",
    "candidate_amount",
)


def _normalize_date_tolerance(value: Any) -> int:
    return max(0, min(cint(value if value is not None else DEFAULT_DATE_TOLERANCE_DAYS), MAX_DATE_TOLERANCE_DAYS))


def _expanded_date_bounds(from_date: Any, to_date: Any, tolerance_days: Any) -> tuple[Any, Any]:
    tolerance = _normalize_date_tolerance(tolerance_days)
    expanded_from = getdate(from_date) - timedelta(days=tolerance) if from_date else None
    expanded_to = getdate(to_date) + timedelta(days=tolerance) if to_date else None
    return expanded_from, expanded_to


def _search_values(row: dict[str, Any]) -> list[str]:
    return [
        cstr(row.get(field)).strip()
        for field in SEARCH_FIELDS
        if row.get(field) not in (None, "") and cstr(row.get(field)).strip()
    ]


def _word_tokens(value: Any) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9]+", cstr(value)) if token]


def _token_similarity(token: str, words: list[str]) -> float:
    token = cstr(token).strip().lower()
    if not token:
        return 0.0
    if token.isdigit():
        return 1.0 if any(token == word or token in word for word in words) else 0.0
    if token in words:
        return 1.0
    if any(token in word or word in token for word in words if len(word) >= 2):
        return 0.9
    comparable = [word for word in words if abs(len(word) - len(token)) <= max(3, len(token) // 2)]
    if not comparable:
        comparable = words
    return max((fuzzy_text_similarity(token, word) for word in comparable), default=0.0)


def fuzzy_workspace_search_score(row: dict[str, Any], query: Any) -> float:
    """Return discovery-only relevance for a permission-visible banking workspace row.

    This score is never used for accounting eligibility, confirmation, approval or reconciliation.
    """
    search = cstr(query).strip()
    if not search:
        return 1.0

    values = _search_values(row)
    if not values:
        return 0.0

    joined = " ".join(values)
    search_lower = search.lower()
    joined_lower = joined.lower()
    if search_lower in joined_lower:
        return 1.0

    query_tokens = _word_tokens(search)
    words = _word_tokens(joined)
    if query_tokens and words:
        token_scores = [_token_similarity(token, words) for token in query_tokens]
        if token_scores and min(token_scores) >= FUZZY_TOKEN_FLOOR:
            token_score = sum(token_scores) / len(token_scores)
        else:
            token_score = 0.0
    else:
        token_score = 0.0

    field_score = max((fuzzy_text_similarity(search, value) for value in values), default=0.0)
    return max(token_score, field_score)


def _row_sort_date(row: dict[str, Any]) -> str:
    return cstr(row.get("transaction_date")).strip()


@frappe.whitelist()
def get_fuzzy_banking_workspace_rows(
    direction: str | None = "All",
    queue: str | None = "To Match",
    limit: int | str | None = 100,
    company: str | None = None,
    branch: str | None = None,
    bank_account: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    search: str | None = None,
    date_tolerance_days: int | str | None = DEFAULT_DATE_TOLERANCE_DAYS,
) -> dict[str, Any]:
    """Return the normal banking workspace with fuzzy discovery layered on top.

    Company, branch, Bank Account, queue and direction remain exact. Date tolerance and text
    similarity only broaden the operator's discovery surface. The selected accounting candidate
    must still pass the existing exact RetailEdge review and ERPNext reconciliation gates.
    """
    requested_limit = max(1, min(cint(limit or 100), MAX_WORKSPACE_SCAN_ROWS))
    tolerance = _normalize_date_tolerance(date_tolerance_days)
    expanded_from, expanded_to = _expanded_date_bounds(from_date, to_date, tolerance)
    fuzzy_search = cstr(search).strip()
    scan_limit = (
        min(max(requested_limit * 5, 200), MAX_WORKSPACE_SCAN_ROWS)
        if fuzzy_search
        else requested_limit
    )

    payload = get_exact_banking_workspace_rows(
        direction=direction,
        queue=queue,
        limit=scan_limit,
        company=company,
        branch=branch,
        bank_account=bank_account,
        from_date=expanded_from,
        to_date=expanded_to,
        search=None,
    )
    rows = list(payload.get("rows") or [])

    if fuzzy_search:
        scored = []
        for row in rows:
            score = fuzzy_workspace_search_score(row, fuzzy_search)
            if score < FUZZY_SEARCH_THRESHOLD:
                continue
            item = dict(row)
            item["search_relevance"] = round(score * 100)
            scored.append(item)
        scored.sort(
            key=lambda row: (
                int(row.get("search_relevance") or 0),
                _row_sort_date(row),
            ),
            reverse=True,
        )
        rows = scored

    rows = rows[:requested_limit]
    result = dict(payload)
    result.update(
        {
            "rows": rows,
            "count": len(rows),
            "fuzzy_search": bool(fuzzy_search),
            "date_tolerance_days": tolerance if (from_date or to_date) else 0,
            "requested_from_date": from_date,
            "requested_to_date": to_date,
        }
    )
    return result
