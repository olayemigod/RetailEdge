from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request
from erpnext.accounts.doctype.sales_invoice.sales_invoice import create_dunning

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_user_allowed_branches,
	has_field,
	user_has_global_branch_access,
	validate_user_branch_access,
)

ACTIVE_PAYMENT_REQUEST_STATUSES = {"Draft", "Requested", "Initiated", "Partially Paid", "Failed"}
ACTIVE_DUNNING_STATUSES = {"Draft", "Unresolved"}


def _invoice_branch_field() -> str | None:
	seen: set[str] = set()
	for candidate in ("retailedge_branch", *BRANCH_FIELD_CANDIDATES):
		if candidate in seen:
			continue
		seen.add(candidate)
		if has_field("Sales Invoice", candidate):
			return candidate
	return None


def _invoice_branch(invoice: Any) -> str:
	fieldname = _invoice_branch_field()
	return str(invoice.get(fieldname) or "") if fieldname else ""


def _assert_invoice_scope(invoice: Any) -> None:
	if not frappe.has_permission("Sales Invoice", "read", doc=invoice.name):
		frappe.throw(_("You do not have permission to read this Sales Invoice."), frappe.PermissionError)
	if invoice.docstatus != 1 or int(invoice.get("is_return") or 0):
		frappe.throw(_("Only submitted customer Sales Invoices can use collection actions."), frappe.ValidationError)
	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("This Sales Invoice has no outstanding amount."), frappe.ValidationError)
	if not frappe.has_permission("Company", "read", doc=invoice.company):
		frappe.throw(_("You do not have permission to read this Company."), frappe.PermissionError)

	branch = _invoice_branch(invoice)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=invoice.company,
			throw=True,
		)
		return

	if user_has_global_branch_access(user=frappe.session.user):
		return
	allowed = list(
		get_user_allowed_branches(user=frappe.session.user, company=invoice.company).get("branches") or []
	)
	if allowed:
		frappe.throw(
			_(
				"This Sales Invoice has no Branch attribution, so a branch-restricted collection action cannot be performed safely."
			),
			frappe.PermissionError,
		)


def _get_locked_invoice(invoice_name: str):
	invoice_name = str(invoice_name or "").strip()
	if not invoice_name:
		frappe.throw(_("Sales Invoice is required."), frappe.ValidationError)
	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(_("Sales Invoice was not found."), frappe.DoesNotExistError)

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	_assert_invoice_scope(invoice)
	frappe.db.sql("select name from `tabSales Invoice` where name=%s for update", (invoice.name,))
	invoice.reload()
	_assert_invoice_scope(invoice)
	return invoice


def _visible_existing_or_block(doctype: str, row: Any | None) -> Any | None:
	"""Return an active native record only when it is readable.

	Existence detection is intentionally permissionless so an inaccessible draft
	cannot be duplicated. Its identifier is never returned or interpolated into an
	error when document-level permission does not allow the current user to read it.
	"""
	if not row:
		return None
	if not frappe.has_permission(doctype, "read", doc=row.name):
		frappe.throw(
			_("An active {0} already exists for this Sales Invoice but is not accessible to you.").format(
				_(doctype)
			),
			frappe.PermissionError,
		)
	return row


def _active_payment_request(invoice_name: str) -> Any | None:
	rows = frappe.get_all(
		"Payment Request",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice_name,
			"docstatus": ["<", 2],
			"status": ["in", sorted(ACTIVE_PAYMENT_REQUEST_STATUSES)],
		},
		fields=["name", "status", "docstatus"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return _visible_existing_or_block("Payment Request", rows[0] if rows else None)


def _active_dunning(invoice_name: str, *, company: str) -> Any | None:
	links = frappe.get_all(
		"Overdue Payment",
		filters={
			"parenttype": "Dunning",
			"parentfield": "overdue_payments",
			"sales_invoice": invoice_name,
		},
		pluck="parent",
		limit_page_length=50,
	)
	if not links:
		return None
	rows = frappe.get_all(
		"Dunning",
		filters={
			"name": ["in", links],
			"company": company,
			"docstatus": ["<", 2],
			"status": ["in", sorted(ACTIVE_DUNNING_STATUSES)],
		},
		fields=["name", "status", "docstatus"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return _visible_existing_or_block("Dunning", rows[0] if rows else None)


def _has_overdue_payment_schedule(invoice: Any) -> bool:
	if not invoice.get("payment_schedule"):
		return bool(invoice.due_date and getdate(invoice.due_date) < getdate(today()))
	return any(
		flt(row.get("outstanding")) > 0 and row.due_date and getdate(row.due_date) < getdate(today())
		for row in invoice.payment_schedule
	)


@frappe.whitelist(methods=["POST"])
def prepare_payment_request(invoice_name: str) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Payment Request"):
		frappe.throw(_("Payment Request is unavailable on this site."), frappe.ValidationError)
	frappe.has_permission("Payment Request", "read", throw=True)
	frappe.has_permission("Payment Request", "create", throw=True)
	invoice = _get_locked_invoice(invoice_name)

	existing = _active_payment_request(invoice.name)
	if existing:
		return {
			"doctype": "Payment Request",
			"name": existing.name,
			"status": existing.status or "",
			"docstatus": int(existing.docstatus or 0),
			"reused": True,
			"submitted": int(existing.docstatus or 0) == 1,
			"route": f"/app/payment-request/{existing.name}",
		}

	payment_request = make_payment_request(
		dt="Sales Invoice",
		dn=invoice.name,
		company=invoice.company,
		party_type="Customer",
		party=invoice.customer,
		party_name=invoice.customer_name,
		mute_email=1,
		submit_doc=0,
		return_doc=1,
	)
	if not payment_request.is_new() and not frappe.has_permission(
		"Payment Request", "read", doc=payment_request.name
	):
		frappe.throw(
			_("An active Payment Request already exists for this Sales Invoice but is not accessible to you."),
			frappe.PermissionError,
		)
	if payment_request.is_new():
		payment_request.insert()
	if payment_request.docstatus != 0:
		frappe.throw(
			_("The collection handoff may only prepare a draft Payment Request."),
			frappe.ValidationError,
		)
	return {
		"doctype": payment_request.doctype,
		"name": payment_request.name,
		"status": payment_request.status or "Draft",
		"docstatus": payment_request.docstatus,
		"reused": False,
		"submitted": False,
		"route": f"/app/payment-request/{payment_request.name}",
	}


@frappe.whitelist(methods=["POST"])
def prepare_dunning(invoice_name: str) -> dict[str, Any]:
	if not frappe.db.exists("DocType", "Dunning"):
		frappe.throw(_("Dunning is unavailable on this site."), frappe.ValidationError)
	frappe.has_permission("Dunning", "read", throw=True)
	frappe.has_permission("Dunning", "create", throw=True)
	invoice = _get_locked_invoice(invoice_name)
	if not _has_overdue_payment_schedule(invoice):
		frappe.throw(
			_("This Sales Invoice has no overdue payment schedule eligible for Dunning."),
			frappe.ValidationError,
		)

	existing = _active_dunning(invoice.name, company=invoice.company)
	if existing:
		return {
			"doctype": "Dunning",
			"name": existing.name,
			"status": existing.status or "",
			"docstatus": int(existing.docstatus or 0),
			"reused": True,
			"submitted": int(existing.docstatus or 0) == 1,
			"route": f"/app/dunning/{existing.name}",
		}

	dunning = create_dunning(invoice.name, ignore_permissions=False)
	if not dunning.get("overdue_payments"):
		frappe.throw(
			_("ERPNext found no overdue payment rows for this Sales Invoice."),
			frappe.ValidationError,
		)
	dunning.insert()
	if dunning.docstatus != 0:
		frappe.throw(
			_("The collection handoff may only prepare a draft Dunning."),
			frappe.ValidationError,
		)
	return {
		"doctype": dunning.doctype,
		"name": dunning.name,
		"status": dunning.status or "Draft",
		"docstatus": dunning.docstatus,
		"reused": False,
		"submitted": False,
		"route": f"/app/dunning/{dunning.name}",
	}
