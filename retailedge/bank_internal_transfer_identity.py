from __future__ import annotations

from contextlib import contextmanager

import frappe
from frappe.utils import cstr

_CONTEXT_ATTR = "_retailedge_internal_transfer_bank_transaction"
_INSTALL_MARKER = "_retailedge_internal_transfer_leg_identity_installed"
_INACTIVE_MATCH_STATUSES = {"Rejected", "Cancelled", "Reopened"}


def build_payment_entry_leg_key(
	payment_entry_name,
	payment_type,
	direction,
	paid_from=None,
	paid_to=None,
):
	"""Return the duplicate/conflict identity for a Payment Entry bank event.

	Ordinary Payment Entries remain document-scoped. Submitted Internal Transfers
	are bank-leg scoped because ERPNext legitimately exposes one source-bank
	outflow and one destination-bank inflow for the same immutable voucher.
	Unknown/ambiguous Internal Transfer direction fails closed to the legacy
	document-level identity.
	"""
	name = cstr(payment_entry_name).strip()
	if not name:
		return None
	if cstr(payment_type).strip() != "Internal Transfer":
		return ("Payment Entry", name)

	direction = cstr(direction).strip()
	if direction == "Inflow":
		account = cstr(paid_to).strip()
	elif direction == "Outflow":
		account = cstr(paid_from).strip()
	else:
		return ("Payment Entry", name)
	if not account:
		return ("Payment Entry", name)
	return ("Payment Entry", name, direction, account)


def _get_context_bank_transaction():
	try:
		return getattr(frappe.local, _CONTEXT_ATTR, None)
	except Exception:
		return None


@contextmanager
def _bank_transaction_context(bank_transaction):
	try:
		previous = getattr(frappe.local, _CONTEXT_ATTR, None)
		setattr(frappe.local, _CONTEXT_ATTR, bank_transaction)
	except Exception:
		previous = None
	try:
		yield
	finally:
		try:
			if previous is None and hasattr(frappe.local, _CONTEXT_ATTR):
				delattr(frappe.local, _CONTEXT_ATTR)
			else:
				setattr(frappe.local, _CONTEXT_ATTR, previous)
		except Exception:
			pass


def _payment_entry_metadata(payment_entry_name):
	"""Read only the immutable Payment Entry fields needed for leg identity.

	The leg-aware exception is allowed only when ERPNext returns a real mapping
	that proves this is a submitted Internal Transfer. Any unavailable, invalid,
	or ambiguous response fails closed to the legacy document-level identity.
	"""
	name = cstr(payment_entry_name).strip()
	if not name:
		return frappe._dict()
	try:
		row = frappe.db.get_value(
			"Payment Entry",
			name,
			["name", "payment_type", "paid_from", "paid_to", "docstatus"],
			as_dict=True,
		)
	except Exception:
		return frappe._dict()
	if not isinstance(row, dict):
		return frappe._dict()
	return frappe._dict(row)


def _is_submitted_internal_transfer(payment_entry_name):
	row = _payment_entry_metadata(payment_entry_name)
	return bool(
		cstr(row.get("payment_type")).strip() == "Internal Transfer"
		and int(row.get("docstatus") or 0) == 1
	)


def _bank_transaction_direction(bank_transaction):
	if isinstance(bank_transaction, dict):
		direction = cstr(bank_transaction.get("direction")).strip()
		if direction:
			return direction
		bank_transaction = bank_transaction.get("bank_transaction") or bank_transaction.get("name")
	name = cstr(bank_transaction).strip()
	if not name:
		return ""
	from retailedge.bank_transaction_matching import normalize_bank_transaction

	try:
		return cstr(normalize_bank_transaction(name).get("direction")).strip()
	except Exception:
		return ""


def _payment_entry_leg_key(payment_entry_name, bank_transaction):
	row = _payment_entry_metadata(payment_entry_name)
	return build_payment_entry_leg_key(
		payment_entry_name,
		row.get("payment_type"),
		_bank_transaction_direction(bank_transaction),
		paid_from=row.get("paid_from"),
		paid_to=row.get("paid_to"),
	)


def _active_payment_entry_match_rows(payment_entry_name, confirmed_only=False):
	name = cstr(payment_entry_name).strip()
	if not name:
		return []
	status_filter = "Confirmed" if confirmed_only else ["not in", sorted(_INACTIVE_MATCH_STATUSES)]
	fields = [
		"name",
		"bank_transaction",
		"decision_status",
		"suggested_document_type",
		"suggested_document",
		"payment_entry",
		"modified",
	]
	rows = []
	queries = (
		{
			"suggested_document_type": "Payment Entry",
			"suggested_document": name,
			"decision_status": status_filter,
		},
		{"payment_entry": name, "decision_status": status_filter},
	)
	for filters in queries:
		try:
			rows.extend(
				frappe.get_all(
					"RetailEdge Bank Transaction Match",
					filters=filters,
					fields=fields,
					limit_page_length=0,
					order_by="modified desc",
				)
			)
		except Exception:
			continue
	seen = set()
	output = []
	for raw in rows:
		row = frappe._dict(raw or {})
		row_name = cstr(row.get("name")).strip()
		if not row_name or row_name in seen:
			continue
		seen.add(row_name)
		output.append(row)
	return output


def _same_leg_match_rows(
	payment_entry_name,
	bank_transaction,
	confirmed_only=False,
	exclude_match=None,
):
	current_key = _payment_entry_leg_key(payment_entry_name, bank_transaction)
	rows = _active_payment_entry_match_rows(payment_entry_name, confirmed_only=confirmed_only)
	exclude_match = cstr(exclude_match).strip()
	if not current_key or len(current_key) == 2:
		return [row for row in rows if cstr(row.get("name")).strip() != exclude_match]

	result = []
	for row in rows:
		if cstr(row.get("name")).strip() == exclude_match:
			continue
		other_key = _payment_entry_leg_key(payment_entry_name, row.get("bank_transaction"))
		# Ambiguous historical identity stays conflicting rather than weakening safety.
		if not other_key or len(other_key) == 2 or other_key == current_key:
			result.append(row)
	return result


def _opposite_confirmed_leg_rows(payment_entry_name, bank_transaction, exclude_match=None):
	current_key = _payment_entry_leg_key(payment_entry_name, bank_transaction)
	if not current_key or len(current_key) == 2:
		return []
	exclude_match = cstr(exclude_match).strip()
	result = []
	for row in _active_payment_entry_match_rows(payment_entry_name, confirmed_only=True):
		if cstr(row.get("name")).strip() == exclude_match:
			continue
		other_key = _payment_entry_leg_key(payment_entry_name, row.get("bank_transaction"))
		if other_key and len(other_key) > 2 and other_key != current_key:
			result.append(row)
	return result


def _patched_candidate_document_key(original, row):
	row = frappe._dict(row or {})
	document_type = cstr(row.get("suggested_document_type") or row.get("document_type")).strip()
	document_name = cstr(row.get("suggested_document") or row.get("document_name")).strip()
	if document_type != "Payment Entry" or not document_name:
		return original(row)

	# A leg-aware key is safe only when the current row already carries explicit
	# direction + bank-ledger evidence. If either is absent, preserve the legacy
	# document-level key instead of doing extra lookups or guessing a bank leg.
	direction = cstr(row.get("direction") or row.get("bank_direction")).strip()
	payment_account = cstr(row.get("payment_account") or row.get("account")).strip()
	if direction not in {"Inflow", "Outflow"} or not payment_account:
		return original(row)
	if not _is_submitted_internal_transfer(document_name):
		return original(row)
	return ("Payment Entry", document_name, direction, payment_account)


def install_internal_transfer_bank_leg_identity():
	"""Install a narrow bank-leg-aware duplicate policy for Internal Transfers.

	This does not change ERPNext vouchers, candidate accounting eligibility, or
	reconciliation execution. It only changes RetailEdge duplicate/conflict
	identity when the same submitted Internal Transfer legitimately represents
	two different bank statement legs.
	"""
	from retailedge import bank_transaction_matching as matching

	if getattr(matching, _INSTALL_MARKER, False):
		return

	original_find_payment_entries = matching.find_payment_entry_candidates_for_bank_transaction
	original_candidate_confirmed = matching.candidate_document_has_active_confirmed_bank_match
	original_active_review = matching._active_review_match_for_candidate
	original_candidate_key = matching.get_candidate_document_key

	def candidate_document_has_active_confirmed_bank_match(document_type, document_name):
		legacy_conflict = original_candidate_confirmed(document_type, document_name)
		if not legacy_conflict:
			return False
		if cstr(document_type).strip() == "Payment Entry":
			bank_transaction = _get_context_bank_transaction()
			if bank_transaction and _is_submitted_internal_transfer(document_name):
				return bool(
					_same_leg_match_rows(
						document_name,
						bank_transaction,
						confirmed_only=True,
					)
				)
		return True

	def payment_entry_has_active_confirmed_bank_match(payment_entry):
		return candidate_document_has_active_confirmed_bank_match("Payment Entry", payment_entry)

	def active_review_match_for_candidate(document_type, document_name):
		legacy_match = original_active_review(document_type, document_name)
		if not legacy_match:
			return None
		if cstr(document_type).strip() == "Payment Entry":
			bank_transaction = _get_context_bank_transaction()
			if bank_transaction and _is_submitted_internal_transfer(document_name):
				rows = _same_leg_match_rows(document_name, bank_transaction, confirmed_only=False)
				return rows[0] if rows else None
		return legacy_match

	def find_payment_entry_candidates_for_bank_transaction(
		bank_transaction_name,
		filters=None,
		limit=20,
		context=None,
	):
		with _bank_transaction_context(bank_transaction_name):
			return original_find_payment_entries(
				bank_transaction_name,
				filters=filters,
				limit=limit,
				context=context,
			)

	def get_candidate_document_key(row):
		return _patched_candidate_document_key(original_candidate_key, row)

	matching.payment_entry_has_active_confirmed_bank_match = payment_entry_has_active_confirmed_bank_match
	matching.candidate_document_has_active_confirmed_bank_match = candidate_document_has_active_confirmed_bank_match
	matching._active_review_match_for_candidate = active_review_match_for_candidate
	matching.find_payment_entry_candidates_for_bank_transaction = find_payment_entry_candidates_for_bank_transaction
	matching.get_candidate_document_key = get_candidate_document_key

	from retailedge import bank_transaction_match_workflow as workflow

	# Workflow imports these names directly from bank_transaction_matching.
	workflow.payment_entry_has_active_confirmed_bank_match = payment_entry_has_active_confirmed_bank_match
	workflow.candidate_document_has_active_confirmed_bank_match = candidate_document_has_active_confirmed_bank_match
	original_find_active_candidate_review = workflow._find_active_candidate_review_match
	original_classify_preparation = workflow._classify_suggestion_review_preparation
	original_validate_locked = workflow._validate_locked_candidate_from_selected_row
	original_first_confirmed_conflict = workflow._get_first_active_confirmed_conflict
	original_validate_no_confirmed = workflow._validate_no_other_active_confirmed_match

	def find_active_candidate_review_match(suggested_document_type, suggested_document):
		legacy_match = original_find_active_candidate_review(suggested_document_type, suggested_document)
		if not legacy_match:
			return None
		if cstr(suggested_document_type).strip() == "Payment Entry":
			bank_transaction = _get_context_bank_transaction()
			if bank_transaction and _is_submitted_internal_transfer(suggested_document):
				rows = _same_leg_match_rows(suggested_document, bank_transaction, confirmed_only=False)
				return cstr(rows[0].get("name")).strip() if rows else None
		return legacy_match

	def classify_suggestion_review_preparation(row, *args, **kwargs):
		bank_transaction = cstr((row or {}).get("bank_transaction")).strip()
		with _bank_transaction_context(bank_transaction):
			return original_classify_preparation(row, *args, **kwargs)

	def validate_locked_candidate_from_selected_row(row):
		row = frappe._dict(row or {})
		bank_transaction = cstr(row.get("bank_transaction")).strip()
		candidate_type = cstr(row.get("candidate_doctype") or row.get("suggested_document_type")).strip()
		candidate_name = cstr(row.get("candidate_name") or row.get("suggested_document")).strip()
		with _bank_transaction_context(bank_transaction):
			if (
				candidate_type == "Payment Entry"
				and bank_transaction
				and _is_submitted_internal_transfer(candidate_name)
			):
				same_leg = _same_leg_match_rows(
					candidate_name,
					bank_transaction,
					confirmed_only=True,
					exclude_match=row.get("match_record"),
				)
				if not same_leg:
					opposite = _opposite_confirmed_leg_rows(
						candidate_name,
						bank_transaction,
						exclude_match=row.get("match_record"),
					)
					if len(opposite) == 1:
						# The legacy validator excludes one match by name. Point that
						# exclusion at the proven opposite bank leg so it cannot be
						# mistaken for a same-leg duplicate.
						row = frappe._dict(dict(row))
						row["match_record"] = opposite[0].get("name")
					elif len(opposite) > 1:
						return {
							"valid": False,
							"reason": "Multiple confirmed opposite-leg Internal Transfer matches require manual review.",
							"do_not_substitute": True,
						}
			return original_validate_locked(row)

	def get_first_active_confirmed_conflict(doc):
		legacy_conflict = original_first_confirmed_conflict(doc)
		if not legacy_conflict:
			return None
		payment_entry = cstr(getattr(doc, "payment_entry", None)).strip()
		if not payment_entry or not _is_submitted_internal_transfer(payment_entry):
			return legacy_conflict
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
			return f"Bank Transaction already has confirmed match {other_bank_match}."
		same_leg = _same_leg_match_rows(
			payment_entry,
			doc.bank_transaction,
			confirmed_only=True,
			exclude_match=doc.name,
		)
		if same_leg:
			return f"Internal Transfer bank leg already has confirmed match {same_leg[0].get('name')}."
		opposite = _opposite_confirmed_leg_rows(
			payment_entry,
			doc.bank_transaction,
			exclude_match=doc.name,
		)
		if len(opposite) == 1:
			return None
		return legacy_conflict

	def validate_no_other_active_confirmed_match(doc):
		payment_entry = cstr(getattr(doc, "payment_entry", None)).strip()
		if not payment_entry:
			return original_validate_no_confirmed(doc)
		try:
			return original_validate_no_confirmed(doc)
		except frappe.ValidationError:
			# Preserve the original document-level conflict unless ERPNext live
			# metadata proves this is a submitted Internal Transfer and the only
			# existing confirmed match is the opposite bank leg.
			if getattr(doc, "sales_invoice", None) or not _is_submitted_internal_transfer(payment_entry):
				raise
			same_leg = _same_leg_match_rows(
				payment_entry,
				doc.bank_transaction,
				confirmed_only=True,
				exclude_match=doc.name,
			)
			if same_leg:
				raise
			opposite = _opposite_confirmed_leg_rows(
				payment_entry,
				doc.bank_transaction,
				exclude_match=doc.name,
			)
			if len(opposite) == 1:
				return None
			raise

	workflow._find_active_candidate_review_match = find_active_candidate_review_match
	workflow._classify_suggestion_review_preparation = classify_suggestion_review_preparation
	workflow._validate_locked_candidate_from_selected_row = validate_locked_candidate_from_selected_row
	workflow._get_first_active_confirmed_conflict = get_first_active_confirmed_conflict
	workflow._validate_no_other_active_confirmed_match = validate_no_other_active_confirmed_match

	from retailedge import reconciliation_bridge as bridge

	original_active_conflict_counts = bridge._active_conflict_counts

	def active_conflict_counts(match_doc):
		counts = original_active_conflict_counts(match_doc)
		match_doc = frappe._dict(match_doc or {})
		candidate_type = cstr(match_doc.get("suggested_document_type")).strip()
		candidate_name = cstr(match_doc.get("suggested_document")).strip()
		if candidate_type == "Payment Entry" and _is_submitted_internal_transfer(candidate_name):
			key = f"Payment Entry::{candidate_name}"
			counts.setdefault("by_candidate", {})[key] = len(
				_same_leg_match_rows(
					candidate_name,
					match_doc.get("bank_transaction"),
					confirmed_only=False,
				)
			)
		return counts

	bridge._active_conflict_counts = active_conflict_counts

	from retailedge import reconciliation_handoff as handoff

	original_get_conflict_counts = handoff._get_conflict_counts

	def get_conflict_counts(rows):
		counts = original_get_conflict_counts(rows)
		internal_transfer_leg_counts = {}
		for raw in rows or []:
			row = frappe._dict(raw or {})
			status = cstr(row.get("review_status") or row.get("decision_status")).strip()
			if status in _INACTIVE_MATCH_STATUSES:
				continue
			candidate_type = cstr(row.get("suggested_document_type")).strip()
			candidate_name = cstr(row.get("suggested_document")).strip()
			if candidate_type != "Payment Entry" or not _is_submitted_internal_transfer(candidate_name):
				continue
			leg_key = _payment_entry_leg_key(candidate_name, row.get("bank_transaction"))
			if not leg_key or len(leg_key) == 2:
				continue
			document_key = f"Payment Entry::{candidate_name}"
			per_leg = internal_transfer_leg_counts.setdefault(document_key, {})
			per_leg[leg_key] = per_leg.get(leg_key, 0) + 1
		for document_key, per_leg in internal_transfer_leg_counts.items():
			counts.setdefault("by_candidate", {})[document_key] = max(per_leg.values()) if per_leg else 0
		return counts

	handoff._get_conflict_counts = get_conflict_counts
	setattr(matching, _INSTALL_MARKER, True)
