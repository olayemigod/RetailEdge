from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint, cstr, getdate

from retailedge.banking_operations import (
    CATEGORY_UNCLASSIFIED,
    DIRECTION_ALL,
    STATUS_EXCEPTION,
    STATUS_NEEDS_REVIEW,
    STATUS_PAYMENT_EVIDENCE_REQUIRED,
    STATUS_READY_TO_RECONCILE,
    STATUS_RECONCILED,
    STATUS_RECONCILIATION_FAILED,
    STATUS_RECONCILIATION_PENDING,
    STATUS_SUGGESTED,
    STATUS_UNMATCHED,
    get_bank_match_operational_status,
    normalize_direction,
)
from retailedge.bank_transaction_matching import (
    INACTIVE_MATCH_STATUSES,
    assert_can_access_bank_transaction_matching,
    normalize_bank_transaction,
)

QUEUE_TO_MATCH = "To Match"
QUEUE_TO_RECONCILE = "To Reconcile"
QUEUE_EXCEPTIONS = "Exceptions"
QUEUE_RECONCILED = "Reconciled"
VALID_QUEUES = {QUEUE_TO_MATCH, QUEUE_TO_RECONCILE, QUEUE_EXCEPTIONS, QUEUE_RECONCILED}

SCAN_CHUNK_SIZE = 100
MAX_SCAN_ROWS = 5000


def _normalize_queue(queue: str | None) -> str:
    queue = cstr(queue or QUEUE_TO_MATCH).strip()
    if queue not in VALID_QUEUES:
        frappe.throw(f"Unsupported banking queue: {queue}")
    return queue


def _status_belongs_to_queue(status: str, queue: str) -> bool:
    if queue == QUEUE_TO_MATCH:
        return status in {STATUS_UNMATCHED, STATUS_SUGGESTED}
    if queue == QUEUE_TO_RECONCILE:
        return status in {STATUS_READY_TO_RECONCILE, STATUS_RECONCILIATION_PENDING}
    if queue == QUEUE_EXCEPTIONS:
        return status in {
            STATUS_NEEDS_REVIEW,
            STATUS_PAYMENT_EVIDENCE_REQUIRED,
            STATUS_EXCEPTION,
            STATUS_RECONCILIATION_FAILED,
        }
    if queue == QUEUE_RECONCILED:
        return status == STATUS_RECONCILED
    return False


def _matches_filters(row: dict[str, Any], filters: frappe._dict) -> bool:
    if filters.company and cstr(row.get("company")).strip() != cstr(filters.company).strip():
        return False
    if filters.branch and cstr(row.get("branch")).strip() != cstr(filters.branch).strip():
        return False
    if filters.bank_account and cstr(row.get("bank_account")).strip() != cstr(filters.bank_account).strip():
        return False
    if filters.from_date and row.get("transaction_date"):
        if getdate(row.get("transaction_date")) < getdate(filters.from_date):
            return False
    if filters.to_date and row.get("transaction_date"):
        if getdate(row.get("transaction_date")) > getdate(filters.to_date):
            return False
    search = cstr(filters.search).strip().lower()
    if search:
        haystack = " ".join(
            cstr(row.get(key)).strip()
            for key in (
                "bank_transaction",
                "description",
                "reference",
                "party",
                "suggested_document",
                "suggested_document_type",
                "bank_amount",
                "candidate_amount",
            )
            if row.get(key) not in (None, "")
        ).lower()
        if search not in haystack:
            return False
    return True


def _get_active_match_bank_transactions(bank_transaction_names: list[str]) -> set[str]:
    if not bank_transaction_names:
        return set()
    rows = frappe.get_list(
        "RetailEdge Bank Transaction Match",
        filters={
            "bank_transaction": ["in", bank_transaction_names],
            "decision_status": ["not in", list(INACTIVE_MATCH_STATUSES)],
        },
        fields=["bank_transaction"],
        limit_page_length=len(bank_transaction_names),
    )
    return {cstr(row.bank_transaction).strip() for row in rows if row.bank_transaction}


def _unmatched_db_filters(filters: frappe._dict) -> dict[str, Any]:
    db_filters: dict[str, Any] = {"docstatus": 1, "unallocated_amount": [">", 0]}
    if filters.company:
        db_filters["company"] = filters.company
    if filters.bank_account:
        db_filters["bank_account"] = filters.bank_account
    if filters.from_date and filters.to_date:
        db_filters["date"] = ["between", [filters.from_date, filters.to_date]]
    elif filters.from_date:
        db_filters["date"] = [">=", filters.from_date]
    elif filters.to_date:
        db_filters["date"] = ["<=", filters.to_date]
    return db_filters


def _unmatched_row(row, normalized) -> dict[str, Any]:
    return {
        "match_name": None,
        "bank_transaction": row.name,
        "transaction_date": normalized.get("transaction_date"),
        "bank_amount": normalized.get("amount"),
        "candidate_amount": None,
        "amount_difference": None,
        "currency": normalized.get("currency"),
        "description": normalized.get("description"),
        "reference": normalized.get("reference"),
        "party": normalized.get("party"),
        "direction": normalized.get("direction"),
        "transaction_category": CATEGORY_UNCLASSIFIED,
        "operational_status": STATUS_UNMATCHED,
        "suggested_document_type": None,
        "suggested_document": None,
        "decision_status": None,
        "review_status": None,
        "match_confidence": None,
        "match_score": None,
        "company": normalized.get("company"),
        "branch": normalized.get("branch"),
        "bank_account": normalized.get("bank_account"),
        "can_execute": None,
        "recommended_action": "Find and review a valid accounting match.",
    }


def _get_unmatched_bank_transaction_rows(
    direction: str, limit: int, filters: frappe._dict
) -> tuple[list[dict[str, Any]], int]:
    output: list[dict[str, Any]] = []
    skipped = 0
    scanned = 0
    start = 0
    db_filters = _unmatched_db_filters(filters)

    while len(output) < limit and scanned < MAX_SCAN_ROWS:
        page = frappe.get_list(
            "Bank Transaction",
            filters=db_filters,
            fields=[
                "name",
                "date",
                "deposit",
                "withdrawal",
                "bank_account",
                "company",
                "status",
                "allocated_amount",
                "unallocated_amount",
                "description",
                "reference_number",
                "currency",
            ],
            order_by="date desc, modified desc",
            limit_start=start,
            limit_page_length=SCAN_CHUNK_SIZE,
        )
        if not page:
            break
        scanned += len(page)
        start += len(page)
        active_matches = _get_active_match_bank_transactions([row.name for row in page])

        for row in page:
            if row.name in active_matches:
                continue
            try:
                normalized = normalize_bank_transaction(row)
            except Exception:
                skipped += 1
                continue
            row_direction = cstr(normalized.get("direction")).strip()
            if row_direction not in {"Inflow", "Outflow"}:
                skipped += 1
                continue
            if direction != DIRECTION_ALL and row_direction != direction:
                continue
            if normalized.get("is_reconciled"):
                continue
            item = _unmatched_row(row, normalized)
            if not _matches_filters(item, filters):
                continue
            output.append(item)
            if len(output) >= limit:
                break

        if len(page) < SCAN_CHUNK_SIZE:
            break
    return output, skipped


def _review_db_filters(queue: str, filters: frappe._dict) -> dict[str, Any]:
    db_filters: dict[str, Any] = {}
    if filters.company:
        db_filters["company"] = filters.company
    if filters.branch:
        db_filters["branch"] = filters.branch
    if filters.bank_account:
        db_filters["bank_account"] = filters.bank_account
    if filters.from_date and filters.to_date:
        db_filters["transaction_date"] = ["between", [filters.from_date, filters.to_date]]
    elif filters.from_date:
        db_filters["transaction_date"] = [">=", filters.from_date]
    elif filters.to_date:
        db_filters["transaction_date"] = ["<=", filters.to_date]

    if queue == QUEUE_TO_RECONCILE:
        db_filters["decision_status"] = "Confirmed"
    elif queue == QUEUE_TO_MATCH:
        db_filters["decision_status"] = ["in", ["Draft", "Suggested"]]
    elif queue == QUEUE_EXCEPTIONS:
        db_filters["decision_status"] = ["in", ["Needs Review", "Reopened", "Confirmed"]]
    return db_filters


def _bulk_bank_context(bank_transaction_names: list[str]) -> dict[str, dict[str, Any]]:
    names = list(dict.fromkeys(name for name in bank_transaction_names if name))
    if not names:
        return {}
    rows = frappe.get_list(
        "Bank Transaction",
        filters={"name": ["in", names]},
        fields=[
            "name",
            "date",
            "deposit",
            "withdrawal",
            "bank_account",
            "company",
            "status",
            "allocated_amount",
            "unallocated_amount",
            "description",
            "reference_number",
            "currency",
        ],
        limit_page_length=len(names),
    )
    output = {}
    for row in rows:
        try:
            output[row.name] = normalize_bank_transaction(row)
        except Exception:
            continue
    return output


def _cheap_operational(row, bank: dict[str, Any], queue: str) -> dict[str, Any] | None:
    """Resolve states that do not require reconciliation preflight.

    Suggested/unreviewed rows, explicit review states, failed execution, and RetailEdge-recorded
    terminal execution can be placed in their queues from stored state plus the normalized Bank
    Transaction. Confirmed readiness still goes through the canonical reconciliation bridge.
    """
    direction = cstr(bank.get("direction")).strip()
    if direction not in {"Inflow", "Outflow"}:
        return None
    decision_status = cstr(row.decision_status).strip()
    execution_status = cstr(getattr(row, "execution_status", None)).strip()

    if queue == QUEUE_TO_MATCH and decision_status in {"Draft", "Suggested"}:
        return {
            "direction": direction,
            "transaction_category": CATEGORY_UNCLASSIFIED,
            "operational_status": STATUS_SUGGESTED if row.suggested_document else STATUS_UNMATCHED,
            "recommended_action": "Review the prepared suggestion." if row.suggested_document else "Find and review a valid accounting match.",
        }
    if queue == QUEUE_EXCEPTIONS and decision_status in {"Needs Review", "Reopened"}:
        return {
            "direction": direction,
            "transaction_category": CATEGORY_UNCLASSIFIED,
            "operational_status": STATUS_NEEDS_REVIEW,
            "recommended_action": "Review and resolve the match exception.",
        }
    if queue == QUEUE_EXCEPTIONS and execution_status == "Failed":
        return {
            "direction": direction,
            "transaction_category": CATEGORY_UNCLASSIFIED,
            "operational_status": STATUS_RECONCILIATION_FAILED,
            "recommended_action": "Review the reconciliation failure before retrying.",
        }
    if queue == QUEUE_RECONCILED and execution_status in {"Executed", "Already Handled"}:
        return {
            "direction": direction,
            "transaction_category": CATEGORY_UNCLASSIFIED,
            "operational_status": STATUS_RECONCILED,
            "recommended_action": "No action required.",
        }
    return None


def _get_review_queue_rows(
    direction: str, queue: str, limit: int, filters: frappe._dict
) -> tuple[list[dict[str, Any]], int]:
    output: list[dict[str, Any]] = []
    skipped = 0
    scanned = 0
    start = 0
    db_filters = _review_db_filters(queue, filters)

    while len(output) < limit and scanned < MAX_SCAN_ROWS:
        rows = frappe.get_list(
            "RetailEdge Bank Transaction Match",
            filters=db_filters,
            fields=[
                "name",
                "bank_transaction",
                "transaction_date",
                "bank_amount",
                "candidate_amount",
                "amount_difference",
                "suggested_document_type",
                "suggested_document",
                "decision_status",
                "review_status",
                "match_confidence",
                "match_score",
                "company",
                "branch",
                "bank_account",
                "execution_status",
                "modified",
            ],
            order_by="transaction_date desc, modified desc",
            limit_start=start,
            limit_page_length=SCAN_CHUNK_SIZE,
        )
        if not rows:
            break
        scanned += len(rows)
        start += len(rows)
        bank_contexts = _bulk_bank_context([row.bank_transaction for row in rows])

        for row in rows:
            bank = bank_contexts.get(row.bank_transaction, {})
            operational = _cheap_operational(row, bank, queue)
            if operational is None:
                try:
                    operational = get_bank_match_operational_status(row.name, include_gate=False)
                except Exception:
                    skipped += 1
                    continue
            if direction != DIRECTION_ALL and operational.get("direction") != direction:
                continue
            if not _status_belongs_to_queue(operational.get("operational_status"), queue):
                continue

            item = {
                "match_name": row.name,
                "bank_transaction": row.bank_transaction,
                "transaction_date": row.transaction_date or bank.get("transaction_date"),
                "bank_amount": row.bank_amount or bank.get("amount"),
                "candidate_amount": row.candidate_amount,
                "amount_difference": row.amount_difference,
                "currency": bank.get("currency"),
                "description": bank.get("description"),
                "reference": bank.get("reference"),
                "party": bank.get("party"),
                "direction": operational.get("direction"),
                "transaction_category": operational.get("transaction_category"),
                "operational_status": operational.get("operational_status"),
                "suggested_document_type": row.suggested_document_type,
                "suggested_document": row.suggested_document,
                "decision_status": row.decision_status,
                "review_status": row.review_status,
                "match_confidence": row.match_confidence,
                "match_score": row.match_score,
                "company": row.company,
                "branch": row.branch,
                "bank_account": row.bank_account or bank.get("bank_account"),
                "can_execute": None,
                "recommended_action": operational.get("recommended_action"),
            }
            if not _matches_filters(item, filters):
                continue
            output.append(item)
            if len(output) >= limit:
                break

        if len(rows) < SCAN_CHUNK_SIZE:
            break
    return output, skipped


@frappe.whitelist()
def get_banking_workspace_rows(
    direction: str | None = DIRECTION_ALL,
    queue: str | None = QUEUE_TO_MATCH,
    limit: int | str | None = 100,
    company: str | None = None,
    branch: str | None = None,
    bank_account: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    assert_can_access_bank_transaction_matching()
    direction = normalize_direction(direction)
    queue = _normalize_queue(queue)
    limit = max(1, min(cint(limit or 100), 500))
    filters = frappe._dict(
        {
            "company": company,
            "branch": branch,
            "bank_account": bank_account,
            "from_date": from_date,
            "to_date": to_date,
            "search": search,
        }
    )

    if queue == QUEUE_TO_MATCH:
        unmatched, skipped_unmatched = _get_unmatched_bank_transaction_rows(direction, limit, filters)
        suggested, skipped_suggested = _get_review_queue_rows(direction, queue, limit, filters)
        rows = sorted(
            unmatched + suggested,
            key=lambda row: cstr(row.get("transaction_date")),
            reverse=True,
        )[:limit]
        skipped = skipped_unmatched + skipped_suggested
    else:
        rows, skipped = _get_review_queue_rows(direction, queue, limit, filters)

    return {
        "direction": direction,
        "queue": queue,
        "rows": rows,
        "count": len(rows),
        "skipped_count": skipped,
    }
