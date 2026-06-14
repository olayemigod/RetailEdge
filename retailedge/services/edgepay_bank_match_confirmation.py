# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from retailedge.services.edgepay_reconciliation_readiness import (
	get_edgepay_reconciliation_readiness,
	mark_edgepay_evidence_reconciliation_blocked
)

def get_edgepay_bank_match_confirmation_preflight(evidence_name, review_name=None):
	"""
	Validates whether the Bank Match Review can be safely confirmed.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		return {"ok": False, "message": f"Payment Evidence {evidence_name} not found."}
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	
	if evidence.review_status != "Reviewed":
		return {"ok": False, "message": f"Payment Evidence is not Reviewed. Current status: {evidence.review_status}."}
		
	if evidence.submission_status != "Submitted":
		return {"ok": False, "message": f"Payment Evidence submission status is not Submitted. Current status: {evidence.submission_status}."}
		
	if evidence.posting_status != "Submitted":
		return {"ok": False, "message": f"Payment Evidence posting status is not Submitted. Current status: {evidence.posting_status}."}
		
	# Check linked Payment Entry
	if not evidence.payment_entry:
		return {"ok": False, "message": "No linked Payment Entry on payment evidence."}
		
	if not frappe.db.exists("Payment Entry", evidence.payment_entry):
		return {"ok": False, "message": f"Linked Payment Entry {evidence.payment_entry} does not exist."}
		
	pe_doc = frappe.get_doc("Payment Entry", evidence.payment_entry)
	if pe_doc.docstatus != 1:
		return {"ok": False, "message": f"Linked Payment Entry {evidence.payment_entry} is not submitted."}
		
	# Resolve review_name
	if not review_name:
		review_name = evidence.linked_bank_match_review
		
	if not review_name:
		return {"ok": False, "message": "No linked Bank Match Review found."}
		
	if not frappe.db.exists("RetailEdge Bank Transaction Match", review_name):
		return {"ok": False, "message": f"Bank Match Review {review_name} does not exist."}
		
	review = frappe.get_doc("RetailEdge Bank Transaction Match", review_name)
	
	# Verify review links match evidence and payment entry
	if review.payment_entry != evidence.payment_entry and review.suggested_document != evidence.payment_entry:
		return {"ok": False, "message": f"Bank Match Review {review_name} is not linked to Payment Entry {evidence.payment_entry}."}
		
	# If review is already confirmed, that is fine (idempotent path)
	if review.decision_status == "Confirmed":
		return {"ok": True, "message": "Bank Match Review is already confirmed.", "already_confirmed": True, "review_name": review_name}
		
	if review.decision_status in ("Rejected", "Cancelled"):
		return {"ok": False, "message": f"Bank Match Review {review_name} is {review.decision_status} and cannot be confirmed."}
		
	# Verify linked Bank Transaction
	if not review.bank_transaction:
		return {"ok": False, "message": f"Bank Match Review {review_name} has no linked Bank Transaction."}
		
	if not frappe.db.exists("Bank Transaction", review.bank_transaction):
		return {"ok": False, "message": f"Bank Transaction {review.bank_transaction} linked on review does not exist."}
		
	bt = frappe.get_doc("Bank Transaction", review.bank_transaction)
	if bt.docstatus != 1:
		return {"ok": False, "message": f"Bank Transaction {review.bank_transaction} is not submitted."}
		
	if bt.status == "Reconciled":
		return {"ok": False, "message": f"Bank Transaction {review.bank_transaction} is already reconciled."}
		
	# Verify amount and currency
	from retailedge.bank_transaction_matching import get_bank_transaction_matching_settings
	settings = get_bank_transaction_matching_settings()
	tolerance = flt(settings.get("amount_tolerance") or 0.0)
	diff = abs(flt(bt.deposit) - flt(evidence.amount))
	if diff > max(tolerance, 0.01):
		return {"ok": False, "message": f"Amount mismatch: Bank Transaction deposit {bt.deposit} does not match evidence amount {evidence.amount} within tolerance {tolerance}."}
		
	if bt.currency and evidence.currency and bt.currency.upper() != evidence.currency.upper():
		return {"ok": False, "message": f"Currency mismatch: Bank Transaction currency {bt.currency} does not match evidence currency {evidence.currency}."}
		
	# Check for confirmed duplicate match for same Payment Entry or Bank Transaction
	duplicate_pe_match = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"payment_entry": evidence.payment_entry,
			"decision_status": "Confirmed",
			"name": ["!=", review_name]
		},
		"name"
	)
	if duplicate_pe_match:
		return {"ok": False, "message": f"Payment Entry {evidence.payment_entry} already has another confirmed bank match review: {duplicate_pe_match}."}
		
	duplicate_bt_match = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"bank_transaction": review.bank_transaction,
			"decision_status": "Confirmed",
			"name": ["!=", review_name]
		},
		"name"
	)
	if duplicate_bt_match:
		return {"ok": False, "message": f"Bank Transaction {review.bank_transaction} already has another confirmed bank match review: {duplicate_bt_match}."}
		
	return {"ok": True, "message": "Preflight validation passed."}

def confirm_edgepay_bank_match_review(evidence_name, review_name=None):
	"""
	Confirms the Bank Match Review linked to the given Payment Evidence.
	"""
	preflight = get_edgepay_bank_match_confirmation_preflight(evidence_name, review_name)
	if not preflight["ok"]:
		mark_edgepay_evidence_reconciliation_blocked(evidence_name, preflight["message"])
		frappe.throw(preflight["message"])
		
	if not review_name:
		evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
		review_name = evidence.linked_bank_match_review
		
	if preflight.get("already_confirmed"):
		mark_edgepay_evidence_reconciliation_matched(evidence_name, review_name)
		return {
			"ok": True,
			"review_name": review_name,
			"message": "Bank Match Review was already confirmed.",
			"confirmed": False
		}
		
	# Invoke existing RetailEdge match confirmation logic
	from retailedge.bank_transaction_match_workflow import confirm_bank_transaction_match
	
	confirm_bank_transaction_match(
		match_name=review_name,
		decision_note=f"Confirmed match review for EdgePay Payment Evidence {evidence_name}."
	)
	
	# Update evidence details
	mark_edgepay_evidence_reconciliation_matched(evidence_name, review_name)
	
	return {
		"ok": True,
		"review_name": review_name,
		"message": "Bank Match Review confirmed successfully.",
		"confirmed": True
	}

def mark_edgepay_evidence_reconciliation_matched(evidence_name, review_name):
	"""
	Links the Bank Match Review and sets evidence reconciliation status to Matched/Reconciled.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	review = frappe.get_doc("RetailEdge Bank Transaction Match", review_name)
	
	# Transition status: check if the bank transaction is reconciled natively or if there is completed reconciliation
	readiness = get_edgepay_reconciliation_readiness(evidence_name)
	
	status = readiness.get("status") or "Matched"
	if status not in ("Matched", "Reconciled"):
		status = "Matched"
		
	evidence.db_set("reconciliation_status", status)
	evidence.db_set("linked_bank_transaction", review.bank_transaction)
	evidence.db_set("linked_bank_match_review", review_name)
	evidence.db_set("reconciliation_message", f"Bank Match Review confirmed: {review_name} for Bank Transaction {review.bank_transaction}.")
	evidence.db_set("reconciliation_checked_on", now_datetime())
	evidence.db_set("reconciliation_checked_by", frappe.session.user)
