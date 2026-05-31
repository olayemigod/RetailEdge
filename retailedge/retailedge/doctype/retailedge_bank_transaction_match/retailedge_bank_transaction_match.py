from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import flt, fmt_money

from retailedge.bank_transaction_matching import get_amount_scenario_label


class RetailEdgeBankTransactionMatch(Document):
	def validate(self):
		self._validate_candidate_fields()
		self._validate_party_fields()
		self._sync_sales_invoice_party_fields()
		self._set_amount_difference()
		self._set_review_classification()
		self._set_readable_summaries()
		self._refresh_sync_readiness()

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

	def _validate_party_fields(self):
		allowed_party_types = {"Customer", "Supplier"}
		if not self.party_type:
			self.party_type = "Customer"
		if self.party_type not in allowed_party_types:
			frappe.throw("Party Type must be either Customer or Supplier.")
		if self.party and not frappe.db.exists(self.party_type, self.party):
			frappe.throw(f"{self.party_type} {self.party} does not exist.")

	def _sync_sales_invoice_party_fields(self):
		if not self.sales_invoice:
			return
		customer = frappe.db.get_value("Sales Invoice", self.sales_invoice, "customer")
		if not customer:
			frappe.throw(f"Sales Invoice {self.sales_invoice} does not have a customer.")
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

	def _set_readable_summaries(self):
		document_label = getattr(self, "suggested_document", None) or "no suggested document"
		if getattr(self, "suggested_document_type", None):
			document_label = f"{self.suggested_document_type} {document_label}"
		party = getattr(self, "customer", None) or getattr(self, "party", None)
		party_text = f" for {party}" if party else ""
		self.match_summary = (
			f"Bank amount {fmt_money(getattr(self, 'bank_amount', 0))} matched to {document_label}{party_text}. "
			f"Candidate amount: {fmt_money(getattr(self, 'candidate_amount', 0))}. "
			f"Variance: {fmt_money(getattr(self, 'amount_difference', 0))}. "
			f"Scenario: {getattr(self, 'amount_scenario', None) or 'Not specified'}. "
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
		lines = [
			f"Bank Amount: {fmt_money(getattr(self, 'bank_amount', 0))}",
			f"Suggested Match Amount: {fmt_money(getattr(self, 'candidate_amount', 0))}",
			f"Difference / Variance: {fmt_money(getattr(self, 'amount_difference', 0))}",
		]
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
