from __future__ import annotations

from collections import Counter
from hashlib import sha256

import frappe
from frappe.utils import cint, cstr, flt, getdate, now_datetime

UNRELIABLE_STATEMENT_REFERENCES = {
	"",
	"NA",
	"N/A",
	"NIL",
	"NONE",
	"UNKNOWN",
	"TRANSFER",
	"PAYMENT",
	"POS",
	"BANK",
	"REF",
	"0000",
}


def get_bank_transaction_meta_fields():
	meta = frappe.get_meta("Bank Transaction")
	return {
		field.fieldname: frappe._dict(
			{
				"fieldname": field.fieldname,
				"fieldtype": field.fieldtype,
				"reqd": cint(getattr(field, "reqd", 0)),
				"read_only": cint(getattr(field, "read_only", 0)),
				"options": getattr(field, "options", None),
				"default": getattr(field, "default", None),
			}
		)
		for field in meta.fields
		if getattr(field, "fieldname", None)
	}


def normalize_statement_reference(reference=None, narration=None):
	raw = cstr(reference).strip()
	normalized = "".join(ch for ch in raw.upper() if ch.isalnum())
	return normalized or ""


def normalize_statement_text(value=None):
	raw = cstr(value).strip()
	normalized = "".join(ch for ch in raw.upper() if ch.isalnum())
	return normalized or ""


UNRELIABLE_NORMALIZED_REFERENCES = {normalize_statement_text(value) for value in UNRELIABLE_STATEMENT_REFERENCES}


def is_reliable_statement_reference(reference):
	normalized = normalize_statement_reference(reference=reference)
	if not normalized or len(normalized) < 4:
		return False
	if normalized in UNRELIABLE_NORMALIZED_REFERENCES:
		return False
	if set(normalized) == {"0"}:
		return False
	return True


def build_statement_row_fingerprint(
	company,
	bank_account,
	transaction_date,
	amount,
	reference=None,
	narration=None,
	direction=None,
):
	payload = "|".join(
		[
			cstr(company).strip().upper(),
			cstr(bank_account).strip().upper(),
			cstr(getdate(transaction_date)) if transaction_date else "",
			f"{flt(amount):.2f}",
			normalize_statement_reference(reference=reference),
			cstr(direction).strip().upper(),
		]
	)
	return sha256(payload.encode("utf-8")).hexdigest()


def normalize_statement_row_for_bank_transaction(row_doc, import_doc=None):
	if import_doc is None and getattr(row_doc, "parent", None):
		import_doc = frappe.get_cached_doc("RetailEdge Payment Statement Import", row_doc.parent)

	transaction_date = getattr(row_doc, "normalized_date", None) or getattr(row_doc, "transaction_date", None) or getattr(row_doc, "value_date", None)
	normalized_amount = flt(
		getattr(row_doc, "normalized_amount", None)
		or getattr(row_doc, "amount", None)
		or getattr(row_doc, "credit", None)
		or getattr(row_doc, "debit", None)
	)
	reference = cstr(getattr(row_doc, "reference", None)).strip()
	description = cstr(getattr(row_doc, "narration", None)).strip() or reference
	normalized_reference = cstr(getattr(row_doc, "normalized_reference", None)).strip() or normalize_statement_reference(reference=reference)
	normalized_narration = cstr(getattr(row_doc, "normalized_narration", None)).strip() or normalize_statement_text(description)
	normalized_account = cstr(getattr(row_doc, "normalized_account", None)).strip() or cstr(getattr(row_doc, "account", None)).strip()
	direction = cstr(getattr(row_doc, "transaction_direction", None)).strip()
	if not direction:
		direction = _map_direction(row_doc)
	deposit = normalized_amount if direction == "Inflow" else 0.0
	withdrawal = normalized_amount if direction == "Outflow" else 0.0
	currency = cstr(getattr(row_doc, "currency", None)).strip() or cstr(getattr(import_doc, "currency", None)).strip()
	if not currency and getattr(import_doc, "bank_account", None):
		currency = cstr(frappe.db.get_value("Bank Account", import_doc.bank_account, "account_currency") or "").strip()

	errors = []
	if not getattr(import_doc, "company", None):
		errors.append("Company is required on the Payment Statement Import.")
	if not getattr(import_doc, "bank_account", None):
		errors.append("Bank Account is required on the Payment Statement Import.")
	if not transaction_date:
		errors.append("Transaction date is missing.")
	if normalized_amount <= 0:
		errors.append("Transaction amount must be greater than zero.")
	if direction == "Unknown":
		errors.append("Transaction direction could not be determined.")

	row_fingerprint = build_statement_row_fingerprint(
		company=getattr(import_doc, "company", None),
		bank_account=getattr(import_doc, "bank_account", None),
		transaction_date=transaction_date,
		amount=normalized_amount,
		reference=reference or normalized_reference,
		narration=description,
		direction=direction,
	)

	return {
		"company": getattr(import_doc, "company", None),
		"bank_account": getattr(import_doc, "bank_account", None),
		"transaction_date": cstr(getdate(transaction_date)) if transaction_date else None,
		"amount": normalized_amount,
		"direction": direction,
		"deposit": deposit,
		"withdrawal": withdrawal,
		"reference_number": reference,
		"normalized_reference": normalized_reference,
		"description": description,
		"currency": currency or None,
		"party_type": cstr(getattr(row_doc, "party_type", None)).strip() or None,
		"party": cstr(getattr(row_doc, "party", None)).strip() or None,
		"row_fingerprint": row_fingerprint,
		"normalized_narration": normalized_narration or None,
		"normalized_account": normalized_account or None,
		"errors": errors,
	}


def find_existing_statement_row_duplicate(row_doc, normalized=None):
	normalized = normalized or normalize_statement_row_for_bank_transaction(row_doc)
	if not normalized.get("row_fingerprint"):
		return _duplicate_result()

	current_reference = normalized.get("normalized_reference")
	current_reference_reliable = is_reliable_statement_reference(current_reference)

	if current_reference_reliable:
		exact_rows = frappe.get_all(
			"RetailEdge Statement Import Row",
			filters={"row_fingerprint": normalized.get("row_fingerprint")},
			fields=["name", "parent", "bank_transaction", "existing_bank_transaction", "import_status"],
			limit_page_length=20,
		)
		for candidate in exact_rows:
			if candidate.name == getattr(row_doc, "name", None):
				continue
			bank_transaction = candidate.bank_transaction or candidate.existing_bank_transaction
			duplicate_type = "Already Imported" if bank_transaction or candidate.import_status in ("Imported", "Already Imported", "Manually Accepted") else "Exact Duplicate"
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type=duplicate_type,
				statement_row=candidate.name,
				bank_transaction=bank_transaction,
				reason=f"Exact duplicate: the same date, amount, reference, account, and direction already exist on {candidate.name}.",
			)

	candidate_map = {}
	if normalized.get("transaction_date") and normalized.get("amount"):
		for candidate in frappe.get_all(
			"RetailEdge Statement Import Row",
			filters={
				"normalized_date": normalized.get("transaction_date"),
				"normalized_amount": normalized.get("amount"),
				"transaction_direction": normalized.get("direction"),
			},
			fields=["name", "parent", "reference", "normalized_reference", "bank_transaction", "existing_bank_transaction"],
			limit_page_length=20,
		):
			candidate_map[candidate.name] = candidate

	if normalized.get("normalized_reference"):
		for candidate in frappe.get_all(
			"RetailEdge Statement Import Row",
			filters={"normalized_reference": normalized.get("normalized_reference")},
			fields=["name", "parent", "normalized_date", "normalized_amount", "transaction_direction", "bank_transaction", "existing_bank_transaction"],
			limit_page_length=20,
		):
			candidate_map[candidate.name] = candidate

	for candidate in candidate_map.values():
		if candidate.name == getattr(row_doc, "name", None):
			continue
		if not _statement_row_candidate_matches_context(candidate, normalized):
			continue

		candidate_reference = normalize_statement_reference(reference=getattr(candidate, "normalized_reference", None) or getattr(candidate, "reference", None))
		candidate_reference_reliable = is_reliable_statement_reference(candidate_reference)
		same_reference = bool(current_reference and candidate_reference and current_reference == candidate_reference)
		same_date_amount = (
			cstr(getattr(candidate, "normalized_date", None) or normalized.get("transaction_date")) == cstr(normalized.get("transaction_date"))
			and flt(getattr(candidate, "normalized_amount", None) or normalized.get("amount")) == flt(normalized.get("amount"))
		)
		same_direction = _same_direction(getattr(candidate, "transaction_direction", None), normalized.get("direction"))
		candidate_narration = normalize_statement_text(getattr(candidate, "normalized_narration", None) or getattr(candidate, "narration", None))

		if current_reference_reliable and candidate_reference_reliable and current_reference != candidate_reference and same_date_amount and same_direction:
			continue
		if same_reference and not same_date_amount:
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type="Possible Duplicate",
				statement_row=candidate.name,
				bank_transaction=candidate.bank_transaction or candidate.existing_bank_transaction,
				reason="Possible duplicate: the same reliable reference appears on another row with a different date or amount.",
			)
		if same_date_amount and same_direction and (not current_reference_reliable or not candidate_reference_reliable):
			reason = "Possible duplicate: same date and amount with missing or weak reference."
			if normalized.get("normalized_narration") and candidate_narration and candidate_narration == normalized.get("normalized_narration"):
				reason = "Possible duplicate: similar narration found, but reference is not reliable."
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type="Possible Duplicate",
				statement_row=candidate.name,
				bank_transaction=candidate.bank_transaction or candidate.existing_bank_transaction,
				reason=reason,
			)
		if same_reference and current_reference_reliable and candidate_reference_reliable:
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type="Possible Duplicate",
				statement_row=candidate.name,
				bank_transaction=candidate.bank_transaction or candidate.existing_bank_transaction,
				reason="Possible duplicate: the same reliable reference appears more than once and needs review.",
			)

	return _duplicate_result()


def find_existing_bank_transaction_duplicate(normalized):
	meta_fields = get_bank_transaction_meta_fields()
	filters = {}
	if "bank_account" in meta_fields and normalized.get("bank_account"):
		filters["bank_account"] = normalized.get("bank_account")
	if "date" in meta_fields and normalized.get("transaction_date"):
		filters["date"] = normalized.get("transaction_date")
	amount_field = "deposit" if normalized.get("direction") == "Inflow" else "withdrawal"
	if amount_field in meta_fields:
		filters[amount_field] = normalized.get("amount")
	if not filters:
		return _duplicate_result()

	candidates = frappe.get_all(
		"Bank Transaction",
		filters=filters,
		fields=[
			"name",
			"bank_account",
			"date",
			"deposit",
			"withdrawal",
			"description",
			"reference_number",
			"status",
		],
		limit_page_length=20,
	)
	normalized_reference = normalized.get("normalized_reference")
	normalized_reference_reliable = is_reliable_statement_reference(normalized_reference)
	normalized_description = normalize_statement_text(normalized.get("description"))

	for candidate in candidates:
		candidate_reference = normalize_statement_reference(reference=candidate.reference_number)
		candidate_reference_reliable = is_reliable_statement_reference(candidate_reference)
		candidate_description = normalize_statement_text(candidate.description)
		if normalized_reference_reliable and candidate_reference_reliable and candidate_reference == normalized_reference:
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type="Already Imported",
				bank_transaction=candidate.name,
				reason=f"Exact duplicate: Bank Transaction {candidate.name} already has the same date, amount, reference, account, and direction.",
			)
		if normalized_reference_reliable and candidate_reference_reliable and candidate_reference != normalized_reference:
			continue
		if normalized_description and candidate_description and candidate_description == normalized_description:
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type="Possible Duplicate",
				bank_transaction=candidate.name,
				reason="Possible duplicate: similar narration found, but reference is not reliable.",
			)
		if not normalized_reference_reliable or not candidate_reference_reliable:
			return _duplicate_result(
				is_duplicate=True,
				duplicate_type="Possible Duplicate",
				bank_transaction=candidate.name,
				reason="Possible duplicate: same date and amount with missing or weak reference.",
			)

	if normalized_reference_reliable and "reference_number" in meta_fields:
		reference_candidates = frappe.get_all(
			"Bank Transaction",
			filters={
				"reference_number": ["like", f"%{normalized.get('reference_number') or normalized_reference}%"],
				**({"bank_account": normalized.get("bank_account")} if normalized.get("bank_account") and "bank_account" in meta_fields else {}),
			},
			fields=["name", "reference_number", "description", "date", "deposit", "withdrawal", "bank_account"],
			limit_page_length=20,
		)
		for candidate in reference_candidates:
			candidate_reference = normalize_statement_reference(reference=candidate.reference_number)
			if _bank_transaction_direction(candidate) != cstr(normalized.get("direction")).strip():
				continue
			if candidate_reference == normalized_reference:
				return _duplicate_result(
					is_duplicate=True,
					duplicate_type="Possible Duplicate",
					bank_transaction=candidate.name,
					reason="Possible duplicate: the same reliable reference appears on another Bank Transaction with a different date or amount.",
				)

	return _duplicate_result()


def create_or_link_bank_transaction_from_statement_row(row_name, force=False, dry_run=True):
	row_doc = frappe.get_doc("RetailEdge Statement Import Row", row_name)
	import_doc = frappe.get_doc("RetailEdge Payment Statement Import", row_doc.parent)
	normalized = normalize_statement_row_for_bank_transaction(row_doc, import_doc=import_doc)
	errors = list(normalized.get("errors") or [])
	statement_duplicate = find_existing_statement_row_duplicate(row_doc, normalized=normalized)
	bank_duplicate = find_existing_bank_transaction_duplicate(normalized)

	status = "Would Import" if dry_run else "Imported"
	reason = ""
	bank_transaction_name = None

	if errors:
		status = "Invalid"
		reason = "; ".join(errors)
	elif statement_duplicate.get("is_duplicate"):
		status = statement_duplicate.get("duplicate_type") or "Duplicate Suspected"
		reason = statement_duplicate.get("reason") or ""
		bank_transaction_name = statement_duplicate.get("bank_transaction")
	elif bank_duplicate.get("is_duplicate"):
		status = bank_duplicate.get("duplicate_type") or "Duplicate Suspected"
		reason = bank_duplicate.get("reason") or ""
		bank_transaction_name = bank_duplicate.get("bank_transaction")

	if status == "Possible Duplicate" and not force:
		status = "Duplicate Suspected"
	if force and status == "Possible Duplicate":
		status = "Would Import" if dry_run else "Imported"
		reason = "Operator accepted a possible duplicate for manual import."
		bank_transaction_name = None
	if status in {"Exact Duplicate", "Already Imported"} and not bank_transaction_name:
		bank_transaction_name = statement_duplicate.get("bank_transaction") or bank_duplicate.get("bank_transaction")

	if dry_run:
		return _result_payload(
			row_doc=row_doc,
			dry_run=True,
			status=status if status != "Failed" else "Failed",
			bank_transaction=bank_transaction_name,
			normalized=normalized,
			reason=reason or "Preview only. No Bank Transaction was created or linked.",
			errors=errors,
		)

	if status == "Invalid":
		_update_statement_row_bridge_fields(
			row_doc,
			normalized=normalized,
			import_status="Invalid",
			duplicate_status="Not Checked",
			duplicate_of=None,
			existing_bank_transaction=None,
			bank_transaction=None,
			row_error=reason,
		)
		return _result_payload(
			row_doc=row_doc,
			dry_run=False,
			status="Invalid",
			bank_transaction=None,
			normalized=normalized,
			reason=reason,
			errors=errors,
		)

	if status == "Already Imported":
		_update_statement_row_bridge_fields(
			row_doc,
			normalized=normalized,
			import_status="Already Imported",
			duplicate_status="Already Imported",
			duplicate_of=statement_duplicate.get("statement_row"),
			existing_bank_transaction=bank_transaction_name,
			bank_transaction=bank_transaction_name,
			row_error=None,
		)
		return _result_payload(
			row_doc=row_doc,
			dry_run=False,
			status="Already Imported",
			bank_transaction=bank_transaction_name,
			normalized=normalized,
			reason=reason,
			errors=errors,
		)

	if status in {"Duplicate Suspected", "Exact Duplicate"} and not force:
		if not dry_run:
			_update_statement_row_bridge_fields(
				row_doc,
				normalized=normalized,
				import_status="Skipped",
				duplicate_status="Possible Duplicate" if status == "Duplicate Suspected" else "Exact Duplicate",
				duplicate_of=statement_duplicate.get("statement_row"),
				existing_bank_transaction=bank_transaction_name,
				row_error=reason,
			)
		return _result_payload(
			row_doc=row_doc,
			dry_run=False,
			status=status,
			bank_transaction=bank_transaction_name,
			normalized=normalized,
			reason=reason,
			errors=errors,
		)

	if dry_run:
		return _result_payload(
			row_doc=row_doc,
			dry_run=True,
			status="Would Import",
			bank_transaction=bank_transaction_name,
			normalized=normalized,
			reason=reason or "Bank Transaction would be created or linked.",
			errors=errors,
		)

	if bank_transaction_name:
		_update_statement_row_bridge_fields(
			row_doc,
			normalized=normalized,
			import_status="Already Imported" if status == "Already Imported" else "Imported",
			duplicate_status="Already Imported" if status == "Already Imported" else "Not Duplicate",
			duplicate_of=statement_duplicate.get("statement_row"),
			existing_bank_transaction=bank_transaction_name,
			bank_transaction=bank_transaction_name,
			row_error=None,
		)
		return _result_payload(
			row_doc=row_doc,
			dry_run=False,
			status="Already Imported" if status == "Already Imported" else "Imported",
			bank_transaction=bank_transaction_name,
			normalized=normalized,
			reason=reason or "Linked to an existing Bank Transaction.",
			errors=errors,
		)

	bank_transaction_name = _create_bank_transaction(normalized)
	_update_statement_row_bridge_fields(
		row_doc,
		normalized=normalized,
		import_status="Imported",
		duplicate_status="Not Duplicate",
		duplicate_of=None,
		existing_bank_transaction=None,
		bank_transaction=bank_transaction_name,
		row_error=None,
	)
	return _result_payload(
		row_doc=row_doc,
		dry_run=False,
		status="Imported",
		bank_transaction=bank_transaction_name,
		normalized=normalized,
		reason="Created a new ERPNext Bank Transaction.",
		errors=errors,
	)


def preview_bank_transaction_import(statement_import_name):
	import_doc = frappe.get_doc("RetailEdge Payment Statement Import", statement_import_name)
	rows = frappe.get_all(
		"RetailEdge Statement Import Row",
		filters={"parent": import_doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		fields=["name"],
		order_by="idx asc",
		limit_page_length=5000,
	)
	results = [create_or_link_bank_transaction_from_statement_row(row.name, dry_run=True) for row in rows]
	return _summarize_bridge_results(import_doc.name, results)


def import_statement_rows_to_bank_transactions(statement_import_name, force=False):
	import_doc = frappe.get_doc("RetailEdge Payment Statement Import", statement_import_name)
	eligible_statuses = ["Pending", "Ready", "Failed", "Invalid"]
	if force:
		eligible_statuses.extend(["Skipped"])
	rows = frappe.get_all(
		"RetailEdge Statement Import Row",
		filters={
			"parent": import_doc.name,
			"parenttype": "RetailEdge Payment Statement Import",
			"import_status": ["in", eligible_statuses],
		},
		fields=["name"],
		order_by="idx asc",
		limit_page_length=5000,
	)
	results = [create_or_link_bank_transaction_from_statement_row(row.name, force=force, dry_run=False) for row in rows]
	_refresh_statement_import_bridge_summary(import_doc)
	frappe.db.commit()
	return _summarize_bridge_results(import_doc.name, results)


def accept_possible_duplicate_statement_row(row_name, acceptance_note=None):
	row_doc = frappe.get_doc("RetailEdge Statement Import Row", row_name)
	if not _row_is_possible_duplicate(row_doc):
		frappe.throw("Only rows marked as Possible Duplicate or skipped duplicate rows can be manually accepted.")

	normalized = normalize_statement_row_for_bank_transaction(row_doc)
	if normalized.get("errors"):
		frappe.throw("; ".join(normalized.get("errors")))

	statement_duplicate = find_existing_statement_row_duplicate(row_doc, normalized=normalized)
	bank_duplicate = find_existing_bank_transaction_duplicate(normalized)
	for duplicate in (statement_duplicate, bank_duplicate):
		if duplicate.get("duplicate_type") in {"Exact Duplicate", "Already Imported"}:
			frappe.throw(duplicate.get("reason") or "An exact duplicate still exists. This row cannot be manually accepted.")

	result = create_or_link_bank_transaction_from_statement_row(row_name, force=True, dry_run=False)
	if result.get("status") not in {"Imported", "Already Imported"}:
		frappe.throw(result.get("reason") or "The possible duplicate could not be accepted.")

	values = {
		"manually_accepted": 1,
		"accepted_by": frappe.session.user,
		"accepted_on": now_datetime(),
		"acceptance_note": cstr(acceptance_note).strip() or None,
		"duplicate_status": "Accepted Possible Duplicate",
		"import_status": "Manually Accepted",
	}
	frappe.db.set_value("RetailEdge Statement Import Row", row_doc.name, values, update_modified=False)
	_refresh_statement_import_bridge_summary(frappe.get_doc("RetailEdge Payment Statement Import", row_doc.parent))
	frappe.db.commit()
	result["status"] = "Manually Accepted"
	result["reason"] = "Possible duplicate accepted manually and imported as a separate Bank Transaction."
	result["acceptance_note"] = values["acceptance_note"]
	return result


def get_possible_duplicate_statement_rows(statement_import_name):
	import_doc = frappe.get_doc("RetailEdge Payment Statement Import", statement_import_name)
	rows = frappe.get_all(
		"RetailEdge Statement Import Row",
		filters={"parent": import_doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		fields=[
			"name",
			"transaction_date",
			"reference",
			"narration",
			"amount",
			"transaction_direction",
			"direction",
			"duplicate_status",
			"import_status",
			"row_error",
			"duplicate_reason",
			"existing_bank_transaction",
			"bank_transaction",
		],
		order_by="idx asc",
		limit_page_length=5000,
	)
	result = []
	for row in rows:
		duplicate_status = cstr(getattr(row, "duplicate_status", None)).strip()
		if duplicate_status in {"Exact Duplicate", "Already Imported"}:
			continue
		if not _row_is_possible_duplicate(row):
			continue
		result.append(
			{
				"name": row.name,
				"transaction_date": row.transaction_date,
				"bank_account": getattr(import_doc, "bank_account", None),
				"reference": cstr(row.reference).strip() or None,
				"narration": cstr(row.narration).strip() or None,
				"amount": flt(row.amount),
				"direction": cstr(row.transaction_direction).strip() or cstr(row.direction).strip() or "Unknown",
				"duplicate_status": cstr(row.duplicate_status).strip() or "Not Checked",
				"import_status": cstr(row.import_status).strip() or "Pending",
				"reason": cstr(row.row_error).strip() or cstr(getattr(row, "duplicate_reason", None)).strip() or None,
				"existing_bank_transaction": cstr(row.bank_transaction).strip() or cstr(row.existing_bank_transaction).strip() or None,
			}
		)
	return result


def _map_direction(row_doc):
	transaction_direction = cstr(getattr(row_doc, "direction", None)).strip().lower()
	if transaction_direction == "credit" or flt(getattr(row_doc, "credit", None)) > 0:
		return "Inflow"
	if transaction_direction == "debit" or flt(getattr(row_doc, "debit", None)) > 0:
		return "Outflow"
	return "Unknown"


def _create_bank_transaction(normalized):
	meta_fields = get_bank_transaction_meta_fields()
	doc = frappe.new_doc("Bank Transaction")
	_set_if_available(doc, meta_fields, "bank_account", normalized.get("bank_account"))
	if "date" in meta_fields:
		_set_if_available(doc, meta_fields, "date", normalized.get("transaction_date"))
	_set_if_available(doc, meta_fields, "deposit", normalized.get("deposit"))
	_set_if_available(doc, meta_fields, "withdrawal", normalized.get("withdrawal"))
	_set_if_available(doc, meta_fields, "currency", normalized.get("currency"))
	_set_if_available(doc, meta_fields, "description", normalized.get("description"))
	_set_if_available(doc, meta_fields, "reference_number", normalized.get("reference_number"))
	if normalized.get("party_type") and normalized.get("party"):
		_set_if_available(doc, meta_fields, "party_type", normalized.get("party_type"))
		_set_if_available(doc, meta_fields, "party", normalized.get("party"))
	doc.insert(ignore_permissions=True)
	return doc.name


def _refresh_statement_import_bridge_summary(import_doc):
	rows = frappe.get_all(
		"RetailEdge Statement Import Row",
		filters={"parent": import_doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		fields=["name", "import_status", "duplicate_status", "bank_transaction", "existing_bank_transaction"],
		limit_page_length=5000,
	)
	import_status_counter = Counter((row.import_status or "Pending") for row in rows)
	duplicate_counter = Counter((row.duplicate_status or "Not Checked") for row in rows)
	linked_bank_transactions = sum(1 for row in rows if row.bank_transaction or row.existing_bank_transaction)
	values = {
		"total_rows": len(rows),
		"ready_rows": import_status_counter.get("Ready", 0),
		"imported_rows": import_status_counter.get("Imported", 0)
		+ import_status_counter.get("Already Imported", 0)
		+ import_status_counter.get("Manually Accepted", 0),
		"duplicate_rows": duplicate_counter.get("Exact Duplicate", 0)
		+ duplicate_counter.get("Possible Duplicate", 0)
		+ duplicate_counter.get("Already Imported", 0),
		"skipped_rows": import_status_counter.get("Skipped", 0),
		"failed_rows": import_status_counter.get("Failed", 0) + import_status_counter.get("Invalid", 0),
		"linked_bank_transactions": linked_bank_transactions,
		"last_import_run_on": now_datetime(),
		"last_import_run_by": frappe.session.user,
		"import_summary_note": (
			f"Rows: {len(rows)} | "
			f"Imported or Linked: {import_status_counter.get('Imported', 0) + import_status_counter.get('Already Imported', 0) + import_status_counter.get('Manually Accepted', 0)} | "
			f"Possible Duplicate: {duplicate_counter.get('Possible Duplicate', 0)} | "
			f"Exact Duplicate: {duplicate_counter.get('Exact Duplicate', 0)} | "
			f"Failed: {import_status_counter.get('Failed', 0) + import_status_counter.get('Invalid', 0)} | "
			f"Linked Bank Transactions: {linked_bank_transactions}"
		),
		"import_summary_json": frappe.as_json(
			{
				"import_status": import_status_counter,
				"duplicate_status": duplicate_counter,
				"linked_bank_transactions": linked_bank_transactions,
			},
			indent=2,
		),
	}
	frappe.db.set_value("RetailEdge Payment Statement Import", import_doc.name, values, update_modified=False)


def _result_payload(row_doc, dry_run, status, bank_transaction, normalized, reason, errors):
	return {
		"statement_row": row_doc.name,
		"dry_run": bool(dry_run),
		"status": status,
		"bank_transaction": bank_transaction,
		"amount": flt(normalized.get("amount")),
		"direction": normalized.get("direction"),
		"reference": normalized.get("reference_number"),
		"reason": reason,
		"errors": list(errors or []),
	}


def _summarize_bridge_results(statement_import_name, results):
	counter = Counter(result.get("status") or "Failed" for result in results)
	imported_rows = counter.get("Imported", 0) + counter.get("Manually Accepted", 0)
	possible_duplicates = counter.get("Duplicate Suspected", 0)
	exact_duplicates = counter.get("Exact Duplicate", 0) + counter.get("Already Imported", 0)
	duplicate_rows = possible_duplicates + exact_duplicates
	skipped_rows = counter.get("Skipped", 0)
	failed_rows = counter.get("Invalid", 0) + counter.get("Failed", 0)
	linked_bank_transactions = sum(1 for result in results if result.get("bank_transaction"))
	return {
		"statement_import": statement_import_name,
		"total_rows": len(results),
		"would_import": counter.get("Would Import", 0),
		"already_imported": counter.get("Already Imported", 0),
		"duplicate_suspected": duplicate_rows,
		"invalid": counter.get("Invalid", 0),
		"failed": counter.get("Failed", 0),
		"imported": counter.get("Imported", 0),
		"imported_rows": imported_rows,
		"possible_duplicates": possible_duplicates,
		"exact_duplicates": exact_duplicates,
		"duplicate_rows": duplicate_rows,
		"skipped_rows": skipped_rows,
		"failed_rows": failed_rows,
		"linked_bank_transactions": linked_bank_transactions,
		"rows": results,
	}


def _set_if_available(doc, meta_fields, fieldname, value):
	if fieldname not in meta_fields:
		return
	if value in (None, ""):
		return
	doc.set(fieldname, value)


def _update_statement_row_bridge_fields(
	row_doc,
	normalized,
	import_status,
	duplicate_status,
	duplicate_of=None,
	existing_bank_transaction=None,
	bank_transaction=None,
	row_error=None,
):
	values = {
		"normalized_reference": normalized.get("normalized_reference") or None,
		"normalized_date": normalized.get("transaction_date") or None,
		"normalized_amount": flt(normalized.get("amount")),
		"normalized_narration": normalized.get("normalized_narration") or None,
		"normalized_account": normalized.get("normalized_account") or None,
		"transaction_direction": normalized.get("direction") or "Unknown",
		"row_fingerprint": normalized.get("row_fingerprint") or None,
		"evidence_fingerprint": normalized.get("row_fingerprint") or None,
		"import_status": import_status,
		"duplicate_status": duplicate_status,
		"duplicate_of": duplicate_of or None,
		"existing_bank_transaction": existing_bank_transaction or None,
		"bank_transaction": bank_transaction or None,
		"row_error": row_error or None,
	}
	frappe.db.set_value("RetailEdge Statement Import Row", row_doc.name, values, update_modified=False)


def _duplicate_result(is_duplicate=False, duplicate_type=None, statement_row=None, bank_transaction=None, reason=None):
	return {
		"is_duplicate": bool(is_duplicate),
		"duplicate_type": duplicate_type,
		"statement_row": statement_row,
		"bank_transaction": bank_transaction,
		"reason": reason,
	}


def _row_is_possible_duplicate(row_doc):
	duplicate_status = cstr(getattr(row_doc, "duplicate_status", None)).strip()
	import_status = cstr(getattr(row_doc, "import_status", None)).strip()
	return duplicate_status == "Possible Duplicate" or import_status in {"Duplicate Suspected", "Skipped"}


def _same_direction(candidate_direction, normalized_direction):
	candidate_value = cstr(candidate_direction).strip()
	normalized_value = cstr(normalized_direction).strip()
	if not candidate_value or candidate_value == "Unknown" or not normalized_value or normalized_value == "Unknown":
		return True
	return candidate_value == normalized_value


def _bank_transaction_direction(candidate):
	if flt(getattr(candidate, "deposit", None)) > 0:
		return "Inflow"
	if flt(getattr(candidate, "withdrawal", None)) > 0:
		return "Outflow"
	return "Unknown"


def _statement_row_candidate_matches_context(candidate, normalized):
	parent_name = getattr(candidate, "parent", None)
	if not parent_name:
		return False
	parent = frappe.get_cached_doc("RetailEdge Payment Statement Import", parent_name)
	if cstr(getattr(parent, "company", None)).strip() != cstr(normalized.get("company")).strip():
		return False
	if cstr(getattr(parent, "bank_account", None)).strip() != cstr(normalized.get("bank_account")).strip():
		return False
	return True
