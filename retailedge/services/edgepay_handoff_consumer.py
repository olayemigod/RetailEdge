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

def process_edgepay_handoff(event):
	"""
	Processes a single payment handoff event, performing validation, logging, and status updates.
	"""
	event_name = event.get("name")
	try:
		validate_edgepay_handoff(event)
		
		# Validation succeeded: Create a local process log
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
			"processing_status": "Processed",
			"processed_on": frappe.utils.now_datetime()
		})
		log_doc.insert(ignore_permissions=True)
		
		# Mark delivered in EdgePay queue
		mark_edgepay_handoff_delivered(event_name)
		return True
		
	except Exception as e:
		redacted_err = redact_secrets(str(e))
		
		# Validation/processing failed: Create a failed process log
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
			
		# Mark failed in EdgePay queue
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
	# Limit type-casting safety
	limit_int = int(limit) if limit else 50
	events = fetch_pending_edgepay_handoffs(limit=limit_int)
	success_count = 0
	for event in events:
		if process_edgepay_handoff(event):
			success_count += 1
	return success_count

