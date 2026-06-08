from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, fmt_money

from retailedge.bank_transaction_match_workflow import _resolve_matching_candidate
from retailedge.bank_transaction_matching import (
	_get_sales_invoice_doc,
	_invoice_payment_row_is_bank_matchable,
	_resolve_account_match_payload,
	_resolve_bank_transaction_canonical_account,
	get_amount_scenario_label,
	get_candidate_category_label,
	normalize_bank_transaction,
)
from retailedge.invoice_payment_audit import get_sales_invoice_payment_rows


class RetailEdgeBankTransactionMatch(Document):
	def validate(self):
		self._hydrate_bank_transaction_context()
		flags = getattr(self, "flags", None)
		if getattr(flags, "retailedge_preserve_reviewed_candidate", False):
			self._validate_candidate_fields()
			self._validate_party_fields()
			self._sync_sales_invoice_party_fields()
			self._set_review_classification()
			self._set_decision_summary_only()
			self._refresh_sync_readiness()
			return
		if getattr(flags, "retailedge_preserve_selected_candidate", False):
			self._validate_candidate_fields()
			self._validate_party_fields()
			self._sync_sales_invoice_party_fields()
			self._set_amount_difference()
			self._set_review_classification()
			self._set_readable_summaries()
			self._refresh_sync_readiness()
			return
		self._hydrate_candidate_context()
		self._validate_candidate_fields()
		self._validate_party_fields()
		self._sync_sales_invoice_party_fields()
		self._set_amount_difference()
		self._set_review_classification()
		self._set_readable_summaries()
		self._refresh_sync_readiness()

	def _hydrate_bank_transaction_context(self):
		bank_transaction = getattr(self, "bank_transaction", None)
		if not bank_transaction:
			return
		context = _build_bank_transaction_context(bank_transaction)
		for fieldname, value in context.items():
			if value not in (None, "") or fieldname in {"bank_reference", "bank_narration"}:
				setattr(self, fieldname, value)
		self._retailedge_bank_context = context

	def _hydrate_candidate_context(self):
		flags = getattr(self, "flags", None)
		if getattr(flags, "retailedge_preserve_reviewed_candidate", False) or getattr(flags, "retailedge_preserve_selected_candidate", False):
			return
		suggested_document_type = getattr(self, "suggested_document_type", None)
		suggested_document = getattr(self, "suggested_document", None)
		if not suggested_document_type or not suggested_document:
			return
		context = _resolve_manual_candidate_context(
			bank_transaction=getattr(self, "bank_transaction", None),
			suggested_document_type=suggested_document_type,
			suggested_document=suggested_document,
			sales_invoice=getattr(self, "sales_invoice", None),
			payment_entry=getattr(self, "payment_entry", None),
		)
		for fieldname, value in context.get("doc_values", {}).items():
			if value is not None:
				setattr(self, fieldname, value)
		if context.get("details") or getattr(self, "_retailedge_bank_context", None):
			self.details_json = json.dumps(
				{
					"bank_context": getattr(self, "_retailedge_bank_context", None) or {},
					"candidate_context": context.get("details", {}),
				},
				default=str,
				sort_keys=True,
			)
		self._retailedge_candidate_context = context

	def _validate_candidate_fields(self):
		if not self.bank_transaction:
			frappe.throw("Bank Transaction is required.")
		if not self.suggested_document_type or not self.suggested_document:
			frappe.throw(
				"Cannot save Bank Match Review because no Sales Invoice, Payment Entry, or payment event candidate was found."
			)
		if self.suggested_document_type not in {"Sales Invoice", "Payment Entry"}:
			frappe.throw("Suggested Document Type must be either Sales Invoice or Payment Entry.")
		if not frappe.db.exists(self.suggested_document_type, self.suggested_document):
			frappe.throw(f"{self.suggested_document_type} {self.suggested_document} does not exist.")
		candidate_context = getattr(self, "_retailedge_candidate_context", None) or {}
		if candidate_context.get("block_reason"):
			frappe.throw(candidate_context.get("block_reason"))

	def _validate_party_fields(self):
		allowed_party_types = {"Customer", "Supplier"}
		if not self.party_type:
			self.party_type = "Customer"
		if self.party_type not in allowed_party_types:
			frappe.throw("Party Type must be either Customer or Supplier.")
		if self.party and not frappe.db.exists(self.party_type, self.party):
			frappe.throw(f"{self.party_type} {self.party} does not exist.")

	def _sync_sales_invoice_party_fields(self):
		sales_invoice = getattr(self, "sales_invoice", None)
		if not sales_invoice:
			return
		customer = frappe.db.get_value("Sales Invoice", sales_invoice, "customer")
		if not customer:
			frappe.throw(f"Sales Invoice {sales_invoice} does not have a customer.")
		self.party_type = "Customer"
		self.party = customer
		self.customer = customer

	def _set_amount_difference(self):
		self.bank_amount = flt(self.bank_amount)
		self.candidate_amount = flt(self.candidate_amount)
		self.amount_difference = flt(self.bank_amount) - flt(self.candidate_amount)
		if getattr(self, "amount_scenario", None):
			self.amount_scenario = get_amount_scenario_label(self.amount_scenario)

	def _set_review_classification(self):
		self.candidate_type = getattr(self, "suggested_document_type", None)
		self.match_status = getattr(self, "match_confidence", None) or "No Match"
		status = self.decision_status or "Suggested"
		if status == "Confirmed":
			self.review_status = "Confirmed"
			self.risk_level = "Low"
			return
		if status == "Rejected":
			self.review_status = "Rejected"
			self.risk_level = "Blocked"
			return
		if status == "Cancelled":
			self.review_status = "Cancelled"
			self.risk_level = "Blocked"
			return
		if status == "Reopened":
			self.review_status = "Reopened"
		elif status == "Needs Review":
			self.review_status = "Needs Review"
		elif getattr(self, "match_confidence", None) == "Strong Match" and abs(flt(self.amount_difference)) <= 0.01:
			self.review_status = "Ready to Confirm"
		else:
			self.review_status = "Pending Review"

		if getattr(self, "match_confidence", None) == "Strong Match" and abs(flt(self.amount_difference)) <= 0.01:
			self.risk_level = "Low"
		elif getattr(self, "match_confidence", None) == "Possible Match":
			self.risk_level = "Medium"
		else:
			self.risk_level = "High"

	def _set_decision_summary_only(self):
		status = getattr(self, "decision_status", None) or "Suggested"
		if status == "Suggested":
			self.decision_summary = "Suggested - awaiting review."
		elif getattr(self, "last_action_by", None) and getattr(self, "last_action_on", None):
			self.decision_summary = f"{status} by {self.last_action_by} on {self.last_action_on}."
		else:
			self.decision_summary = f"{status}."

	def _set_readable_summaries(self):
		document_label = getattr(self, "suggested_document", None) or "no suggested document"
		if getattr(self, "suggested_document_type", None):
			document_label = f"{self.suggested_document_type} {document_label}"
		party = getattr(self, "customer", None) or getattr(self, "party", None)
		party_text = f" for {party}" if party else ""
		candidate_context = getattr(self, "_retailedge_candidate_context", None) or {}
		candidate_details = candidate_context.get("details", {})
		category_label = get_candidate_category_label(candidate_details.get("candidate_category")) or "Not specified"
		self.match_summary = (
			f"Bank amount {fmt_money(getattr(self, 'bank_amount', 0))} matched to {document_label}{party_text}. "
			f"Candidate amount: {fmt_money(getattr(self, 'candidate_amount', 0))}. "
			f"Variance: {fmt_money(getattr(self, 'amount_difference', 0))}. "
			f"Scenario: {getattr(self, 'amount_scenario', None) or 'Not specified'}. "
			f"Candidate Category: {category_label}. "
			f"Confidence: {getattr(self, 'match_confidence', None) or 'No Match'} "
			f"({getattr(self, 'match_score', 0) or 0}). Risk: {getattr(self, 'risk_level', None) or 'High'}."
		)
		self.amount_breakdown_summary = self._build_amount_breakdown_summary()
		self.match_reason_summary = getattr(self, "match_reason", None) or "No match reason recorded."
		status = getattr(self, "decision_status", None) or "Suggested"
		if status == "Suggested":
			self.decision_summary = "Suggested - awaiting review."
		elif getattr(self, "last_action_by", None) and getattr(self, "last_action_on", None):
			self.decision_summary = f"{status} by {self.last_action_by} on {self.last_action_on}."
		else:
			self.decision_summary = f"{status}."

	def _build_amount_breakdown_summary(self):
		bank_context = getattr(self, "_retailedge_bank_context", None) or {}
		candidate_context = getattr(self, "_retailedge_candidate_context", None) or {}
		candidate_details = candidate_context.get("details", {})
		lines = [
			f"Bank Amount: {fmt_money(getattr(self, 'bank_amount', 0))}",
			f"Suggested Match Amount: {fmt_money(getattr(self, 'candidate_amount', 0))}",
			f"Difference / Variance: {fmt_money(getattr(self, 'amount_difference', 0))}",
		]
		if bank_context.get("resolved_bank_account"):
			lines.append(f"Resolved Bank Account: {bank_context.get('resolved_bank_account')}")
		if bank_context.get("bank_direction"):
			lines.append(f"Direction: {bank_context.get('bank_direction')}")
		if candidate_details.get("posting_date"):
			lines.append(f"Candidate Posting Date: {candidate_details.get('posting_date')}")
		if candidate_details.get("payment_event_source"):
			lines.append(f"Payment Event Source: {candidate_details.get('payment_event_source')}")
		if candidate_details.get("payment_row_index") not in (None, ""):
			lines.append(f"Payment Row Index: {candidate_details.get('payment_row_index')}")
		if candidate_details.get("payment_mode"):
			lines.append(f"Mode of Payment: {candidate_details.get('payment_mode')}")
		if candidate_details.get("payment_account"):
			lines.append(f"Payment Account: {candidate_details.get('payment_account')}")
		if candidate_details.get("resolved_payment_account"):
			lines.append(f"Resolved Payment Account: {candidate_details.get('resolved_payment_account')}")
		if candidate_details.get("reference"):
			lines.append(f"Candidate Reference: {candidate_details.get('reference')}")
		if getattr(self, "amount_scenario", None):
			lines.append(f"Scenario: {self.amount_scenario}")
		if getattr(self, "match_confidence", None):
			lines.append(f"Match Confidence: {self.match_confidence}")
		if getattr(self, "match_score", None) is not None:
			lines.append(f"Match Score: {self.match_score or 0}")
		if getattr(self, "match_reason", None):
			lines.append(f"Issue / Reason: {self.match_reason}")
		return "\n".join(lines)

	def _refresh_sync_readiness(self):
		if self.synced_to_sales_invoice:
			self.sales_invoice_sync_ready = 0
			self.sync_blocked_reason = "Already synced to Sales Invoice."
			return
		if self.decision_status != "Confirmed":
			self.sales_invoice_sync_ready = 0
			self.sync_blocked_reason = "Decision is not confirmed yet."
			return
		if not self.sales_invoice:
			self.sales_invoice_sync_ready = 0
			self.sync_blocked_reason = "No Sales Invoice is linked to this match."
			return
		self.sales_invoice_sync_ready = 1
		self.sync_blocked_reason = None


def _build_bank_transaction_context(bank_transaction_name):
	bank_transaction = normalize_bank_transaction(bank_transaction_name)
	account_payload = _resolve_bank_transaction_canonical_account(bank_transaction)
	return {
		"bank_transaction": bank_transaction.get("bank_transaction"),
		"company": bank_transaction.get("company"),
		"branch": bank_transaction.get("branch"),
		"bank_account": bank_transaction.get("bank_account"),
		"transaction_date": bank_transaction.get("transaction_date"),
		"bank_amount": flt(bank_transaction.get("amount")),
		"bank_reference": bank_transaction.get("reference"),
		"bank_narration": bank_transaction.get("description"),
		"bank_direction": bank_transaction.get("direction"),
		"bank_party": bank_transaction.get("party"),
		"resolved_bank_account": account_payload.get("canonical_account"),
	}


def _resolve_manual_candidate_context(
	bank_transaction=None,
	suggested_document_type=None,
	suggested_document=None,
	sales_invoice=None,
	payment_entry=None,
):
	suggested_document_type = cstr(suggested_document_type).strip()
	suggested_document = cstr(suggested_document or sales_invoice or payment_entry).strip()
	if not suggested_document_type or not suggested_document:
		return {"doc_values": {}, "details": {}, "block_reason": "No match candidate found."}
	candidate = None
	if bank_transaction:
		candidate = _resolve_matching_candidate(
			bank_transaction_name=bank_transaction,
			suggested_document_type=suggested_document_type,
			suggested_document=suggested_document,
			sales_invoice=sales_invoice or (suggested_document if suggested_document_type == "Sales Invoice" else None),
			payment_entry=payment_entry or (suggested_document if suggested_document_type == "Payment Entry" else None),
		)
	if not candidate:
		candidate = _build_source_candidate_context(suggested_document_type, suggested_document)
	if not candidate:
		if suggested_document_type == "Sales Invoice":
			return {
				"doc_values": {},
				"details": {},
				"block_reason": "Sales Invoice is context only; payment event evidence is required for review creation and auto-match.",
			}
		return {
			"doc_values": {},
			"details": {},
			"block_reason": "Cannot create review record because no Sales Invoice, Payment Entry, or payment event candidate was found.",
		}
	candidate = frappe._dict(candidate)
	bank_context = _build_bank_transaction_context(bank_transaction) if bank_transaction else {}
	account_payload = _resolve_account_match_payload(bank_context, candidate) if bank_context else {}
	details = {
		"candidate_category": candidate.get("candidate_category"),
		"candidate_category_label": get_candidate_category_label(candidate.get("candidate_category")),
		"payment_event_source": candidate.get("payment_event_source"),
		"payment_row_index": candidate.get("payment_row_index"),
		"payment_mode": candidate.get("payment_mode"),
		"payment_account": candidate.get("payment_account"),
		"resolved_payment_account": account_payload.get("candidate_canonical_account") or candidate.get("account") or candidate.get("payment_account"),
		"posting_date": candidate.get("posting_date"),
		"reference": candidate.get("reference"),
		"account_resolution_status": account_payload.get("status"),
		"account_resolution_reason": account_payload.get("reason"),
		"reasons": list(candidate.get("reasons") or []),
	}
	doc_values = {
		"company": bank_context.get("company") or candidate.get("company"),
		"branch": bank_context.get("branch") or candidate.get("branch"),
		"suggested_document_type": candidate.get("document_type") or suggested_document_type,
		"suggested_document": candidate.get("document_name") or suggested_document,
		"sales_invoice": candidate.get("suggested_sales_invoice")
		if (candidate.get("document_type") or suggested_document_type) == "Sales Invoice"
		else candidate.get("suggested_sales_invoice") or sales_invoice,
		"payment_entry": candidate.get("document_name")
		if (candidate.get("document_type") or suggested_document_type) == "Payment Entry"
		else payment_entry,
		"customer": candidate.get("customer"),
		"party_type": candidate.get("party_type") or "Customer",
		"party": candidate.get("party") or candidate.get("customer"),
		"candidate_amount": flt(candidate.get("candidate_amount")),
		"match_confidence": candidate.get("confidence") or "No Match",
		"match_score": cint(candidate.get("score") or 0),
		"amount_scenario": get_amount_scenario_label(candidate.get("amount_scenario")) or candidate.get("amount_scenario"),
		"match_reason": _build_candidate_reason_summary(candidate, details, account_payload),
		"candidate_posting_date": candidate.get("posting_date"),
		"payment_event_source": details.get("payment_event_source"),
		"payment_row_index": details.get("payment_row_index"),
		"payment_mode": details.get("payment_mode"),
		"payment_account": details.get("payment_account"),
		"resolved_payment_account": details.get("resolved_payment_account"),
		"account_resolution_status": details.get("account_resolution_status"),
	}
	if bank_context:
		doc_values.update(bank_context)
		doc_values["amount_difference"] = flt(bank_context.get("bank_amount")) - flt(doc_values.get("candidate_amount"))
	return {"doc_values": doc_values, "details": details, "candidate": candidate, "block_reason": None}


def _build_source_candidate_context(suggested_document_type, suggested_document):
	if suggested_document_type == "Payment Entry":
		return _build_payment_entry_source_candidate(suggested_document)
	if suggested_document_type == "Sales Invoice":
		return _build_sales_invoice_source_candidate(suggested_document)
	return None


def _build_payment_entry_source_candidate(payment_entry_name):
	fields = [
		"name",
		"posting_date",
		"company",
		"party",
		"party_type",
		"payment_type",
		"paid_from",
		"paid_to",
		"paid_amount",
		"received_amount",
		"reference_no",
		"remarks",
	]
	if frappe.get_meta("Payment Entry").has_field("mode_of_payment"):
		fields.append("mode_of_payment")
	if frappe.get_meta("Payment Entry").has_field("retailedge_branch"):
		fields.append("retailedge_branch")
	payload = frappe.db.get_value("Payment Entry", payment_entry_name, fields, as_dict=True)
	if not payload:
		return None
	account = cstr(payload.get("paid_to") or payload.get("paid_from")).strip()
	if cstr(payload.get("mode_of_payment")).strip().lower() == "cash":
		return None
	return {
		"document_type": "Payment Entry",
		"document_name": payment_entry_name,
		"posting_date": payload.get("posting_date"),
		"company": payload.get("company"),
		"branch": payload.get("retailedge_branch"),
		"customer": payload.get("party"),
		"party": payload.get("party"),
		"party_type": payload.get("party_type") or "Customer",
		"candidate_amount": flt(payload.get("received_amount") or payload.get("paid_amount")),
		"candidate_category": "payment_entry_match",
		"payment_event_source": "Payment Entry",
		"payment_mode": payload.get("mode_of_payment"),
		"payment_account": account,
		"account": account,
		"reference": payload.get("reference_no") or payload.get("name"),
		"payment_entry_paid_amount": flt(payload.get("received_amount") or payload.get("paid_amount")),
		"amount_scenario": "Submitted Payment Entry Amount",
		"confidence": "Possible Match",
		"score": 0,
		"reasons": [_("Matched submitted Payment Entry.")],
	}


def _build_sales_invoice_source_candidate(invoice_name):
	invoice_doc = _get_sales_invoice_doc({"name": invoice_name})
	if not invoice_doc or cstr(getattr(invoice_doc, "docstatus", 1)) != "1":
		return None
	try:
		payment_rows = get_sales_invoice_payment_rows(invoice_doc)
	except Exception:
		payment_rows = []
	bank_rows = [row for row in payment_rows if _invoice_payment_row_is_bank_matchable(row)]
	if not bank_rows:
		return None
	best_row = sorted(bank_rows, key=lambda row: flt(row.get("base_amount") or row.get("amount")), reverse=True)[0]
	category = "pos_payment_match" if cstr(best_row.get("payment_category")).strip() == "Card / POS" else "invoice_payment_row_match"
	return {
		"document_type": "Sales Invoice",
		"document_name": invoice_name,
		"suggested_sales_invoice": invoice_name,
		"posting_date": cstr(getattr(invoice_doc, "posting_date", None) or ""),
		"company": getattr(invoice_doc, "company", None),
		"branch": getattr(invoice_doc, "retailedge_branch", None) or getattr(invoice_doc, "branch", None),
		"customer": getattr(invoice_doc, "customer", None),
		"party": getattr(invoice_doc, "customer", None),
		"party_type": "Customer",
		"candidate_amount": flt(best_row.get("base_amount") or best_row.get("amount")),
		"candidate_category": category,
		"payment_event_source": "POS Payment Row" if category == "pos_payment_match" else "Invoice Payment Row",
		"payment_row_index": best_row.get("payment_row_index"),
		"payment_mode": best_row.get("mode_of_payment"),
		"payment_account": best_row.get("account") or best_row.get("expected_account"),
		"account": best_row.get("account") or best_row.get("expected_account"),
		"reference": best_row.get("reference") or best_row.get("reference_no") or invoice_name,
		"payment_row_amount": flt(best_row.get("base_amount") or best_row.get("amount")),
		"amount_scenario": "Exact Invoice Payment Row Amount",
		"confidence": "Possible Match",
		"score": 0,
		"reasons": [_("Matched invoice payment row.")],
	}


def _build_candidate_reason_summary(candidate, details, account_payload):
	lines = list(candidate.get("reasons") or [])
	if details.get("candidate_category_label"):
		lines.append(f"Candidate Category: {details.get('candidate_category_label')}")
	if details.get("payment_event_source"):
		lines.append(f"Payment Event Source: {details.get('payment_event_source')}")
	if details.get("posting_date"):
		lines.append(f"Candidate Posting Date: {details.get('posting_date')}")
	if details.get("payment_mode"):
		lines.append(f"Mode of Payment: {details.get('payment_mode')}")
	if details.get("payment_account"):
		lines.append(f"Payment Account: {details.get('payment_account')}")
	if details.get("resolved_payment_account"):
		lines.append(f"Resolved Payment Account: {details.get('resolved_payment_account')}")
	if details.get("reference"):
		lines.append(f"Reference: {details.get('reference')}")
	if account_payload and account_payload.get("reason"):
		lines.append(account_payload.get("reason"))
	return "; ".join(line for line in lines if line)


@frappe.whitelist()
def get_bank_transaction_match_form_context(
	bank_transaction=None,
	suggested_document_type=None,
	suggested_document=None,
	sales_invoice=None,
	payment_entry=None,
):
	context = {}
	if bank_transaction:
		context.update(_build_bank_transaction_context(bank_transaction))
	if suggested_document_type and (suggested_document or sales_invoice or payment_entry):
		candidate_context = _resolve_manual_candidate_context(
			bank_transaction=bank_transaction,
			suggested_document_type=suggested_document_type,
			suggested_document=suggested_document,
			sales_invoice=sales_invoice,
			payment_entry=payment_entry,
		)
		context.update(candidate_context.get("doc_values", {}))
		context["details_json"] = json.dumps(
			{
				"bank_context": _build_bank_transaction_context(bank_transaction) if bank_transaction else {},
				"candidate_context": candidate_context.get("details", {}),
			},
			default=str,
			sort_keys=True,
		)
		if candidate_context.get("block_reason"):
			context["block_reason"] = candidate_context.get("block_reason")
	return context
