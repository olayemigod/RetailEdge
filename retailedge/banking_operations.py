from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cstr

from retailedge.bank_transaction_match_workflow import (
    assert_can_manage_bank_transaction_match,
    confirm_bank_transaction_match,
)
from retailedge.bank_transaction_matching import (
    assert_can_access_bank_transaction_matching,
    normalize_bank_transaction,
)
from retailedge.reconciliation_approval import build_reconciliation_approval_state
from retailedge.reconciliation_bridge import (
    EXECUTION_STATUS_ALREADY_HANDLED,
    EXECUTION_STATUS_EXECUTED,
    READINESS_GROUP_ALREADY_HANDLED,
    READINESS_GROUP_BLOCKED,
    READINESS_GROUP_NEEDS_REVIEW,
    READINESS_GROUP_READY,
    check_reconciliation_execution_gate,
    execute_reconciliation_for_match,
    get_reconciliation_preflight,
)

DIRECTION_ALL = "All"
DIRECTION_INFLOW = "Inflow"
DIRECTION_OUTFLOW = "Outflow"
VALID_DIRECTIONS = {DIRECTION_ALL, DIRECTION_INFLOW, DIRECTION_OUTFLOW}

STATUS_UNMATCHED = "Unmatched"
STATUS_SUGGESTED = "Suggested Match"
STATUS_NEEDS_REVIEW = "Needs Review"
STATUS_MATCH_CONFIRMED = "Match Confirmed"
STATUS_RECONCILIATION_PENDING = "Reconciliation Pending"
STATUS_AWAITING_APPROVAL = "Awaiting Approval"
STATUS_READY_TO_RECONCILE = "Ready to Reconcile"
STATUS_PAYMENT_EVIDENCE_REQUIRED = "Payment Evidence Required"
STATUS_EXCEPTION = "Exception"
STATUS_RECONCILIATION_FAILED = "Reconciliation Failed"
STATUS_RECONCILED = "Reconciled"

CATEGORY_CUSTOMER_RECEIPT = "Customer Receipt"
CATEGORY_POS_SALE = "POS Sale"
CATEGORY_BANK_DEPOSIT = "Deposit to Bank"
CATEGORY_SUPPLIER_PAYMENT = "Supplier Payment"
CATEGORY_EXPENSE = "Expense"
CATEGORY_BANK_CHARGE = "Bank Charge"
CATEGORY_TRANSFER = "Bank Transfer"
CATEGORY_REFUND = "Refund"
CATEGORY_OTHER_INCOME = "Other Income"
CATEGORY_OTHER_OUTFLOW = "Other Outflow"
CATEGORY_UNCLASSIFIED = "Unclassified"

INACTIVE_DECISION_STATUSES = {"Rejected", "Cancelled"}


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def normalize_direction(value: str | None) -> str:
    value = cstr(value).strip().lower()
    if value in {"inflow", "credit", "deposit", "receive", "received"}:
        return DIRECTION_INFLOW
    if value in {"outflow", "debit", "withdrawal", "pay", "paid"}:
        return DIRECTION_OUTFLOW
    if value in {"", "all"}:
        return DIRECTION_ALL
    frappe.throw(f"Unsupported banking direction: {value}")


def get_bank_transaction_direction(bank_transaction: str | dict[str, Any]) -> str:
    normalized = normalize_bank_transaction(bank_transaction)
    direction = cstr(normalized.get("direction")).strip()
    if direction == DIRECTION_INFLOW:
        return DIRECTION_INFLOW
    if direction == DIRECTION_OUTFLOW:
        return DIRECTION_OUTFLOW
    frappe.throw("Bank Transaction direction could not be determined safely.")


def direction_matches(bank_transaction: str | dict[str, Any], direction: str | None) -> bool:
    wanted = normalize_direction(direction)
    return wanted == DIRECTION_ALL or get_bank_transaction_direction(bank_transaction) == wanted


def _payment_entry_category(name: str, direction: str) -> str:
    name = cstr(name).strip()
    if not name:
        return CATEGORY_CUSTOMER_RECEIPT if direction == DIRECTION_INFLOW else CATEGORY_OTHER_OUTFLOW
    rows = frappe.get_list(
        "Payment Entry",
        filters={"name": name, "docstatus": 1},
        fields=["payment_type", "party_type", "remarks"],
        limit_page_length=1,
    )
    if not rows:
        return CATEGORY_UNCLASSIFIED
    row = frappe._dict(rows[0])
    payment_type = cstr(row.get("payment_type")).strip()
    party_type = cstr(row.get("party_type")).strip()
    remarks = cstr(row.get("remarks")).lower()
    if payment_type == "Internal Transfer":
        return CATEGORY_BANK_DEPOSIT if direction == DIRECTION_INFLOW else CATEGORY_TRANSFER
    if direction == DIRECTION_INFLOW:
        return CATEGORY_CUSTOMER_RECEIPT if party_type == "Customer" else CATEGORY_OTHER_INCOME
    if party_type == "Supplier":
        return CATEGORY_SUPPLIER_PAYMENT
    if any(token in remarks for token in ("expense", "charge", "fee", "rent", "utility")):
        return CATEGORY_EXPENSE
    return CATEGORY_OTHER_OUTFLOW


def classify_transaction_category(match_doc: dict[str, Any] | None, direction: str) -> str:
    match_doc = frappe._dict(match_doc or {})
    candidate_doctype = cstr(
        match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")
    ).strip()
    candidate_name = cstr(
        match_doc.get("suggested_document") or match_doc.get("candidate_name")
    ).strip()
    candidate_category = cstr(match_doc.get("candidate_category")).strip().lower()
    payment_event_source = cstr(match_doc.get("payment_event_source")).strip().lower()
    party_type = cstr(match_doc.get("party_type")).strip()

    if "deposit" in candidate_category or "deposit to bank" in payment_event_source:
        return CATEGORY_BANK_DEPOSIT
    if "pos" in candidate_category.split() or "pos payment" in payment_event_source:
        return CATEGORY_POS_SALE
    if "transfer" in candidate_category or "transfer" in payment_event_source:
        return CATEGORY_TRANSFER
    if "bank charge" in candidate_category or "bank charge" in payment_event_source:
        return CATEGORY_BANK_CHARGE
    if "expense" in candidate_category or candidate_doctype == "Expense Claim":
        return CATEGORY_EXPENSE
    if "refund" in candidate_category or "refund" in payment_event_source:
        return CATEGORY_REFUND

    if candidate_doctype == "Purchase Invoice" or party_type == "Supplier":
        return CATEGORY_SUPPLIER_PAYMENT
    if candidate_doctype == "Sales Invoice" or party_type == "Customer":
        return CATEGORY_CUSTOMER_RECEIPT if direction == DIRECTION_INFLOW else CATEGORY_REFUND
    if candidate_doctype == "Payment Entry":
        return _payment_entry_category(candidate_name, direction)
    if candidate_doctype == "Journal Entry":
        return CATEGORY_OTHER_INCOME if direction == DIRECTION_INFLOW else CATEGORY_OTHER_OUTFLOW

    return CATEGORY_UNCLASSIFIED


def _load_match(match_name: str) -> frappe._dict:
    fields = [
        "name",
        "bank_transaction",
        "suggested_document_type",
        "suggested_document",
        "payment_row_index",
        "payment_account",
        "resolved_payment_account",
        "decision_status",
        "review_status",
        "confirmed_by",
        "confirmed_on",
        "approval_status",
        "approval_requested_by",
        "approval_requested_on",
        "approved_by",
        "approved_on",
        "approval_note",
        "approval_candidate_identity",
        "match_confidence",
        "match_score",
        "candidate_amount",
        "bank_amount",
        "amount_difference",
        "company",
        "branch",
        "bank_account",
        "party",
        "customer",
        "execution_status",
        "execution_message",
        "execution_error_summary",
    ]
    row = frappe.db.get_value(
        "RetailEdge Bank Transaction Match", match_name, fields, as_dict=True
    )
    if not row:
        frappe.throw(f"Bank match review {match_name} was not found.")
    return frappe._dict(row)


def derive_operational_status(
    match_doc: dict[str, Any] | None,
    preflight: dict[str, Any] | None = None,
    gate: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
) -> str:
    match_doc = frappe._dict(match_doc or {})
    preflight = frappe._dict(preflight or {})
    gate = frappe._dict(gate or {})
    approval = frappe._dict(approval or {})

    decision_status = cstr(match_doc.get("decision_status")).strip()
    execution_status = cstr(match_doc.get("execution_status")).strip()
    readiness_group = cstr(
        preflight.get("readiness_group")
        or preflight.get("eligibility_status")
        or gate.get("dry_run_status")
    ).strip()
    preflight_status = cstr(preflight.get("status")).strip()
    target_status = cstr(preflight.get("erpnext_target_status")).strip()

    if execution_status in {EXECUTION_STATUS_EXECUTED, EXECUTION_STATUS_ALREADY_HANDLED}:
        return STATUS_RECONCILED
    if execution_status == "Failed":
        return STATUS_RECONCILIATION_FAILED
    if preflight_status == "Already Reconciled" or readiness_group == READINESS_GROUP_ALREADY_HANDLED:
        return STATUS_RECONCILED
    if decision_status in INACTIVE_DECISION_STATUSES:
        return STATUS_UNMATCHED
    if decision_status in {"", "Draft", "Suggested"}:
        return STATUS_SUGGESTED if match_doc.get("suggested_document") else STATUS_UNMATCHED
    if decision_status in {"Needs Review", "Reopened"} or readiness_group == READINESS_GROUP_NEEDS_REVIEW:
        return STATUS_NEEDS_REVIEW
    if decision_status != "Confirmed":
        return STATUS_NEEDS_REVIEW

    if target_status in {"Payment Voucher Missing", "Manual ERPNext Review Required"}:
        return STATUS_PAYMENT_EVIDENCE_REQUIRED
    if readiness_group == READINESS_GROUP_BLOCKED or preflight_status in {"Exception", "Target Ambiguous"}:
        return STATUS_EXCEPTION
    if readiness_group == READINESS_GROUP_READY or preflight_status == "Ready":
        if approval.get("required") and not approval.get("is_satisfied"):
            return STATUS_AWAITING_APPROVAL
        return STATUS_READY_TO_RECONCILE
    if gate and gate.get("can_execute") is False:
        return STATUS_RECONCILIATION_PENDING
    return STATUS_RECONCILIATION_PENDING


@frappe.whitelist()
def get_bank_match_operational_status(match_name: str, include_gate: bool = True) -> dict[str, Any]:
    assert_can_access_bank_transaction_matching()
    include_gate = _bool(include_gate, True)
    match_doc = _load_match(match_name)
    bank_transaction = match_doc.get("bank_transaction")
    direction = get_bank_transaction_direction(bank_transaction)
    preflight = get_reconciliation_preflight(match_name)
    approval = build_reconciliation_approval_state(match_doc)
    gate = check_reconciliation_execution_gate(match_name) if include_gate else frappe._dict()
    status = derive_operational_status(
        match_doc,
        preflight=preflight,
        gate=gate,
        approval=approval,
    )

    context = frappe._dict(preflight or {})
    context.update(match_doc)
    recommended_action = preflight.get("recommended_action")
    if status == STATUS_AWAITING_APPROVAL:
        recommended_action = approval.get("reason") or "A different authorised user must approve this reconciliation."
    return {
        "match_name": match_name,
        "bank_transaction": bank_transaction,
        "direction": direction,
        "transaction_category": classify_transaction_category(context, direction),
        "operational_status": status,
        "decision_status": match_doc.get("decision_status"),
        "reconciliation_status": preflight.get("status"),
        "reconciliation_readiness": preflight.get("readiness_group")
        or preflight.get("eligibility_status"),
        "approval_required": bool(approval.get("required")),
        "approval_status": approval.get("status"),
        "approval_reason": approval.get("reason"),
        "approval_can_approve": bool(approval.get("can_approve")),
        "approved_by": approval.get("approved_by"),
        "approved_on": approval.get("approved_on"),
        "execution_status": match_doc.get("execution_status"),
        "can_execute": bool(gate.get("can_execute")) if include_gate else None,
        "blocking_reasons": (gate.get("block_reasons") or []) if include_gate else [],
        "recommended_action": recommended_action,
        "erpnext_target_doctype": preflight.get("erpnext_target_doctype"),
        "erpnext_target_name": preflight.get("erpnext_target_name"),
    }


@frappe.whitelist()
def match_and_reconcile(match_name: str, confirm_match: bool = False, confirm_reconciliation: bool = False):
    """Confirm a prepared match, rerun native reconciliation gates, then optionally reconcile.

    This deliberately delegates accounting mutation to the existing reconciliation bridge,
    which in turn uses ERPNext's native Bank Reconciliation Tool. It never mutates submitted
    Sales Invoice, Payment Entry, Journal Entry, or GL Entry documents directly.
    """
    assert_can_manage_bank_transaction_match()
    assert_can_access_bank_transaction_matching()
    confirm_match = _bool(confirm_match)
    confirm_reconciliation = _bool(confirm_reconciliation)
    match_doc = _load_match(match_name)
    decision_status = cstr(match_doc.get("decision_status")).strip()

    if decision_status != "Confirmed":
        if not confirm_match:
            return {
                "status": "Confirmation Required",
                "message": "Confirm the proposed match before reconciliation.",
                "operational": get_bank_match_operational_status(match_name),
            }
        confirm_bank_transaction_match(
            match_name,
            decision_note="Confirmed from Bank Matching & Reconciliation.",
        )

    operational = get_bank_match_operational_status(match_name)
    if operational.get("operational_status") == STATUS_RECONCILED:
        return {
            "status": STATUS_RECONCILED,
            "message": "This bank transaction is already reconciled in ERPNext.",
            "operational": operational,
        }
    if operational.get("operational_status") != STATUS_READY_TO_RECONCILE:
        return {
            "status": operational.get("operational_status"),
            "message": operational.get("recommended_action")
            or "This match is not ready for reconciliation.",
            "operational": operational,
        }
    if not confirm_reconciliation:
        return {
            "status": "Reconciliation Confirmation Required",
            "message": "Match is confirmed and ready. Final confirmation is required to reconcile in ERPNext.",
            "operational": operational,
        }

    execution = execute_reconciliation_for_match(match_name, confirm=True)
    return {
        "status": execution.get("execution_status") or execution.get("status"),
        "message": execution.get("message"),
        "execution": execution,
        "operational": get_bank_match_operational_status(match_name),
    }
