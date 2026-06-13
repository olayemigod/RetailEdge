# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt, now_datetime, getdate, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

def get_edgepay_evidence_posting_preflight(evidence_name):
	"""
	Validates whether the EdgePay payment evidence is eligible for posting preparation.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		return {"ok": False, "message": f"Payment Evidence {evidence_name} not found."}
		
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	
	# 1. review_status must be Reviewed
	if evidence.review_status != "Reviewed":
		return {"ok": False, "message": f"Payment Evidence is not Reviewed. Current status: {evidence.review_status}."}
		
	# 2. processing_status must be successful
	if evidence.processing_status == "Failed":
		return {"ok": False, "message": "Payment Evidence processing status is Failed."}
		
	# 3. request_status must be Paid
	if evidence.request_status != "Paid":
		return {"ok": False, "message": f"Payment Request status is not Paid. Current status: {evidence.request_status}."}
		
	# 4. transaction_status is Success or equivalent (if present)
	if evidence.transaction_status and evidence.transaction_status.upper() not in ("SUCCESS", "PAID"):
		return {"ok": False, "message": f"Transaction status is not successful. Current status: {evidence.transaction_status}."}
		
	# 5. source document exists
	if not frappe.db.exists(evidence.source_doctype, evidence.source_name):
		return {"ok": False, "message": f"Source document {evidence.source_doctype} {evidence.source_name} does not exist."}
		
	# 6. amount matches source outstanding/payment expectation safely
	doc = frappe.get_doc(evidence.source_doctype, evidence.source_name)
	source_amount = doc.get("outstanding_amount") or doc.get("grand_total") or doc.get("amount") or 0.0
	
	if flt(source_amount) <= 0:
		return {"ok": False, "message": f"Source document {evidence.source_name} has no outstanding balance."}
		
	if abs(flt(evidence.amount) - flt(source_amount)) > 0.01:
		return {"ok": False, "message": f"Amount mismatch: evidence amount {evidence.amount} does not match source amount {source_amount}."}
		
	# 7. currency matches source currency
	source_currency = doc.get("currency")
	if not source_currency or evidence.currency.upper() != source_currency.upper():
		return {"ok": False, "message": f"Currency mismatch: evidence currency {evidence.currency} does not match source currency {source_currency}."}
		
	# 8. provider_reference exists
	if not evidence.provider_reference:
		return {"ok": False, "message": "Missing provider_reference on payment evidence."}
		
	# 9. no duplicate posting marker exists
	if evidence.payment_entry:
		return {"ok": False, "message": f"Payment Entry {evidence.payment_entry} is already linked to this evidence."}
		
	# 10. no conflicting existing Payment Entry / payment allocation already covers the same source and provider reference
	conflicts = frappe.get_all("Payment Entry", filters={
		"reference_no": evidence.provider_reference,
		"docstatus": ["<", 2]
	}, fields=["name", "docstatus"])
	
	if conflicts:
		return {"ok": False, "message": f"Conflicting Payment Entry {conflicts[0].name} already exists with reference_no {evidence.provider_reference}."}
		
	return {"ok": True, "message": "Preflight passed."}

def prepare_edgepay_payment_entry_draft(evidence_name):
	"""
	Prepares a draft Payment Entry for the specified payment evidence.
	"""
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	
	# If preflight passes, check if we already have a draft Payment Entry linked/exists
	# 1. Linked via evidence.payment_entry
	if evidence.payment_entry:
		if frappe.db.exists("Payment Entry", evidence.payment_entry):
			pe_docstatus = frappe.db.get_value("Payment Entry", evidence.payment_entry, "docstatus")
			if pe_docstatus == 0:
				return {
					"ok": True,
					"payment_entry": evidence.payment_entry,
					"message": _("Existing draft Payment Entry returned.")
				}
			elif pe_docstatus == 1:
				evidence.db_set("posting_status", "Draft Created")
				evidence.db_set("posting_preflight_message", _("Payment Entry {0} is already submitted for this transaction.").format(evidence.payment_entry))
				frappe.throw(_("Payment Entry {0} is already submitted for this transaction.").format(evidence.payment_entry))
			elif pe_docstatus == 2:
				# If cancelled, clear and mark as Cancelled, then proceed
				evidence.db_set("payment_entry", None)
				evidence.db_set("posting_status", "Cancelled")
			
	# 2. Exists in database with same reference_no (draft status)
	if evidence.provider_reference:
		existing_draft = frappe.db.get_value("Payment Entry", {"reference_no": evidence.provider_reference, "docstatus": 0}, "name")
		if existing_draft:
			evidence.db_set("payment_entry", existing_draft)
			evidence.db_set("posting_status", "Draft Created")
			evidence.db_set("posting_preflight_message", _("Existing draft linked."))
			return {
				"ok": True,
				"payment_entry": existing_draft,
				"message": _("Existing draft Payment Entry found and linked.")
			}
			
		# 3. Exists in database with same reference_no (submitted status)
		existing_submitted = frappe.db.get_value("Payment Entry", {"reference_no": evidence.provider_reference, "docstatus": 1}, "name")
		if existing_submitted:
			evidence.db_set("payment_entry", existing_submitted)
			evidence.db_set("posting_status", "Draft Created")
			evidence.db_set("posting_preflight_message", _("Existing submitted linked."))
			frappe.throw(_("Payment Entry {0} is already submitted for this transaction.").format(existing_submitted))

	preflight = get_edgepay_evidence_posting_preflight(evidence_name)
	
	# If preflight fails
	if not preflight.get("ok"):
		evidence.db_set("posting_status", "Blocked")
		evidence.db_set("posting_preflight_message", preflight.get("message"))
		frappe.throw(preflight.get("message"))
		
	# Prepare the new Payment Entry draft
	pe = get_payment_entry(
		dt=evidence.source_doctype,
		dn=evidence.source_name,
		party_amount=evidence.amount,
		bank_amount=evidence.amount
	)
	
	pe.reference_no = evidence.provider_reference
	pe.reference_date = getdate(evidence.paid_on) if evidence.paid_on else getdate(nowdate())
	pe.remarks = f"Prepared from RetailEdge EdgePay Payment Evidence {evidence.name}"
	
	# Insert draft document (does NOT submit)
	pe.flags.ignore_validate = True
	pe.insert(ignore_permissions=True)
	
	# Update evidence document status
	evidence.db_set("payment_entry", pe.name)
	evidence.db_set("posting_status", "Draft Created")
	evidence.db_set("posting_preflight_message", "Draft Payment Entry created successfully.")
	evidence.db_set("posting_prepared_on", now_datetime())
	evidence.db_set("posting_prepared_by", frappe.session.user)
	
	return {
		"ok": True,
		"payment_entry": pe.name,
		"message": _("Draft Payment Entry created successfully.")
	}

def mark_edgepay_evidence_posting_ready(evidence_name):
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	evidence.db_set("posting_status", "Ready")
	return {"ok": True, "message": "Posting status marked as Ready."}

def mark_edgepay_evidence_posting_blocked(evidence_name, reason=None):
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))
	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	evidence.db_set("posting_status", "Blocked")
	if reason:
		evidence.db_set("posting_preflight_message", reason)
	return {"ok": True, "message": "Posting status marked as Blocked."}
