# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt, now_datetime
import json

def get_edgepay_bank_match_review_preflight(evidence_name, bank_transaction_name=None):
	"""
	Performs preflight checks for creating a Bank Transaction Match Review.
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
		
	# Check completed reconciliation
	from retailedge.services.edgepay_reconciliation_readiness import get_edgepay_reconciliation_readiness
	readiness = get_edgepay_reconciliation_readiness(evidence_name)
	
	if readiness.get("status") == "Reconciled":
		return {"ok": False, "message": "A completed reconciliation already exists for this payment evidence."}
		
	if not readiness.get("ok") and readiness.get("status") not in ("Ready", "Matched"):
		return {"ok": False, "message": readiness.get("message") or "Evidence is not reconciliation-ready."}
		
	# If a confirmed match review already exists for this payment entry
	confirmed_pe_match = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"payment_entry": evidence.payment_entry,
			"decision_status": "Confirmed"
		},
		"name"
	)
	if confirmed_pe_match:
		if bank_transaction_name:
			confirmed_bt = frappe.db.get_value("RetailEdge Bank Transaction Match", confirmed_pe_match, "bank_transaction")
			if confirmed_bt == bank_transaction_name:
				return {
					"ok": True,
					"message": "A confirmed match review already exists for this bank transaction and payment entry.",
					"review_name": confirmed_pe_match
				}
		return {"ok": False, "message": f"Payment Entry {evidence.payment_entry} already has a confirmed bank match review: {confirmed_pe_match}."}
		
	# If bank_transaction_name is provided:
	if bank_transaction_name:
		if not frappe.db.exists("Bank Transaction", bank_transaction_name):
			return {"ok": False, "message": f"Selected Bank Transaction {bank_transaction_name} does not exist."}
			
		bt = frappe.get_doc("Bank Transaction", bank_transaction_name)
		if bt.docstatus != 1:
			return {"ok": False, "message": f"Bank Transaction {bank_transaction_name} is not submitted."}
		if bt.status == "Reconciled":
			return {"ok": False, "message": f"Bank Transaction {bank_transaction_name} is already reconciled."}
			
		# Amount matches or is within existing RetailEdge variance/review rules
		from retailedge.bank_transaction_matching import get_bank_transaction_matching_settings
		settings = get_bank_transaction_matching_settings()
		tolerance = flt(settings.get("amount_tolerance") or 0.0)
		diff = abs(flt(bt.deposit) - flt(evidence.amount))
		if diff > max(tolerance, 0.01):
			return {"ok": False, "message": f"Amount mismatch: Bank Transaction deposit {bt.deposit} does not match evidence amount {evidence.amount} within tolerance {tolerance}."}
			
		# Currency consistency
		if bt.currency and evidence.currency and bt.currency.upper() != evidence.currency.upper():
			return {"ok": False, "message": f"Currency mismatch: Bank Transaction currency {bt.currency} does not match evidence currency {evidence.currency}."}
			
		# Check if this Bank Transaction already has a confirmed match review
		confirmed_bt_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": bank_transaction_name,
				"decision_status": "Confirmed"
			},
			"name"
		)
		if confirmed_bt_match:
			return {"ok": False, "message": f"Bank Transaction {bank_transaction_name} already has a confirmed bank match review: {confirmed_bt_match}."}
			
		# Check if an active review record already exists for this exact pair
		existing_pair_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": bank_transaction_name,
				"payment_entry": evidence.payment_entry,
				"decision_status": ["not in", ["Rejected", "Cancelled"]]
			},
			"name"
		)
		if existing_pair_match:
			return {"ok": True, "message": "An active match review already exists for this pair.", "review_name": existing_pair_match}
			
		# Check if there is another active match review for the same Bank Transaction
		active_bt_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": bank_transaction_name,
				"decision_status": ["not in", ["Rejected", "Cancelled"]]
			},
			"name"
		)
		if active_bt_match:
			return {"ok": False, "message": f"Bank Transaction {bank_transaction_name} already has an active review record: {active_bt_match}."}
			
		# Check if there is another active match review for the same Payment Entry
		active_pe_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"payment_entry": evidence.payment_entry,
				"decision_status": ["not in", ["Rejected", "Cancelled"]]
			},
			"name"
		)
		if active_pe_match:
			return {"ok": False, "message": f"Payment Entry {evidence.payment_entry} already has an active review record: {active_pe_match}."}
			
	# Check if evidence is already linked to an active review
	if evidence.linked_bank_match_review:
		if frappe.db.exists("RetailEdge Bank Transaction Match", evidence.linked_bank_match_review):
			status = frappe.db.get_value("RetailEdge Bank Transaction Match", evidence.linked_bank_match_review, "decision_status")
			if status not in ("Rejected", "Cancelled"):
				if bank_transaction_name:
					bt_of_review = frappe.db.get_value("RetailEdge Bank Transaction Match", evidence.linked_bank_match_review, "bank_transaction")
					if bt_of_review == bank_transaction_name:
						return {
							"ok": True,
							"message": "Active match review already exists.",
							"review_name": evidence.linked_bank_match_review
						}
					else:
						return {"ok": False, "message": f"Evidence is already linked to another active match review: {evidence.linked_bank_match_review}."}
				else:
					return {
						"ok": True,
						"message": "Active match review already exists.",
						"review_name": evidence.linked_bank_match_review
					}
					
	return {"ok": True, "message": "Preflight validation passed."}

def create_edgepay_bank_match_review(evidence_name, bank_transaction_name):
	"""
	Creates a Bank Transaction Match Review for the given evidence and bank transaction.
	"""
	preflight = get_edgepay_bank_match_review_preflight(evidence_name, bank_transaction_name)
	if not preflight["ok"]:
		frappe.throw(preflight["message"])
		
	# Idempotency: return existing active match review
	if preflight.get("review_name"):
		mark_edgepay_evidence_match_review_created(evidence_name, preflight["review_name"])
		return {
			"ok": True,
			"review_name": preflight["review_name"],
			"message": "Returned existing active match review.",
			"created": False
		}
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	
	from retailedge.bank_transaction_match_workflow import create_or_get_bank_transaction_match
	
	res = create_or_get_bank_transaction_match(
		bank_transaction_name=bank_transaction_name,
		suggested_document_type="Payment Entry",
		suggested_document=evidence.payment_entry,
		payment_entry=evidence.payment_entry,
		source_report="EdgePay Reconciliation Readiness"
	)
	
	review_name = res["name"]
	
	# Enrich the match review details_json with EdgePay evidence context
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", review_name)
	details = {}
	if doc.details_json:
		try:
			details = json.loads(doc.details_json)
		except Exception:
			details = {}
	details.update({
		"edgepay_evidence": evidence_name,
		"provider_reference": evidence.provider_reference,
		"transaction_reference": evidence.transaction_reference,
	})
	doc.db_set("details_json", json.dumps(details, default=str, sort_keys=True))
	
	# Update evidence with review link and matched status
	mark_edgepay_evidence_match_review_created(evidence_name, review_name)
	
	return {
		"ok": True,
		"review_name": review_name,
		"message": "Bank Match Review created successfully.",
		"created": True
	}

def mark_edgepay_evidence_match_review_created(evidence_name, review_name):
	"""
	Links the Bank Match Review back to the Payment Evidence and updates status.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	review = frappe.get_doc("RetailEdge Bank Transaction Match", review_name)
	
	evidence.db_set("reconciliation_status", "Matched")
	evidence.db_set("linked_bank_transaction", review.bank_transaction)
	evidence.db_set("linked_bank_match_review", review_name)
	evidence.db_set("reconciliation_message", f"Bank Match Review created: {review_name} for Bank Transaction {review.bank_transaction}.")
	evidence.db_set("reconciliation_checked_on", now_datetime())
	evidence.db_set("reconciliation_checked_by", frappe.session.user)
