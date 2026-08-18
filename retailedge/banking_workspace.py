from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint, cstr

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


def _normalize_queue(queue: str | None) -> str:
    queue = cstr(queue or QUEUE_TO_MATCH).strip()
    if queue not in VALID_QUEUES:
        frappe.throw(f"Unsupported banking queue: {queue}")
    return queue


def _status_belongs_to_queue(status: str, queue: str) -> bool:
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
    return status == STATUS_UNMATCHED


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


def _get_unmatched_bank_transaction_rows(direction: str, limit: int) -> tuple[list[dict[str, Any]], int]:
    source_limit = min(max(limit * 5, 100), 500)
    bank_rows = frappe.get_list(
        "Bank Transaction",
        filters={
            "docstatus": 1,
            "unallocated_amount": [">", 0],
        },
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
        ],
        order_by="date desc, modified desc",
        limit_page_length=source_limit,
    )
    active_matches = _get_active_match_bank_transactions([row.name for row in bank_rows])

    output = []
    skipped = 0
    for row in bank_rows:
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

        output.append(
            {
                "match_name": None,
                "bank_transaction": row.name,
                "transaction_date": normalized.get("transaction_date"),
                "bank_amount": normalized.get("amount"),
                "direction": row_direction,
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
        )
        if len(output) >= limit:
            break
    return output, skipped


def _get_review_queue_rows(direction: str, queue: str, limit: int) -> tuple[list[dict[str, Any]], int]:
    rows = frappe.get_list(
        "RetailEdge Bank Transaction Match",
        fields=[
            "name",
            "bank_transaction",
            "transaction_date",
            "bank_amount",
            "suggested_document_type",
            "suggested_document",
            "decision_status",
            "review_status",
            "match_confidence",
            "match_score",
            "company",
            "branch",
            "bank_account",
            "modified",
        ],
        order_by="transaction_date desc, modified desc",
        limit_page_length=min(limit * 3, 500),
    )

    output = []
    skipped = 0
    for row in rows:
        try:
            operational = get_bank_match_operational_status(row.name, include_gate=False)
        except Exception:
            skipped += 1
            continue
        if direction != DIRECTION_ALL and operational.get("direction") != direction:
            continue
        if not _status_belongs_to_queue(operational.get("operational_status"), queue):
            continue

        output.append(
            {
                "match_name": row.name,
                "bank_transaction": row.bank_transaction,
                "transaction_date": row.transaction_date,
                "bank_amount": row.bank_amount,
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
                "bank_account": row.bank_account,
                "can_execute": None,
                "recommended_action": operational.get("recommended_action"),
            }
        )
        if len(output) >= limit:
            break
    return output, skipped


@frappe.whitelist()
def get_banking_workspace_rows(
    direction: str | None = DIRECTION_ALL,
    queue: str | None = QUEUE_TO_MATCH,
    limit: int | str | None = 100,
) -> dict[str, Any]:
    assert_can_access_bank_transaction_matching()
    direction = normalize_direction(direction)
    queue = _normalize_queue(queue)
    limit = max(1, min(cint(limit or 100), 500))

    if queue == QUEUE_TO_MATCH:
        rows, skipped = _get_unmatched_bank_transaction_rows(direction, limit)
    else:
        rows, skipped = _get_review_queue_rows(direction, queue, limit)

    return {
        "direction": direction,
        "queue": queue,
        "rows": rows,
        "count": len(rows),
        "skipped_count": skipped,
    }
