from __future__ import annotations

from collections import Counter
from pathlib import Path

import frappe
from frappe.utils import cint, cstr, flt, getdate
from frappe.utils.csvutils import read_csv_content
from frappe.utils.file_manager import get_file_path
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

from retailedge.bank_transaction_bridge import (
	build_statement_row_fingerprint,
	normalize_statement_reference,
	normalize_statement_text,
)

LEGACY_DUPLICATE_STATUS_MAP = {
	"Unique": "Not Duplicate",
	"Duplicate Suspected": "Possible Duplicate",
	"Rejected Duplicate": "Exact Duplicate",
}


def normalize_payment_reference(reference=None, narration=None):
	normalized_reference = normalize_statement_reference(reference=reference)
	return {
		"reference": cstr(reference).strip() or None,
		"narration": cstr(narration).strip() or None,
		"normalized_reference": normalized_reference or None,
	}


def prepare_statement_import_row_doc(row, parent=None):
	if parent is None and getattr(row, "parenttype", None) and getattr(row, "parent", None):
		try:
			parent = frappe.get_cached_doc(row.parenttype, row.parent)
		except Exception:
			parent = None

	normalized = normalize_payment_reference(
		reference=getattr(row, "reference", None),
		narration=getattr(row, "narration", None),
	)
	transaction_date = getattr(row, "normalized_date", None) or getattr(row, "transaction_date", None)
	amount = flt(getattr(row, "normalized_amount", None) or getattr(row, "amount", None))
	transaction_direction = cstr(getattr(row, "transaction_direction", None)).strip() or _map_transaction_direction(
		direction=getattr(row, "direction", None),
		credit=getattr(row, "credit", None),
		debit=getattr(row, "debit", None),
	)
	row.normalized_reference = normalized.get("normalized_reference")
	row.normalized_date = transaction_date
	row.normalized_amount = amount
	row.normalized_narration = cstr(getattr(row, "normalized_narration", None) or normalize_statement_text(getattr(row, "narration", None))).strip() or None
	row.normalized_account = cstr(getattr(row, "normalized_account", None) or getattr(row, "account", None)).strip() or None
	row.transaction_direction = transaction_direction
	row.row_fingerprint = build_statement_row_fingerprint(
		company=getattr(parent, "company", None),
		bank_account=getattr(parent, "bank_account", None),
		transaction_date=transaction_date,
		amount=amount,
		reference=getattr(row, "reference", None),
		narration=getattr(row, "narration", None),
		direction=transaction_direction,
	)
	row.evidence_fingerprint = row.row_fingerprint
	row.duplicate_status = _normalize_legacy_duplicate_status(getattr(row, "duplicate_status", None))
	if not getattr(row, "duplicate_status", None):
		row.duplicate_status = "Not Checked"
	if not getattr(row, "import_status", None):
		row.import_status = "Invalid" if getattr(row, "row_error", None) else "Ready"
	if row.import_status == "Duplicate Suspected":
		row.match_status = "Ignored"
	elif not getattr(row, "match_status", None):
		row.match_status = "Pending"


def validate_payment_statement_import(doc):
	statement_type = cstr(getattr(doc, "statement_type", None) or getattr(doc, "payment_category", None)).strip().lower()
	if statement_type == "cash":
		frappe.throw("Cash verification is shift-based in RetailEdge and should not be imported as a statement batch.")
	_refresh_payment_statement_import_summary(doc)


def preview_payment_statement_import_rows(import_name, sample_limit=200):
	doc = frappe.get_doc("RetailEdge Payment Statement Import", import_name)
	template = _get_statement_mapping_template(doc)
	raw_rows = _read_statement_import_attachment(doc)
	preview_rows = []
	errors = []
	counter = Counter()

	for index, raw_row in enumerate(raw_rows, start=1):
		try:
			normalized = normalize_statement_row(raw_row, template, import_doc=doc)
			if not _should_include_statement_row(normalized, doc):
				continue
			import_status = normalized.get("import_status") or "Ready"
			counter[import_status] += 1
			normalized["row_index"] = index
			if not sample_limit or len(preview_rows) < cint(sample_limit):
				preview_rows.append(normalized)
		except Exception as exc:
			errors.append(f"Row {index}: {frappe.safe_decode(str(exc))}")

	total_rows = sum(counter.values())
	ready_count = counter.get("Ready", 0)
	invalid_count = counter.get("Invalid", 0)
	return {
		"statement_import": doc.name,
		"mapping_template": doc.mapping_template,
		"row_count": total_rows,
		"sample_row_count": len(preview_rows),
		"truncated": bool(sample_limit and total_rows > cint(sample_limit)),
		"duplicate_summary": {
			"unique_count": ready_count,
			"duplicate_suspected_count": 0,
			"rejected_duplicate_count": 0,
			"invalid_count": invalid_count,
		},
		"total_rows": total_rows,
		"ready_rows": ready_count,
		"failed_rows": invalid_count,
		"rows": preview_rows,
		"errors": errors,
	}


def import_payment_statement_rows(import_name, replace_rows=True):
	doc = frappe.get_doc("RetailEdge Payment Statement Import", import_name)
	preview = preview_payment_statement_import_rows(import_name, sample_limit=0)
	replace_flag = bool(cint(replace_rows)) if isinstance(replace_rows, str) else bool(replace_rows)
	if replace_flag:
		frappe.db.delete(
			"RetailEdge Statement Import Row",
			{"parent": doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		)
	for row in preview.get("rows") or []:
		child = frappe.get_doc(
			{
				"doctype": "RetailEdge Statement Import Row",
				"parent": doc.name,
				"parenttype": "RetailEdge Payment Statement Import",
				"parentfield": "rows",
				"transaction_date": row.get("transaction_date"),
				"value_date": row.get("value_date"),
				"payment_category": row.get("payment_category"),
				"reference": row.get("reference"),
				"normalized_reference": row.get("normalized_reference"),
				"normalized_date": row.get("normalized_date"),
				"normalized_amount": row.get("normalized_amount"),
				"narration": row.get("narration"),
				"normalized_narration": row.get("normalized_narration"),
				"party": row.get("party"),
				"debit": row.get("debit"),
				"credit": row.get("credit"),
				"amount": row.get("amount"),
				"direction": row.get("direction"),
				"transaction_direction": row.get("transaction_direction"),
				"account": row.get("account"),
				"normalized_account": row.get("normalized_account"),
				"channel": row.get("channel"),
				"branch": row.get("branch"),
				"currency": row.get("currency"),
				"balance": row.get("balance"),
				"mapping_template": doc.mapping_template,
				"evidence_fingerprint": row.get("row_fingerprint"),
				"row_fingerprint": row.get("row_fingerprint"),
				"duplicate_of": row.get("duplicate_of"),
				"duplicate_status": row.get("duplicate_status") or "Not Checked",
				"duplicate_reason": row.get("duplicate_reason"),
				"row_error": row.get("row_error"),
				"import_status": row.get("import_status") or "Ready",
				"match_status": "Pending",
			}
		)
		child.insert(ignore_permissions=True)
	doc.reload()
	_refresh_payment_statement_import_summary(doc)
	values = {
		"import_status": "Imported",
		"imported_row_count": cint(getattr(doc, "imported_row_count", 0)),
		"unique_row_count": cint(getattr(doc, "unique_row_count", 0)),
		"duplicate_suspected_count": cint(getattr(doc, "duplicate_suspected_count", 0)),
		"rejected_duplicate_count": cint(getattr(doc, "rejected_duplicate_count", 0)),
		"total_rows": cint(getattr(doc, "total_rows", 0)),
		"ready_rows": cint(getattr(doc, "ready_rows", 0)),
		"imported_rows": cint(getattr(doc, "imported_rows", 0)),
		"duplicate_rows": cint(getattr(doc, "duplicate_rows", 0)),
		"skipped_rows": cint(getattr(doc, "skipped_rows", 0)),
		"failed_rows": cint(getattr(doc, "failed_rows", 0)),
		"linked_bank_transactions": cint(getattr(doc, "linked_bank_transactions", 0)),
		"import_summary_note": getattr(doc, "import_summary_note", None),
		"import_summary_json": getattr(doc, "import_summary_json", None),
	}
	frappe.db.set_value("RetailEdge Payment Statement Import", doc.name, values, update_modified=False)
	frappe.db.commit()
	return {
		"statement_import": doc.name,
		"imported_row_count": cint(values.get("imported_row_count", 0)),
		"total_rows": cint(values.get("total_rows", 0)),
		"ready_rows": cint(values.get("ready_rows", 0)),
		"imported_rows": cint(values.get("imported_rows", 0)),
		"duplicate_rows": cint(values.get("duplicate_rows", 0)),
		"skipped_rows": cint(values.get("skipped_rows", 0)),
		"failed_rows": cint(values.get("failed_rows", 0)),
		"linked_bank_transactions": cint(values.get("linked_bank_transactions", 0)),
		"errors": preview.get("errors") or [],
	}


def refresh_payment_statement_import_summary(import_name, persist=True):
	doc = frappe.get_doc("RetailEdge Payment Statement Import", import_name)
	_refresh_payment_statement_import_summary(doc)
	if persist:
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	return {
		"statement_import": doc.name,
		"imported_row_count": cint(getattr(doc, "imported_row_count", 0)),
		"unique_row_count": cint(getattr(doc, "unique_row_count", 0)),
		"duplicate_suspected_count": cint(getattr(doc, "duplicate_suspected_count", 0)),
		"rejected_duplicate_count": cint(getattr(doc, "rejected_duplicate_count", 0)),
		"total_rows": cint(getattr(doc, "total_rows", 0)),
		"ready_rows": cint(getattr(doc, "ready_rows", 0)),
		"imported_rows": cint(getattr(doc, "imported_rows", 0)),
		"duplicate_rows": cint(getattr(doc, "duplicate_rows", 0)),
		"skipped_rows": cint(getattr(doc, "skipped_rows", 0)),
		"failed_rows": cint(getattr(doc, "failed_rows", 0)),
		"linked_bank_transactions": cint(getattr(doc, "linked_bank_transactions", 0)),
	}


def normalize_statement_row(raw_row, mapping_template_doc, import_doc=None):
	row = frappe._dict(raw_row or {})
	template = frappe._dict(mapping_template_doc.as_dict() if hasattr(mapping_template_doc, "as_dict") else mapping_template_doc or {})
	date_column = cstr(template.get("date_column")).strip()
	if not date_column:
		raise frappe.ValidationError("Mapping template is missing a date column.")
	if date_column not in row:
		raise frappe.ValidationError(f"Required statement column '{date_column}' was not found in the uploaded row.")

	debit_credit_mode = cstr(template.get("debit_credit_mode")).strip() or "Signed Amount Column"
	transaction_date = row.get(date_column)
	value_date = row.get(template.get("value_date_column")) if template.get("value_date_column") else None
	reference = row.get(template.get("reference_column")) if template.get("reference_column") else None
	narration = row.get(template.get("narration_column")) if template.get("narration_column") else None
	debit = credit = amount = 0.0
	direction = "Unknown"

	if debit_credit_mode == "Separate Debit/Credit Columns":
		if not template.get("debit_column") and not template.get("credit_column"):
			raise frappe.ValidationError("Mapping template is missing debit/credit columns.")
		debit = flt(row.get(template.get("debit_column")))
		credit = flt(row.get(template.get("credit_column")))
		amount = credit if credit > 0 else debit
		direction = "Credit" if credit > 0 else "Debit" if debit > 0 else "Unknown"
	elif debit_credit_mode == "Credit Only Amount Column":
		if not template.get("amount_column"):
			raise frappe.ValidationError("Mapping template is missing amount column.")
		amount = flt(row.get(template.get("amount_column")))
		credit = amount
		direction = "Credit" if amount > 0 else "Unknown"
	else:
		if not template.get("amount_column"):
			raise frappe.ValidationError("Mapping template is missing amount column.")
		signed_amount = flt(row.get(template.get("amount_column")))
		amount = abs(signed_amount)
		if signed_amount > 0:
			credit = signed_amount
			direction = "Credit"
		elif signed_amount < 0:
			debit = abs(signed_amount)
			direction = "Debit"

	normalized = normalize_payment_reference(reference=reference, narration=narration)
	account = row.get(template.get("account_column")) if template.get("account_column") else template.get("default_account")
	transaction_direction = _map_transaction_direction(direction=direction, credit=credit, debit=debit)
	errors = []

	resolved_transaction_date = str(getdate(transaction_date)) if transaction_date else None
	resolved_value_date = str(getdate(value_date)) if value_date else None
	if not resolved_transaction_date:
		errors.append("Transaction date is missing.")
	if flt(amount) <= 0:
		errors.append("Transaction amount must be greater than zero.")
	if transaction_direction == "Unknown":
		errors.append("Transaction direction could not be determined.")
	if import_doc is not None and not getattr(import_doc, "bank_account", None):
		errors.append("Bank Account is missing on the Payment Statement Import.")

	row_fingerprint = build_statement_row_fingerprint(
		company=getattr(import_doc, "company", None) if import_doc else template.get("company"),
		bank_account=getattr(import_doc, "bank_account", None) if import_doc else None,
		transaction_date=transaction_date,
		amount=amount,
		reference=reference,
		narration=narration,
		direction=transaction_direction,
	)
	return {
		"transaction_date": resolved_transaction_date,
		"value_date": resolved_value_date,
		"reference": reference,
		"normalized_reference": normalized.get("normalized_reference"),
		"normalized_date": resolved_transaction_date,
		"narration": narration,
		"normalized_narration": normalize_statement_text(narration) or None,
		"debit": debit,
		"credit": credit,
		"amount": amount,
		"normalized_amount": amount,
		"direction": direction,
		"transaction_direction": transaction_direction,
		"account": account,
		"normalized_account": cstr(account).strip() or None,
		"party": row.get(template.get("party_column")) if template.get("party_column") else None,
		"channel": row.get(template.get("channel_column")) if template.get("channel_column") else None,
		"branch": row.get(template.get("branch_column")) if template.get("branch_column") else None,
		"currency": row.get(template.get("currency_column")) if template.get("currency_column") else None,
		"balance": flt(row.get(template.get("balance_column"))) if template.get("balance_column") else 0.0,
		"payment_category": template.get("payment_category") or getattr(import_doc, "payment_category", None),
		"evidence_fingerprint": row_fingerprint,
		"row_fingerprint": row_fingerprint,
		"duplicate_of": None,
		"duplicate_status": "Not Checked",
		"duplicate_reason": None,
		"row_error": "; ".join(errors) if errors else None,
		"import_status": "Invalid" if errors else "Ready",
	}


def _refresh_payment_statement_import_summary(doc, preview=None):
	if preview is not None:
		duplicate_summary = frappe._dict(preview.get("duplicate_summary") or {})
		doc.imported_row_count = cint(preview.get("row_count") or 0)
		doc.unique_row_count = cint(duplicate_summary.get("unique_count") or 0)
		doc.duplicate_suspected_count = cint(duplicate_summary.get("duplicate_suspected_count") or 0)
		doc.rejected_duplicate_count = cint(duplicate_summary.get("rejected_duplicate_count") or 0)
		doc.total_rows = cint(preview.get("row_count") or 0)
		doc.ready_rows = cint(duplicate_summary.get("unique_count") or 0)
		doc.imported_rows = 0
		doc.duplicate_rows = 0
		doc.skipped_rows = 0
		doc.failed_rows = cint(duplicate_summary.get("invalid_count") or 0)
		doc.linked_bank_transactions = 0
		doc.import_summary_note = (
			f"Rows: {doc.imported_row_count} | "
			f"Ready: {doc.ready_rows} | "
			f"Invalid: {doc.failed_rows} | "
			f"Duplicate Suspected: {doc.duplicate_suspected_count}"
		)
		doc.import_summary_json = frappe.as_json(
			{
				"preview": True,
				"summary": duplicate_summary,
				"errors": preview.get("errors") or [],
			},
			indent=2,
		)
		return

	if not getattr(doc, "name", None):
		doc.imported_row_count = 0
		doc.unique_row_count = 0
		doc.duplicate_suspected_count = 0
		doc.rejected_duplicate_count = 0
		doc.total_rows = 0
		doc.ready_rows = 0
		doc.imported_rows = 0
		doc.duplicate_rows = 0
		doc.skipped_rows = 0
		doc.failed_rows = 0
		doc.linked_bank_transactions = 0
		doc.import_summary_note = None
		doc.import_summary_json = None
		return

	rows = frappe.get_all(
		"RetailEdge Statement Import Row",
		filters={"parent": doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		fields=["duplicate_status", "import_status", "bank_transaction", "existing_bank_transaction"],
		limit_page_length=5000,
	)
	duplicate_counter = Counter((row.get("duplicate_status") or "Not Checked") for row in rows)
	import_counter = Counter((row.get("import_status") or "Pending") for row in rows)
	doc.imported_row_count = len(rows)
	doc.unique_row_count = import_counter.get("Ready", 0)
	doc.duplicate_suspected_count = duplicate_counter.get("Possible Duplicate", 0)
	doc.rejected_duplicate_count = duplicate_counter.get("Exact Duplicate", 0) + duplicate_counter.get("Already Imported", 0)
	doc.total_rows = len(rows)
	doc.ready_rows = import_counter.get("Ready", 0)
	doc.imported_rows = import_counter.get("Imported", 0) + import_counter.get("Already Imported", 0)
	doc.imported_rows += import_counter.get("Manually Accepted", 0)
	doc.duplicate_rows = (
		duplicate_counter.get("Possible Duplicate", 0)
		+ duplicate_counter.get("Exact Duplicate", 0)
		+ duplicate_counter.get("Already Imported", 0)
	)
	doc.skipped_rows = import_counter.get("Skipped", 0)
	doc.failed_rows = import_counter.get("Invalid", 0) + import_counter.get("Failed", 0)
	doc.linked_bank_transactions = sum(1 for row in rows if row.get("bank_transaction") or row.get("existing_bank_transaction"))
	doc.import_summary_note = (
		f"Rows: {doc.total_rows} | "
		f"Ready: {doc.ready_rows} | "
		f"Imported: {doc.imported_rows} | "
		f"Duplicate: {doc.duplicate_rows} | "
		f"Failed: {doc.failed_rows} | "
		f"Linked Bank Transactions: {doc.linked_bank_transactions}"
	)
	doc.import_summary_json = frappe.as_json(
		{
			"import_status": import_counter,
			"duplicate_status": duplicate_counter,
			"linked_bank_transactions": doc.linked_bank_transactions,
		},
		indent=2,
	)


def _get_statement_mapping_template(doc):
	if not getattr(doc, "mapping_template", None):
		frappe.throw("Select a Statement Mapping Template before previewing or importing rows.")
	return frappe.get_doc("RetailEdge Statement Mapping Template", doc.mapping_template)


def _read_statement_import_attachment(doc):
	if not getattr(doc, "attachment", None):
		frappe.throw("Upload a statement attachment before previewing or importing rows.")
	path = Path(get_file_path(doc.attachment))
	if not path.exists():
		frappe.throw("The attached statement file could not be found on disk.")
	content = path.read_bytes()
	suffix = path.suffix.lower()
	if suffix == ".csv":
		rows = read_csv_content(content, False)
	elif suffix == ".xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content)
	else:
		frappe.throw("Only CSV and XLSX statement attachments are supported right now.")
	if not rows:
		return []
	headers = [cstr(value).strip() for value in rows[0]]
	data_rows = []
	for raw in rows[1:]:
		if raw is None:
			continue
		row_values = list(raw)
		if not any(value not in (None, "") for value in row_values):
			continue
		data_rows.append({headers[index]: row_values[index] if index < len(row_values) else None for index in range(len(headers))})
	return data_rows


def _should_include_statement_row(normalized, doc):
	if not normalized:
		return False
	payment_category = cstr(normalized.get("payment_category") or getattr(doc, "payment_category", None)).strip().lower()
	if payment_category == "cash":
		return False
	amount = flt(normalized.get("amount"))
	return amount > 0


def _map_transaction_direction(direction=None, credit=None, debit=None):
	direction_text = cstr(direction).strip().lower()
	if direction_text == "credit" or flt(credit) > 0:
		return "Inflow"
	if direction_text == "debit" or flt(debit) > 0:
		return "Outflow"
	return "Unknown"


def _normalize_legacy_duplicate_status(value):
	status = cstr(value).strip()
	if not status:
		return status
	return LEGACY_DUPLICATE_STATUS_MAP.get(status, status)
