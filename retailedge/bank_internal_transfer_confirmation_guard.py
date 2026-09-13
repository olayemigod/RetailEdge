from __future__ import annotations

import frappe
from frappe.utils import cstr

from retailedge import bank_internal_transfer_identity as identity

_INSTALL_MARKER = "_retailedge_internal_transfer_confirmation_guard_installed"


def validate_internal_transfer_confirmation_leg(doc):
	"""Validate a submitted Internal Transfer without emitting a legacy false conflict.

	Returns True only when this helper handled the document as an Internal Transfer.
	Ordinary Payment Entries return False so the existing workflow validator remains
	the authority for them.
	"""
	payment_entry = cstr(getattr(doc, "payment_entry", None)).strip()
	if (
		not payment_entry
		or getattr(doc, "sales_invoice", None)
		or not identity._is_submitted_internal_transfer(payment_entry)
	):
		return False

	other_bank_match = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"bank_transaction": doc.bank_transaction,
			"decision_status": "Confirmed",
			"name": ["!=", doc.name],
		},
		"name",
	)
	if other_bank_match:
		frappe.throw(f"Bank Transaction already has confirmed match {other_bank_match}.")

	same_leg = identity._same_leg_match_rows(
		payment_entry,
		doc.bank_transaction,
		confirmed_only=True,
		exclude_match=doc.name,
	)
	if same_leg:
		frappe.throw(
			"This Internal Transfer bank leg already has a confirmed bank match. "
			"Reopen, reject, or cancel that same-leg match before confirming another."
		)

	opposite = identity._opposite_confirmed_leg_rows(
		payment_entry,
		doc.bank_transaction,
		exclude_match=doc.name,
	)
	if len(opposite) > 1:
		frappe.throw(
			"Multiple confirmed opposite-leg Internal Transfer matches require manual review before confirmation."
		)

	# Zero opposite matches is the first bank leg. Exactly one is the legitimate
	# other bank side of the same immutable ERPNext Internal Transfer.
	return True


def install_internal_transfer_confirmation_guard():
	from retailedge import bank_transaction_match_workflow as workflow

	if getattr(workflow, _INSTALL_MARKER, False):
		return

	original_validate = workflow._validate_no_other_active_confirmed_match

	def validate_no_other_active_confirmed_match(doc):
		if validate_internal_transfer_confirmation_leg(doc):
			return None
		return original_validate(doc)

	workflow._validate_no_other_active_confirmed_match = validate_no_other_active_confirmed_match
	setattr(workflow, _INSTALL_MARKER, True)
