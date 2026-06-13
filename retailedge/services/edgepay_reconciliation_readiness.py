# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime

def get_edgepay_reconciliation_readiness(evidence_name):
	"""
	Validates whether the EdgePay payment evidence is eligible for reconciliation.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		return {"ok": False, "status": "Exception", "message": f"Payment Evidence {evidence_name} not found."}
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	
	# 1. review_status must be Reviewed
	if evidence.review_status != "Reviewed":
		return {"ok": False, "status": "Not Ready", "message": f"Payment Evidence is not Reviewed. Current status: {evidence.review_status}."}
		
	# 2. submission_status must be Submitted
	if evidence.submission_status != "Submitted":
		return {"ok": False, "status": "Not Ready", "message": f"Payment Evidence submission status is not Submitted. Current status: {evidence.submission_status}."}
		
	# 3. posting_status must be Submitted
	if evidence.posting_status != "Submitted":
		return {"ok": False, "status": "Not Ready", "message": f"Payment Evidence posting status is not Submitted. Current status: {evidence.posting_status}."}
		
	# 4. linked Payment Entry exists
	if not evidence.payment_entry:
		return {"ok": False, "status": "Blocked", "message": "No linked Payment Entry on payment evidence."}
		
	if not frappe.db.exists("Payment Entry", evidence.payment_entry):
		return {"ok": False, "status": "Blocked", "message": f"Linked Payment Entry {evidence.payment_entry} does not exist."}
		
	pe_doc = frappe.get_doc("Payment Entry", evidence.payment_entry)
	
	# 5. linked Payment Entry is submitted / docstatus 1
	if pe_doc.docstatus != 1:
		# 6. no cancelled Payment Entry is linked
		if pe_doc.docstatus == 2:
			return {"ok": False, "status": "Blocked", "message": f"Linked Payment Entry {evidence.payment_entry} is cancelled."}
		return {"ok": False, "status": "Blocked", "message": f"Linked Payment Entry {evidence.payment_entry} is not submitted."}
		
	# 7. provider_reference exists
	if not evidence.provider_reference:
		return {"ok": False, "status": "Blocked", "message": "Missing provider_reference on payment evidence."}
		
	# 8. amount and currency remain consistent
	if abs(flt(evidence.amount) - flt(pe_doc.paid_amount)) > 0.01:
		return {"ok": False, "status": "Blocked", "message": f"Amount mismatch: evidence amount {evidence.amount} does not match Payment Entry paid amount {pe_doc.paid_amount}."}
		
	# Currency checking: allow if it matches either paid_from or paid_to account currency
	currency_matches = False
	if pe_doc.paid_from_account_currency and evidence.currency.upper() == pe_doc.paid_from_account_currency.upper():
		currency_matches = True
	if pe_doc.paid_to_account_currency and evidence.currency.upper() == pe_doc.paid_to_account_currency.upper():
		currency_matches = True
		
	if not currency_matches:
		return {"ok": False, "status": "Blocked", "message": f"Currency mismatch: evidence currency {evidence.currency} does not match Payment Entry account currencies."}
		
	# 9. source document still exists
	if not frappe.db.exists(evidence.source_doctype, evidence.source_name):
		return {"ok": False, "status": "Blocked", "message": f"Source document {evidence.source_doctype} {evidence.source_name} does not exist."}
		
	# 10. no conflicting submitted Payment Entry exists for the same provider_reference
	conflicts = frappe.get_all("Payment Entry", filters={
		"reference_no": evidence.provider_reference,
		"docstatus": 1
	}, fields=["name"])
	conflicts = [x.name for x in conflicts if x.name != evidence.payment_entry]
	if conflicts:
		return {"ok": False, "status": "Blocked", "message": f"Conflicting submitted Payment Entry {conflicts[0]} already exists with reference_no {evidence.provider_reference}."}
		
	# 11. no completed reconciliation already exists for the same evidence/payment entry
	reconciliations = frappe.get_all("Bank Transaction Payments", filters={
		"payment_document": "Payment Entry",
		"payment_entry": evidence.payment_entry
	}, fields=["parent"])
	
	active_reconciliations = []
	for rec in reconciliations:
		if frappe.db.get_value("Bank Transaction", rec.parent, "docstatus") == 1:
			active_reconciliations.append(rec.parent)
			
	if active_reconciliations:
		return {
			"ok": True,
			"status": "Reconciled",
			"message": f"Completed reconciliation exists on Bank Transaction {active_reconciliations[0]}.",
			"linked_bank_transaction": active_reconciliations[0]
		}
		
	# Check if a confirmed RetailEdge Bank Transaction Match exists
	confirmed_match = frappe.get_all("RetailEdge Bank Transaction Match", filters={
		"payment_entry": evidence.payment_entry,
		"decision_status": "Confirmed"
	}, fields=["name", "bank_transaction"])
	
	if confirmed_match:
		return {
			"ok": True,
			"status": "Matched",
			"message": f"Confirmed match review exists: {confirmed_match[0].name}.",
			"linked_bank_transaction": confirmed_match[0].bank_transaction,
			"linked_bank_match_review": confirmed_match[0].name
		}
		
	return {"ok": True, "status": "Ready", "message": "Reconciliation readiness validation passed."}

def mark_edgepay_evidence_reconciliation_ready(evidence_name):
	"""
	Marks the EdgePay payment evidence reconciliation readiness.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	res = get_edgepay_reconciliation_readiness(evidence_name)
	
	evidence.db_set("reconciliation_status", res["status"])
	evidence.db_set("reconciliation_message", res["message"])
	evidence.db_set("reconciliation_checked_on", now_datetime())
	evidence.db_set("reconciliation_checked_by", frappe.session.user)
	
	if res.get("linked_bank_transaction"):
		evidence.db_set("linked_bank_transaction", res["linked_bank_transaction"])
	if res.get("linked_bank_match_review"):
		evidence.db_set("linked_bank_match_review", res["linked_bank_match_review"])
		
	return {"ok": True, "status": res["status"], "message": res["message"]}

def mark_edgepay_evidence_reconciliation_blocked(evidence_name, reason=None):
	"""
	Marks the EdgePay payment evidence as reconciliation blocked.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	evidence.db_set("reconciliation_status", "Blocked")
	if reason:
		evidence.db_set("reconciliation_message", reason)
	evidence.db_set("reconciliation_checked_on", now_datetime())
	evidence.db_set("reconciliation_checked_by", frappe.session.user)
	
	return {"ok": True, "message": "Reconciliation marked as Blocked."}

def find_edgepay_payment_entry_bank_match_candidates(evidence_name):
	"""
	Finds candidate Bank Transactions for the submitted Payment Entry linked to this evidence.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		return []
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	
	# Find Bank Transactions with deposit == evidence.amount, status in (Unreconciled, Partially Reconciled), docstatus == 1
	bts = frappe.get_all("Bank Transaction", filters={
		"deposit": evidence.amount,
		"status": ["in", ["Unreconciled", "Partially Reconciled"]],
		"docstatus": 1
	}, fields=["name", "date", "reference_number", "description", "bank_account", "currency"])
	
	pe_doc = None
	bank_account_name = None
	if evidence.payment_entry and frappe.db.exists("Payment Entry", evidence.payment_entry):
		pe_doc = frappe.get_doc("Payment Entry", evidence.payment_entry)
		bank_account_name = frappe.db.get_value("Bank Account", {"account": pe_doc.paid_to}, "name")
		
	candidates = []
	for bt in bts:
		# Check if currencies match (or fallback if empty)
		if bt.currency and evidence.currency and bt.currency.upper() != evidence.currency.upper():
			continue
			
		score = 30
		reasons = ["Amount matches."]
		
		# Date gap check
		target_date = getdate(evidence.paid_on) if evidence.paid_on else (getdate(pe_doc.reference_date) if pe_doc else None)
		if target_date and bt.date:
			date_gap = abs((getdate(bt.date) - getdate(target_date)).days)
			if date_gap <= 2:
				score += 30
				reasons.append(f"Transaction date is within {date_gap} days.")
			elif date_gap <= 7:
				score += 15
				reasons.append(f"Transaction date is within {date_gap} days.")
			else:
				score -= 10
				reasons.append(f"Transaction date has a gap of {date_gap} days.")
				
		# Reference check
		refs_to_check = []
		if evidence.provider_reference:
			refs_to_check.append(evidence.provider_reference)
		if evidence.transaction_reference:
			refs_to_check.append(evidence.transaction_reference)
		if pe_doc and pe_doc.reference_no:
			refs_to_check.append(pe_doc.reference_no)
			
		for ref in refs_to_check:
			if not ref:
				continue
			ref_str = str(ref).strip().lower()
			bt_ref_str = str(bt.reference_number or "").strip().lower()
			bt_desc_str = str(bt.description or "").strip().lower()
			
			if ref_str == bt_ref_str:
				score += 40
				reasons.append(f"Exact match on reference number: {ref}.")
				break
			elif ref_str in bt_desc_str:
				score += 30
				reasons.append(f"Reference number {ref} found in transaction narration.")
				break
				
		# Bank account check
		if bank_account_name and bt.bank_account and bank_account_name == bt.bank_account:
			score += 10
			reasons.append("Bank account matches.")
			
		if score >= 30:
			confidence = "Low"
			if score >= 80:
				confidence = "High"
			elif score >= 50:
				confidence = "Medium"
				
			candidates.append({
				"bank_transaction": bt.name,
				"date": bt.date,
				"reference_number": bt.reference_number,
				"description": bt.description,
				"deposit": bt.deposit,
				"bank_account": bt.bank_account,
				"confidence": confidence,
				"match_reason": " ".join(reasons)
			})
			
	# Sort candidates by confidence / score descending, then date
	candidates.sort(key=lambda x: (
		3 if x["confidence"] == "High" else (2 if x["confidence"] == "Medium" else 1),
		x["date"]
	), reverse=True)
	
	return candidates
