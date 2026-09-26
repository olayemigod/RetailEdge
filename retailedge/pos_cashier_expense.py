from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt, getdate

from retailedge.cashier_context import get_current_cashier_context
from retailedge.cashier_expense import user_is_reviewer
from retailedge.cashier_expense_posting import get_cashier_expense_posting_settings
from retailedge.utils.settings import get_retailedge_settings

EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
OPENING_DOCTYPE = "POS Opening Shift"
CLOSING_DOCTYPE = "POS Closing Shift"
POS_SOURCE = "POSNext"
POS_CASH_SOURCE = "POS Till"

POS_CLOSING_CUSTOM_FIELDS = {
	CLOSING_DOCTYPE: [
		{
			"fieldname": "retailedge_cashier_expense_section",
			"label": "Cashier Expenses",
			"fieldtype": "Section Break",
			"insert_after": "payment_reconciliation",
			"collapsible": 1,
		},
		{
			"fieldname": "retailedge_cashier_expense_total",
			"label": "Cashier Expenses",
			"fieldtype": "Currency",
			"insert_after": "retailedge_cashier_expense_section",
			"read_only": 1,
		},
		{
			"fieldname": "retailedge_cashier_expense_count",
			"label": "Expense Count",
			"fieldtype": "Int",
			"insert_after": "retailedge_cashier_expense_total",
			"read_only": 1,
		},
		{
			"fieldname": "retailedge_cashier_expense_note",
			"label": "Cashier Expense Note",
			"fieldtype": "Small Text",
			"insert_after": "retailedge_cashier_expense_count",
			"read_only": 1,
		},
	]
}


def ensure_pos_closing_cashier_expense_custom_fields():
	"""Idempotently add closing fields without modifying the POSNext package."""
	if not frappe.db.exists("DocType", CLOSING_DOCTYPE):
		return {}
	meta = frappe.get_meta(CLOSING_DOCTYPE)
	insert_after = (
		"payment_reconciliation"
		if meta.has_field("payment_reconciliation")
		else "pos_opening_shift"
		if meta.has_field("pos_opening_shift")
		else None
	)
	custom_fields = {
		CLOSING_DOCTYPE: [dict(field) for field in POS_CLOSING_CUSTOM_FIELDS[CLOSING_DOCTYPE]]
	}
	if insert_after:
		custom_fields[CLOSING_DOCTYPE][0]["insert_after"] = insert_after
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	return custom_fields


@frappe.whitelist()
def get_pos_cashier_expense_capabilities(
	pos_profile: str | None = None,
	opening_shift: str | None = None,
) -> dict[str, Any]:
	settings = get_retailedge_settings()
	context = get_current_cashier_context(user=frappe.session.user)
	_assert_requested_context_matches(context, pos_profile=pos_profile, opening_shift=opening_shift)

	integration_enabled = bool(
		cint(getattr(settings, "enable_cashier_expense_workflow", 0))
		and cint(getattr(settings, "enable_cashier_expense_pos_integration", 0))
	)
	posting = get_cashier_expense_posting_settings()
	ready = bool(
		integration_enabled
		and context.get("linked_pos_opening_shift")
		and context.get("company")
		and context.get("payment_account")
		and frappe.has_permission(EXPENSE_DOCTYPE, "create")
	)
	return {
		"enabled": integration_enabled,
		"ready": ready,
		"show_action": integration_enabled and bool(cint(getattr(settings, "show_cashier_expense_in_pos", 1))),
		"include_in_closing": integration_enabled
		and bool(cint(getattr(settings, "include_cashier_expenses_in_pos_closing", 1))),
		"posting_mode": posting["posting_mode"],
		"accounting_posting_enabled": posting["enabled"],
		"source": POS_SOURCE,
		"context": {
			"company": context.get("company") or "",
			"branch": context.get("branch") or "",
			"pos_profile": context.get("pos_profile") or "",
			"opening_shift": context.get("linked_pos_opening_shift") or "",
			"cashier": context.get("user") or frappe.session.user,
		},
	}


@frappe.whitelist(methods=["POST"])
def create_pos_cashier_expense(values: dict[str, Any] | str | None = None) -> dict[str, Any]:
	settings = get_retailedge_settings()
	if not cint(getattr(settings, "enable_cashier_expense_workflow", 0)):
		frappe.throw(_("Cashier Expenses are disabled in Settings."))
	if not cint(getattr(settings, "enable_cashier_expense_pos_integration", 0)):
		frappe.throw(_("Cashier Expense in POS is disabled in Settings."))

	values = _coerce_values(values)
	client_request_id = str(values.get("client_request_id") or "").strip()
	if not client_request_id:
		frappe.throw(_("Client Request ID is required for safe POS retry handling."))

	existing = _get_existing_pos_expense(client_request_id)
	if existing:
		return _expense_result(existing, idempotent=True)

	context = get_current_cashier_context(user=frappe.session.user)
	_assert_requested_context_matches(
		context,
		pos_profile=values.get("pos_profile"),
		opening_shift=values.get("opening_shift"),
	)
	if not context.get("linked_pos_opening_shift"):
		frappe.throw(_("Open a POS shift before recording a Cashier Expense."))

	category = str(values.get("expense_category") or "").strip()
	if not category:
		frappe.throw(_("Expense Category is required."))
	_assert_category_access(category)

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))

	doc = frappe.new_doc(EXPENSE_DOCTYPE)
	doc.expense_category = category
	doc.amount = amount
	doc.entry_source = POS_SOURCE
	doc.cash_source = POS_CASH_SOURCE
	doc.cash_movement_status = "Disbursed"
	doc.client_request_id = client_request_id

	if values.get("description"):
		doc.description = str(values.get("description")).strip()
	if values.get("expense_date") and cint(getattr(settings, "allow_cashier_expense_date_edit", 0)):
		doc.expense_date = getdate(values.get("expense_date"))
	if values.get("attachment"):
		doc.attachment = _validate_attachment(values.get("attachment"))

	try:
		doc.insert()
	except frappe.DuplicateEntryError:
		existing = _get_existing_pos_expense(client_request_id)
		if existing:
			return _expense_result(existing, idempotent=True)
		raise

	if not doc.has_permission("submit"):
		frappe.throw(
			_("You do not have permission to submit Cashier Expenses."),
			frappe.PermissionError,
		)
	doc.submit()

	return _expense_result(
		frappe.get_doc(EXPENSE_DOCTYPE, doc.name),
		idempotent=False,
	)


@frappe.whitelist()
def get_pos_closing_cashier_expense_summary(
	opening_shift: str,
	pos_profile: str | None = None,
) -> dict[str, Any]:
	_assert_opening_shift_access(opening_shift, pos_profile=pos_profile)
	return _build_pos_closing_cashier_expense_summary(
		opening_shift,
		pos_profile=pos_profile,
	)


def apply_retailedge_cashier_expenses_to_closing_shift(doc, method=None):
	"""Adjust only the POS cash expected amount, idempotently.

	POSNext remains the closing engine. RetailEdge contributes the physical POS-till
	expense total. The previously-applied total is first restored so repeated
	validation cannot subtract the same expense twice.
	"""
	if getattr(doc, "doctype", None) != CLOSING_DOCTYPE:
		return
	meta = frappe.get_meta(CLOSING_DOCTYPE)
	if not meta.has_field("retailedge_cashier_expense_total"):
		return

	settings = get_retailedge_settings()
	integration_enabled = bool(
		cint(getattr(settings, "enable_cashier_expense_workflow", 0))
		and cint(getattr(settings, "enable_cashier_expense_pos_integration", 0))
		and cint(getattr(settings, "include_cashier_expenses_in_pos_closing", 1))
	)

	opening_shift = str(getattr(doc, "pos_opening_shift", None) or "").strip()
	pos_profile = str(getattr(doc, "pos_profile", None) or "").strip()
	previous_total = flt(getattr(doc, "retailedge_cashier_expense_total", 0))

	summary = {
		"total": 0.0,
		"count": 0,
		"pending_review": 0.0,
		"pending_ledger": 0.0,
		"posted": 0.0,
		"rejected": 0.0,
	}
	if integration_enabled and opening_shift:
		summary = _build_pos_closing_cashier_expense_summary(
			opening_shift,
			pos_profile=pos_profile or None,
		)

	current_total = flt(summary["total"]) if integration_enabled else 0.0
	cash_row = _find_cash_reconciliation_row(doc, pos_profile=pos_profile)
	if not cash_row:
		doc.retailedge_cashier_expense_total = previous_total
		doc.retailedge_cashier_expense_count = cint(summary["count"])
		doc.retailedge_cashier_expense_note = (
			_("Cashier expenses could not be applied because the POS cash reconciliation row was not found.")
			if current_total
			else None
		)
		return

	base_expected = flt(cash_row.get("expected_amount")) + previous_total
	cash_row.expected_amount = base_expected - current_total
	cash_row.difference = flt(cash_row.get("closing_amount")) - flt(cash_row.expected_amount)

	doc.retailedge_cashier_expense_total = current_total
	doc.retailedge_cashier_expense_count = cint(summary["count"])
	if current_total:
		doc.retailedge_cashier_expense_note = _(
			"Expected POS cash includes {0} submitted Cashier Expense(s) totalling {1}. "
			"Accounting/review status does not change the physical till movement."
		).format(cint(summary["count"]), current_total)
	elif previous_total and not integration_enabled:
		doc.retailedge_cashier_expense_note = _(
			"Cashier Expense closing integration is disabled; the previous adjustment was restored."
		)
	else:
		doc.retailedge_cashier_expense_note = None


def _build_pos_closing_cashier_expense_summary(
	opening_shift: str,
	*,
	pos_profile: str | None = None,
) -> dict[str, Any]:
	filters = {
		"linked_pos_opening_shift": opening_shift,
		"docstatus": ["!=", 2],
		"expense_status": ["!=", "Cancelled"],
	}
	if pos_profile:
		filters["pos_profile"] = pos_profile
	rows = frappe.get_all(
		EXPENSE_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"amount",
			"expense_status",
			"cash_source",
			"cash_movement_status",
			"entry_source",
		],
		limit_page_length=0,
	)
	result = {
		"total": 0.0,
		"count": 0,
		"pending_review": 0.0,
		"pending_ledger": 0.0,
		"posted": 0.0,
		"rejected": 0.0,
	}
	for row in rows:
		# Blank values are accepted only for pre-migration submitted history.
		cash_source = str(row.get("cash_source") or POS_CASH_SOURCE).strip()
		movement = str(row.get("cash_movement_status") or "").strip()
		status = str(row.get("expense_status") or "").strip()
		if cash_source != POS_CASH_SOURCE:
			continue
		if movement != "Disbursed" and not (not movement and status not in {"", "Draft"}):
			continue
		amount = flt(row.get("amount"))
		result["total"] += amount
		result["count"] += 1
		if status == "Submitted":
			result["pending_review"] += amount
		elif status == "Pending Ledger":
			result["pending_ledger"] += amount
		elif status == "Posted":
			result["posted"] += amount
		elif status == "Rejected":
			result["rejected"] += amount
	return result


def _find_cash_reconciliation_row(doc, *, pos_profile: str | None):
	cash_mode = "Cash"
	if pos_profile:
		profile_meta = frappe.get_meta("POS Profile")
		if profile_meta.has_field("posa_cash_mode_of_payment"):
			cash_mode = (
				frappe.db.get_value("POS Profile", pos_profile, "posa_cash_mode_of_payment")
				or cash_mode
			)
	for row in getattr(doc, "payment_reconciliation", []) or []:
		if str(row.get("mode_of_payment") or "").strip() == str(cash_mode).strip():
			return row
	return None


def _assert_requested_context_matches(
	context: dict[str, Any],
	*,
	pos_profile: str | None,
	opening_shift: str | None,
) -> None:
	resolved_profile = str(context.get("pos_profile") or "").strip()
	resolved_shift = str(context.get("linked_pos_opening_shift") or "").strip()
	if pos_profile and str(pos_profile).strip() != resolved_profile:
		frappe.throw(
			_("The requested POS Profile does not match your active POS shift."),
			frappe.PermissionError,
		)
	if opening_shift and str(opening_shift).strip() != resolved_shift:
		frappe.throw(
			_("The requested POS Opening Shift does not match your active POS shift."),
			frappe.PermissionError,
		)


def _assert_opening_shift_access(opening_shift: str, *, pos_profile: str | None) -> None:
	opening_shift = str(opening_shift or "").strip()
	if not opening_shift or not frappe.db.exists(OPENING_DOCTYPE, opening_shift):
		frappe.throw(_("POS Opening Shift is required."))
	row = frappe.db.get_value(
		OPENING_DOCTYPE,
		opening_shift,
		["user", "pos_profile"],
		as_dict=True,
	)
	if pos_profile and str(row.pos_profile or "").strip() != str(pos_profile).strip():
		frappe.throw(_("POS Profile does not match the selected POS Opening Shift."))
	if row.user != frappe.session.user and not user_is_reviewer():
		if not frappe.db.exists(
			"POS Profile User",
			{"parent": row.pos_profile, "user": frappe.session.user},
		):
			frappe.throw(
				_("You do not have access to this POS shift."),
				frappe.PermissionError,
			)


def _assert_category_access(category: str) -> None:
	if not frappe.db.exists("RetailEdge Expense Category", category):
		frappe.throw(_("Expense Category {0} does not exist.").format(category))
	if not frappe.has_permission("RetailEdge Expense Category", "read", doc=category):
		frappe.throw(
			_("You do not have permission to use Expense Category {0}.").format(category),
			frappe.PermissionError,
		)
	active = frappe.db.get_value("RetailEdge Expense Category", category, "is_active")
	if not cint(active):
		frappe.throw(_("Expense Category {0} is inactive.").format(category))


def _get_existing_pos_expense(client_request_id: str):
	name = frappe.db.get_value(
		EXPENSE_DOCTYPE,
		{"client_request_id": client_request_id},
		"name",
	)
	if not name:
		return None
	doc = frappe.get_doc(EXPENSE_DOCTYPE, name)
	if getattr(doc, "entry_source", None) != POS_SOURCE:
		frappe.throw(_("Client Request ID is already used by another Cashier Expense."))
	if getattr(doc, "cashier", None) != frappe.session.user and not user_is_reviewer():
		frappe.throw(_("You do not have access to the existing Cashier Expense."), frappe.PermissionError)
	return doc


def _validate_attachment(file_url: Any) -> str:
	file_url = str(file_url or "").strip()
	if not file_url:
		return ""
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("The supplied receipt attachment does not exist."))
	file_doc = frappe.get_doc("File", file_name)
	if not file_doc.has_permission("read"):
		frappe.throw(_("You do not have permission to use the supplied receipt."), frappe.PermissionError)
	return file_url


def _expense_result(doc, *, idempotent: bool) -> dict[str, Any]:
	return {
		"idempotent": idempotent,
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": cint(doc.docstatus),
		"expense_status": getattr(doc, "expense_status", None),
		"ledger_status": getattr(doc, "ledger_status", None),
		"cash_movement_status": getattr(doc, "cash_movement_status", None),
		"posting_mode": getattr(doc, "posting_mode_applied", None),
		"posting_reference_type": getattr(doc, "posting_reference_type", None),
		"posting_reference": getattr(doc, "posting_reference", None),
		"company": getattr(doc, "company", None),
		"branch": getattr(doc, "branch", None),
		"pos_profile": getattr(doc, "pos_profile", None),
		"opening_shift": getattr(doc, "linked_pos_opening_shift", None),
		"amount": flt(getattr(doc, "amount", 0)),
		"user_message": getattr(doc, "user_message", None),
	}


def _coerce_values(values: dict[str, Any] | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return dict(values)
	frappe.throw(_("Invalid Cashier Expense values."))
	return {}
