from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.advanced_payments import (
	CUSTOMER_DOCTYPE,
	PAYMENT_ENTRY_DOCTYPE,
	SALES_INVOICE_DOCTYPE,
	_company_currency,
	_invoice_branch,
	_payment_branch_field,
)
from retailedge.branch_context import validate_user_branch_access

PAYMENT_RECONCILIATION_DOCTYPE = "Payment Reconciliation"


def _assert_read(doctype: str, name: str) -> None:
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to read {0} {1}.").format(_(doctype), name), frappe.PermissionError)


def _assert_reconciliation_permission() -> None:
	if not (
		frappe.has_permission(PAYMENT_RECONCILIATION_DOCTYPE, "write")
		or frappe.has_permission(PAYMENT_RECONCILIATION_DOCTYPE, "create")
	):
		frappe.throw(
			_("You do not have permission to reconcile customer payments."),
			frappe.PermissionError,
		)


def _payment_branch(payment: Any) -> str:
	field = _payment_branch_field()
	return str(getattr(payment, field, None) or "") if field else ""


def _find_payment_row(reconciliation: Any, payment_entry: str) -> Any:
	for row in reconciliation.get("payments") or []:
		if row.get("reference_type") == PAYMENT_ENTRY_DOCTYPE and row.get("reference_name") == payment_entry:
			return row
	frappe.throw(_("Payment Entry {0} is no longer available for reconciliation.").format(payment_entry))


def _find_invoice_row(reconciliation: Any, sales_invoice: str) -> Any:
	for row in reconciliation.get("invoices") or []:
		if row.get("invoice_type") == SALES_INVOICE_DOCTYPE and row.get("invoice_number") == sales_invoice:
			return row
	frappe.throw(_("Sales Invoice {0} is no longer outstanding for reconciliation.").format(sales_invoice))


@frappe.whitelist(methods=["POST"])
def apply_customer_advance(
	sales_invoice: str,
	payment_entry: str,
	allocated_amount: float | str,
) -> dict[str, Any]:
	"""Apply a submitted unallocated customer Payment Entry to a Sales Invoice.

	RetailEdge performs eligibility and branch checks, then delegates the actual
	reconciliation to ERPNext's Payment Reconciliation document. No Sales Invoice
	field or GL Entry is written directly by RetailEdge.

	The guided action intentionally supports company-currency receipts only. More
	complex multi-currency or separate-advance-account cases remain on ERPNext's
	full Payment Reconciliation screen.
	"""
	_assert_reconciliation_permission()
	_assert_read(SALES_INVOICE_DOCTYPE, sales_invoice)
	_assert_read(PAYMENT_ENTRY_DOCTYPE, payment_entry)

	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice)
	payment = frappe.get_doc(PAYMENT_ENTRY_DOCTYPE, payment_entry)

	if invoice.docstatus != 1:
		frappe.throw(_("Only submitted Sales Invoices can receive an advance allocation."))
	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("Sales Invoice {0} has no positive outstanding amount.").format(sales_invoice))
	if payment.docstatus != 1:
		frappe.throw(_("Only submitted Payment Entries can be applied as customer advances."))
	if payment.payment_type != "Receive" or payment.party_type != CUSTOMER_DOCTYPE:
		frappe.throw(_("Payment Entry {0} is not a submitted customer receipt.").format(payment_entry))
	if payment.party != invoice.customer or payment.company != invoice.company:
		frappe.throw(_("Payment Entry and Sales Invoice must belong to the same Customer and Company."))
	if flt(payment.unallocated_amount) <= 0:
		frappe.throw(_("Payment Entry {0} has no unapplied amount remaining.").format(payment_entry))

	amount = flt(allocated_amount)
	if amount <= 0:
		frappe.throw(_("Allocated Amount must be greater than zero."))
	if amount > flt(payment.unallocated_amount):
		frappe.throw(_("Allocated Amount cannot exceed the Payment Entry's unapplied amount."))
	if amount > flt(invoice.outstanding_amount):
		frappe.throw(_("Allocated Amount cannot exceed the Sales Invoice outstanding amount."))

	company_currency = _company_currency(invoice.company)
	if invoice.currency != company_currency:
		frappe.throw(
			_("Use the full ERPNext Payment Reconciliation form for multi-currency Sales Invoices.")
		)
	party_currency = str(getattr(payment, "paid_from_account_currency", None) or company_currency)
	if party_currency != company_currency:
		frappe.throw(_("Use the full ERPNext Payment Reconciliation form for multi-currency advances."))
	if getattr(payment, "book_advance_payments_in_separate_party_account", 0):
		frappe.throw(
			_("Use the full ERPNext Payment Reconciliation form when advances use a separate party account.")
		)

	invoice_branch = _invoice_branch(invoice)
	payment_branch = _payment_branch(payment)
	if invoice_branch:
		validate_user_branch_access(
			invoice_branch,
			user=frappe.session.user,
			company=invoice.company,
			throw=True,
		)
	if invoice_branch and payment_branch and invoice_branch != payment_branch:
		frappe.throw(
			_("Payment Entry belongs to Branch {0}, not Branch {1}.").format(payment_branch, invoice_branch)
		)

	receivable_account = str(getattr(invoice, "debit_to", None) or "")
	if not receivable_account:
		frappe.throw(_("Sales Invoice {0} has no receivable account.").format(sales_invoice))
	if str(getattr(payment, "paid_from", None) or "") != receivable_account:
		frappe.throw(
			_("Payment Entry and Sales Invoice use different receivable accounts. Use full Payment Reconciliation.")
		)

	reconciliation = frappe.new_doc(PAYMENT_RECONCILIATION_DOCTYPE)
	reconciliation.company = invoice.company
	reconciliation.party_type = CUSTOMER_DOCTYPE
	reconciliation.party = invoice.customer
	reconciliation.receivable_payable_account = receivable_account
	reconciliation.payment_name = payment_entry
	reconciliation.invoice_name = sales_invoice
	reconciliation.payment_limit = 10
	reconciliation.invoice_limit = 10
	reconciliation.get_unreconciled_entries()

	payment_row = _find_payment_row(reconciliation, payment_entry)
	invoice_row = _find_invoice_row(reconciliation, sales_invoice)
	if amount > flt(payment_row.get("amount")):
		frappe.throw(_("Payment Entry changed while applying the advance. Refresh and try again."))
	if amount > flt(invoice_row.get("outstanding_amount")):
		frappe.throw(_("Sales Invoice outstanding amount changed. Refresh and try again."))

	# Let ERPNext build the allocation row, exchange metadata and reconciliation
	# structure from its current authoritative payment/invoice snapshots. The
	# guided company-currency path may then safely reduce the generated allocation
	# to the user's requested partial amount before ERPNext validates/reconciles it.
	reconciliation.allocate_entries(
		{
			"payments": [frappe._dict(payment_row.as_dict())],
			"invoices": [frappe._dict(invoice_row.as_dict())],
		}
	)
	allocations = reconciliation.get("allocation") or []
	if len(allocations) != 1:
		frappe.throw(_("ERPNext could not build a unique reconciliation allocation for this payment and invoice."))
	allocation = allocations[0]
	allocation.allocated_amount = amount
	allocation.difference_amount = 0

	# PaymentReconciliation.reconcile() performs final allocation validation,
	# updates submitted Payment Entry references through ERPNext's controlled
	# reconciliation path, reposts ledgers as required, and refreshes unreconciled
	# entries. RetailEdge never writes Sales Invoice or GL rows directly.
	reconciliation.reconcile()

	return {
		"sales_invoice": sales_invoice,
		"payment_entry": payment_entry,
		"allocated_amount": amount,
		"invoice_outstanding_amount": flt(
			frappe.db.get_value(SALES_INVOICE_DOCTYPE, sales_invoice, "outstanding_amount")
		),
		"payment_unallocated_amount": flt(
			frappe.db.get_value(PAYMENT_ENTRY_DOCTYPE, payment_entry, "unallocated_amount")
		),
		"source_of_truth": PAYMENT_RECONCILIATION_DOCTYPE,
		"invoice_route": f"/app/sales-invoice/{sales_invoice}",
		"payment_route": f"/app/payment-entry/{payment_entry}",
	}
