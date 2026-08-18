from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint, cstr

from retailedge.banking_operations import (
    DIRECTION_ALL,
    STATUS_EXCEPTION,
    STATUS_NEEDS_REVIEW,
    STATUS_PAYMENT_EVIDENCE_REQUIRED,
    STATUS_READY_TO_RECONCILE,
    STATUS_RECONCILED,
    STATUS_RECONCILIATION_FAILED,
    STATUS_RECONCILIATION_PENDING,
    get_bank_match_operational_status,
    normalize_direction,
)
from retailedge.bank_transaction_matching import assert_can_access_bank_transaction_matching

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
    return status not in {
        STATUS_READY_TO_RECONCILE,
        STATUS_RECONCILIATION_PENDING,
        STATUS_NEEDS_REVIEW,
        STATUS_PAYMENT_EVIDENCE_REQUIRED,
        STATUS_EXCEPTION,
        STATUS_RECONCILIATION_FAILED,
        STATUS_RECONCILED,
    }


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

    return {
        "direction": direction,
        "queue": queue,
        "rows": output,
        "count": len(output),
        "skipped_count": skipped,
    }
