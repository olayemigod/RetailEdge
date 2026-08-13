from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


def get_edgepay_bank_match_review_preflight(evidence_name, bank_transaction_name=None):
	"""Validate whether external payment evidence can enter RetailEdge bank-match review."""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		return {"ok": False, "message": f"Payment Evidence {evidence_name} not found."}

	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)

	if evidence.review_status != "Reviewed":
		return {
			"ok": False,
			"message": f"Payment Evidence is not Reviewed. Current status: {evidence.review_status}.",
		}

	if evidence.submission_status != "Submitted":
		return {
			"ok": False,
			"message": (
				"Payment Evidence submission status is not Submitted. "
				f"Current status: {evidence.submission_status}."
			),
		}

	if evidence.posting_status != "Submitted":
		return {
			"ok": False,
			"message": (
				"Payment Evidence posting status is not Submitted. "
				f"Current status: {evidence.posting_status}."
			),
		}

	# EdgePay is a standalone remote platform. This field refers only to the
	# RetailEdge-side Payment Entry produced/linked from accepted payment evidence.
	if not evidence.payment_entry:
		return {"ok": False, "message": "No linked RetailEdge Payment Entry on payment evidence."}

	if not frappe.db.exists("Payment Entry", evidence.payment_entry):
		return {
			"ok": False,
			"message": f"Linked Payment Entry {evidence.payment_entry} does not exist.",
		}

	pe_doc = frappe.get_doc("Payment Entry", evidence.payment_entry)
	if pe_doc.docstatus != 1:
		return {
			"ok": False,
			"message": f"Linked Payment Entry {evidence.payment_entry} is not submitted.",
		}

	from retailedge.services.edgepay_reconciliation_readiness import (
		get_edgepay_reconciliation_readiness,
	)

	readiness = get_edgepay_reconciliation_readiness(evidence_name)
	if readiness.get("status") == "Reconciled":
		return {
			"ok": False,
			"message": "A completed reconciliation already exists for this payment evidence.",
		}

	if not readiness.get("ok") and readiness.get("status") not in ("Ready", "Matched"):
		return {
			"ok": False,
			"message": readiness.get("message") or "Evidence is not reconciliation-ready.",
		}

	confirmed_pe_match = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"payment_entry": evidence.payment_entry,
			"decision_status": "Confirmed",
		},
		"name",
	)
	if confirmed_pe_match:
		if bank_transaction_name:
			confirmed_bt = frappe.db.get_value(
				"RetailEdge Bank Transaction Match",
				confirmed_pe_match,
				"bank_transaction",
			)
			if confirmed_bt == bank_transaction_name:
				return {
					"ok": True,
					"message": (
						"A confirmed match review already exists for this bank transaction "
						"and payment entry."
					),
					"review_name": confirmed_pe_match,
				}
		return {
			"ok": False,
			"message": (
				f"Payment Entry {evidence.payment_entry} already has a confirmed bank "
				f"match review: {confirmed_pe_match}."
			),
		}

	if bank_transaction_name:
		if not frappe.db.exists("Bank Transaction", bank_transaction_name):
			return {
				"ok": False,
				"message": f"Selected Bank Transaction {bank_transaction_name} does not exist.",
			}

		bt = frappe.get_doc("Bank Transaction", bank_transaction_name)
		if bt.docstatus != 1:
			return {
				"ok": False,
				"message": f"Bank Transaction {bank_transaction_name} is not submitted.",
			}
		if bt.status == "Reconciled":
			return {
				"ok": False,
				"message": f"Bank Transaction {bank_transaction_name} is already reconciled.",
			}

		from retailedge.bank_transaction_matching import get_bank_transaction_matching_settings

		settings = get_bank_transaction_matching_settings()
		tolerance = flt(settings.get("amount_tolerance") or 0.0)
		diff = abs(flt(bt.deposit) - flt(evidence.amount))
		if diff > max(tolerance, 0.01):
			return {
				"ok": False,
				"message": (
					f"Amount mismatch: Bank Transaction deposit {bt.deposit} does not match "
					f"evidence amount {evidence.amount} within tolerance {tolerance}."
				),
			}

		if bt.currency and evidence.currency and bt.currency.upper() != evidence.currency.upper():
			return {
				"ok": False,
				"message": (
					f"Currency mismatch: Bank Transaction currency {bt.currency} does not "
					f"match evidence currency {evidence.currency}."
				),
			}

		confirmed_bt_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": bank_transaction_name,
				"decision_status": "Confirmed",
			},
			"name",
		)
		if confirmed_bt_match:
			return {
				"ok": False,
				"message": (
					f"Bank Transaction {bank_transaction_name} already has a confirmed bank "
					f"match review: {confirmed_bt_match}."
				),
			}

		existing_pair_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": bank_transaction_name,
				"payment_entry": evidence.payment_entry,
				"decision_status": ["not in", ["Rejected", "Cancelled"]],
			},
			"name",
		)
		if existing_pair_match:
			return {
				"ok": True,
				"message": "An active match review already exists for this pair.",
				"review_name": existing_pair_match,
			}

		active_bt_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"bank_transaction": bank_transaction_name,
				"decision_status": ["not in", ["Rejected", "Cancelled"]],
			},
			"name",
		)
		if active_bt_match:
			return {
				"ok": False,
				"message": (
					f"Bank Transaction {bank_transaction_name} already has an active review "
					f"record: {active_bt_match}."
				),
			}

		active_pe_match = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			{
				"payment_entry": evidence.payment_entry,
				"decision_status": ["not in", ["Rejected", "Cancelled"]],
			},
			"name",
		)
		if active_pe_match:
			return {
				"ok": False,
				"message": (
					f"Payment Entry {evidence.payment_entry} already has an active review "
					f"record: {active_pe_match}."
				),
			}

	if evidence.linked_bank_match_review and frappe.db.exists(
		"RetailEdge Bank Transaction Match", evidence.linked_bank_match_review
	):
		status = frappe.db.get_value(
			"RetailEdge Bank Transaction Match",
			evidence.linked_bank_match_review,
			"decision_status",
		)
		if status not in ("Rejected", "Cancelled"):
			if bank_transaction_name:
				bt_of_review = frappe.db.get_value(
					"RetailEdge Bank Transaction Match",
					evidence.linked_bank_match_review,
					"bank_transaction",
				)
				if bt_of_review == bank_transaction_name:
					return {
						"ok": True,
						"message": "Active match review already exists.",
						"review_name": evidence.linked_bank_match_review,
					}
				return {
					"ok": False,
					"message": (
						"Evidence is already linked to another active match review: "
						f"{evidence.linked_bank_match_review}."
					),
				}
			return {
				"ok": True,
				"message": "Active match review already exists.",
				"review_name": evidence.linked_bank_match_review,
			}

	return {"ok": True, "message": "Preflight validation passed."}


def _validate_retailedge_payment_entry_candidate(evidence, bank_transaction_name):
	"""Resolve and lock the candidate inside RetailEdge, never from EdgePay package code."""
	from retailedge.bank_transaction_match_workflow import validate_locked_candidate_from_selected_row

	selected_row = frappe._dict(
		{
			"bank_transaction": bank_transaction_name,
			"candidate_doctype": "Payment Entry",
			"candidate_name": evidence.payment_entry,
			"suggested_document_type": "Payment Entry",
			"suggested_document": evidence.payment_entry,
		}
	)
	validation = validate_locked_candidate_from_selected_row(selected_row)
	if not validation.get("valid"):
		frappe.throw(
			validation.get("reason")
			or "RetailEdge could not validate the payment entry as the locked bank-match candidate."
		)
	return validation["candidate"]


def create_edgepay_bank_match_review(evidence_name, bank_transaction_name):
	"""Create a RetailEdge match review from already-ingested external payment evidence.

	EdgePay is remote and does not choose or substitute the reconciliation candidate.
	RetailEdge revalidates and locks the local candidate before creating the review.
	"""
	preflight = get_edgepay_bank_match_review_preflight(evidence_name, bank_transaction_name)
	if not preflight["ok"]:
		frappe.throw(preflight["message"])

	if preflight.get("review_name"):
		mark_edgepay_evidence_match_review_created(evidence_name, preflight["review_name"])
		return {
			"ok": True,
			"review_name": preflight["review_name"],
			"message": "Returned existing active match review.",
			"created": False,
		}

	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	locked_candidate = _validate_retailedge_payment_entry_candidate(
		evidence=evidence,
		bank_transaction_name=bank_transaction_name,
	)

	from retailedge.bank_transaction_match_workflow import create_or_get_bank_transaction_match

	res = create_or_get_bank_transaction_match(
		bank_transaction_name=bank_transaction_name,
		suggested_document_type="Payment Entry",
		suggested_document=evidence.payment_entry,
		payment_entry=evidence.payment_entry,
		source_report="External Payment Reconciliation Readiness",
		locked_candidate=locked_candidate,
		allow_fallback=False,
	)

	review_name = res["name"]
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", review_name)
	details = {}
	if doc.details_json:
		try:
			details = json.loads(doc.details_json)
		except Exception:
			details = {}
	details.update(
		{
			"external_payment_evidence": evidence_name,
			"edgepay_evidence": evidence_name,
			"provider_reference": evidence.provider_reference,
			"transaction_reference": evidence.transaction_reference,
			"candidate_owner": "RetailEdge",
			"candidate_fallback_allowed": False,
		}
	)
	doc.db_set("details_json", json.dumps(details, default=str, sort_keys=True))

	mark_edgepay_evidence_match_review_created(evidence_name, review_name)

	return {
		"ok": True,
		"review_name": review_name,
		"message": "Bank Match Review created successfully.",
		"created": True,
	}


def mark_edgepay_evidence_match_review_created(evidence_name, review_name):
	"""Link a RetailEdge match review back to stored external payment evidence."""
	if not frappe.db.exists("RetailEdge EdgePay Payment Evidence", evidence_name):
		frappe.throw(_("Payment Evidence {0} not found.").format(evidence_name))

	evidence = frappe.get_doc("RetailEdge EdgePay Payment Evidence", evidence_name)
	review = frappe.get_doc("RetailEdge Bank Transaction Match", review_name)

	evidence.db_set("reconciliation_status", "Matched")
	evidence.db_set("linked_bank_transaction", review.bank_transaction)
	evidence.db_set("linked_bank_match_review", review_name)
	evidence.db_set(
		"reconciliation_message",
		f"Bank Match Review created: {review_name} for Bank Transaction {review.bank_transaction}.",
	)
	evidence.db_set("reconciliation_checked_on", now_datetime())
	evidence.db_set("reconciliation_checked_by", frappe.session.user)
