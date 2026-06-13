# -*- coding: utf-8 -*-
import frappe
from frappe import _
from edgepayv1.edgepay.sdk import (
	get_pending_payment_handoffs,
	mark_payment_handoff_delivered,
	mark_payment_handoff_failed
)
from edgepayv1.edgepay.services.security import redact_secrets

def fetch_pending_edgepay_handoffs(limit=50):
	"""
	Fetches pending payment handoffs from EdgePay queue where source_app is RetailEdge.
	"""
	res = get_pending_payment_handoffs(source_app="RetailEdge", limit=limit)
	if not res or not res.get("ok"):
		return []
	
	events = res.get("data") or []
	# Extra safety filter
	filtered = [e for e in events if e.get("source_app") in ("RetailEdge", "retailedge")]
	return filtered

def validate_edgepay_handoff(event):
	"""
	Validates the structure, fields, and existence of the source document.
	"""
	required = ["source_app", "source_doctype", "source_name", "amount", "currency", "request_status"]
	for req in required:
		if not event.get(req):
			frappe.throw(_("Missing required event field: {0}").format(req))
			
	if event.get("source_app") not in ("RetailEdge", "retailedge"):
		frappe.throw(_("Invalid source_app: {0}").format(event.get("source_app")))
		
	try:
		amount = float(event.get("amount"))
		if amount <= 0:
			frappe.throw(_("Amount must be greater than zero"))
	except (ValueError, TypeError):
		frappe.throw(_("Invalid amount format"))
		
	# Confirm source document exists
	doc_type = event.get("source_doctype")
	doc_name = event.get("source_name")
	if not frappe.db.exists(doc_type, doc_name):
		frappe.throw(_("Source document {0} {1} does not exist").format(doc_type, doc_name))

def mark_edgepay_handoff_delivered(event_name):
	"""
	Invokes EdgePay SDK wrapper to mark event as Delivered.
	"""
	res = mark_payment_handoff_delivered(event_name)
	if not res or not res.get("ok"):
		msg = res.get("message") if res else "Unknown error"
		frappe.throw(_("Failed to mark handoff delivered: {0}").format(msg))
	return res

def mark_edgepay_handoff_failed(event_name, error_message):
	"""
	Invokes EdgePay SDK wrapper to mark event as Failed with a redacted error.
	"""
	redacted = redact_secrets(str(error_message))
	res = mark_payment_handoff_failed(event_name, error_message=redacted)
	if not res or not res.get("ok"):
		msg = res.get("message") if res else "Unknown error"
		frappe.throw(_("Failed to mark handoff failed: {0}").format(msg))
	return res

def upsert_payment_evidence(event, idempotency_key, review_status="Pending Review", processing_status=None, error_message=None):
	"""
	Creates or updates exactly one RetailEdge EdgePay Payment Evidence record idempotently.
	"""
	existing_name = frappe.db.get_value(
		"RetailEdge EdgePay Payment Evidence",
		{"idempotency_key": idempotency_key},
		"name"
	)
	
	if existing_name:
		doc = frappe.get_doc("RetailEdge EdgePay Payment Evidence", existing_name)
		proc_status = processing_status or "Evidence Updated"
	else:
		doc = frappe.new_doc("RetailEdge EdgePay Payment Evidence")
		proc_status = processing_status or "Evidence Created"
		doc.idempotency_key = idempotency_key
		doc.created_from_edgepay_handoff = 1

	doc.edgepay_handoff_event = event.get("name")
	doc.edgepay_payment_request = event.get("payment_request")
	doc.edgepay_payment_transaction = event.get("payment_transaction")
	doc.source_app = event.get("source_app")
	doc.source_doctype = event.get("source_doctype")
	doc.source_name = event.get("source_name")
	doc.provider = event.get("provider")
	doc.provider_reference = event.get("provider_reference")
	doc.transaction_reference = event.get("transaction_reference")
	doc.amount = event.get("amount")
	doc.currency = event.get("currency")
	doc.request_status = event.get("request_status")
	doc.transaction_status = event.get("transaction_status")
	
	if event.get("paid_on"):
		doc.paid_on = event.get("paid_on")
		
	doc.processing_status = proc_status
	doc.review_status = review_status
	
	if error_message:
		doc.error_message = error_message
		
	doc.save(ignore_permissions=True)
	return doc.name, proc_status

def process_edgepay_handoff(event):
	"""
	Processes a single payment handoff event, performing validation, logging, and evidence intake.
	"""
	event_name = event.get("name")
	if event.get("source_app") not in ("RetailEdge", "retailedge"):
		return False
		
	idempotency_key = f"{event_name}-{event.get('payment_request') or ''}-{event.get('payment_transaction') or ''}-{event.get('provider_reference') or ''}-{event.get('transaction_reference') or ''}"
	
	try:
		# 1. Validate formats and existence of source document
		validate_edgepay_handoff(event)
		
		doc_type = event.get("source_doctype")
		doc_name = event.get("source_name")
		
		# 2. Check for amount/currency mismatch against host source document
		doc = frappe.get_doc(doc_type, doc_name)
		source_amount = doc.get("grand_total") or doc.get("amount") or 0.0
		source_currency = doc.get("currency")
		
		from frappe.utils import flt
		amount_mismatch = flt(event.get("amount")) != flt(source_amount)
		currency_mismatch = bool(event.get("currency") and source_currency and event.get("currency").upper() != source_currency.upper())
		
		if amount_mismatch or currency_mismatch:
			err_msg = ""
			if amount_mismatch:
				err_msg += f"Amount mismatch: event {event.get('amount')}, source {source_amount}. "
			if currency_mismatch:
				err_msg += f"Currency mismatch: event {event.get('currency')}, source {source_currency}. "
				
			# Block or record as Exception review status safely
			upsert_payment_evidence(
				event, idempotency_key, review_status="Exception", 
				processing_status="Failed", error_message=err_msg
			)
			
			log_doc = frappe.get_doc({
				"doctype": "RetailEdge EdgePay Handoff Log",
				"edgepay_event": event_name,
				"source_doctype": doc_type,
				"source_name": doc_name,
				"provider_reference": event.get("provider_reference"),
				"amount": event.get("amount"),
				"currency": event.get("currency"),
				"request_status": event.get("request_status"),
				"transaction_status": event.get("transaction_status"),
				"processing_status": "Failed",
				"error_message": err_msg,
				"processed_on": frappe.utils.now_datetime()
			})
			log_doc.insert(ignore_permissions=True)
			
			mark_edgepay_handoff_failed(event_name, err_msg)
			return False
		
		# 3. Require provider_reference for Paid events
		if event.get("request_status") == "Paid" and not event.get("provider_reference"):
			frappe.throw(_("Missing provider_reference for Paid event"))
			
		# Determine review status
		if event.get("request_status") == "Paid":
			review_status = "Pending Review"
		elif event.get("request_status") in ("Failed", "Expired", "Cancelled"):
			review_status = "Rejected"
		else:
			review_status = "Pending Review"
			
		# Upsert Payment Evidence idempotently
		upsert_payment_evidence(event, idempotency_key, review_status=review_status, error_message=None)
		
		# Log handoff successfully
		log_doc = frappe.get_doc({
			"doctype": "RetailEdge EdgePay Handoff Log",
			"edgepay_event": event_name,
			"source_doctype": doc_type,
			"source_name": doc_name,
			"provider_reference": event.get("provider_reference"),
			"amount": event.get("amount"),
			"currency": event.get("currency"),
			"request_status": event.get("request_status"),
			"transaction_status": event.get("transaction_status"),
			"processing_status": "Processed",
			"processed_on": frappe.utils.now_datetime()
		})
		log_doc.insert(ignore_permissions=True)
		
		# Acknowledge event to EdgePay only after evidence and log are successfully persisted
		mark_edgepay_handoff_delivered(event_name)
		return True
		
	except Exception as e:
		redacted_err = redact_secrets(str(e))
		
		try:
			log_doc = frappe.get_doc({
				"doctype": "RetailEdge EdgePay Handoff Log",
				"edgepay_event": event_name,
				"source_doctype": event.get("source_doctype"),
				"source_name": event.get("source_name"),
				"provider_reference": event.get("provider_reference"),
				"amount": event.get("amount"),
				"currency": event.get("currency"),
				"request_status": event.get("request_status"),
				"transaction_status": event.get("transaction_status"),
				"processing_status": "Failed",
				"error_message": redacted_err,
				"processed_on": frappe.utils.now_datetime()
			})
			log_doc.insert(ignore_permissions=True)
		except Exception as log_ex:
			frappe.log_error(f"Failed to create RetailEdge EdgePay Handoff Log: {str(log_ex)}", "RetailEdge Handoff Log Error")
			
		if event.get("source_doctype") and event.get("source_name"):
			try:
				upsert_payment_evidence(
					event, idempotency_key, review_status="Exception", 
					processing_status="Failed", error_message=redacted_err
				)
			except Exception:
				pass

		try:
			mark_edgepay_handoff_failed(event_name, redacted_err)
		except Exception as fail_ex:
			frappe.log_error(f"Failed to mark RetailEdge handoff failed in EdgePay: {str(fail_ex)}", "RetailEdge Handoff Mark Failed Error")
			
		return False

@frappe.whitelist()
def process_pending_edgepay_handoffs(limit=50):
	"""
	Fetches and processes all pending EdgePay status handoffs for RetailEdge.
	"""
	limit_int = int(limit) if limit else 50
	events = fetch_pending_edgepay_handoffs(limit=limit_int)
	success_count = 0
	for event in events:
		if process_edgepay_handoff(event):
			success_count += 1
	return success_count

@frappe.whitelist()
def mark_edgepay_evidence_reviewed(evidence_name):
	"""
	Sets the review status of the specified payment evidence to 'Reviewed'.
	This method must NOT post accounting or mutate source documents.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found").format(evidence_name))
		
	doc = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	doc.review_status = "Reviewed"
	doc.save(ignore_permissions=True)
	
	return {
		"ok": True,
		"status": "success",
		"message": f"Payment evidence {evidence_name} marked as Reviewed",
		"data": {
			"name": doc.name,
			"review_status": doc.review_status
		}
	}

@frappe.whitelist()
def mark_edgepay_evidence_rejected(evidence_name, reason=None):
	"""
	Sets the review status of the specified payment evidence to 'Rejected'.
	This method must NOT post accounting or mutate source documents.
	"""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found").format(evidence_name))
		
	doc = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	doc.review_status = "Rejected"
	if reason:
		doc.error_message = redact_secrets(str(reason))
	doc.save(ignore_permissions=True)
	
	return {
		"ok": True,
		"status": "success",
		"message": f"Payment evidence {evidence_name} marked as Rejected",
		"data": {
			"name": doc.name,
			"review_status": doc.review_status
		}
	}
