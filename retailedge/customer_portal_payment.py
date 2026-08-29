from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
from erpnext.accounts.doctype.bank_account.bank_account import get_party_bank_account
from erpnext.accounts.doctype.payment_request.payment_request import (
	get_amount,
	get_gateway_details,
)
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency
from erpnext.controllers.website_list_for_contact import has_website_permission

from retailedge.customer_portal import _assert_customer_portal_user

REUSABLE_PAYMENT_REQUEST_STATUSES = {
	"Requested",
	"Initiated",
	"Partially Paid",
	"Failed",
}


def _assert_payable_invoice(invoice, customers: list[str]) -> None:
	if invoice.doctype != "Sales Invoice":
		frappe.throw(_("Only Sales Invoices can be paid from this portal."), frappe.ValidationError)
	if invoice.customer not in customers:
		frappe.throw(_("This invoice is not linked to your customer account."), frappe.PermissionError)
	if not has_website_permission(invoice, "read", frappe.session.user):
		frappe.throw(_("You do not have access to this invoice."), frappe.PermissionError)
	if invoice.docstatus != 1 or invoice.is_return:
		frappe.throw(
			_("Only submitted sales invoices with an amount due can be paid online."),
			frappe.ValidationError,
		)
	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("This invoice has no outstanding amount to pay."), frappe.ValidationError)


def _lock_and_reload_invoice(invoice, customers: list[str]):
	# Serialize payment-request creation per invoice so concurrent portal clicks
	# cannot create parallel requests for the same outstanding amount.
	frappe.db.sql("select name from `tabSales Invoice` where name=%s for update", (invoice.name,))
	invoice.reload()
	_assert_payable_invoice(invoice, customers)
	return invoice


def _existing_payment_request(invoice) -> Any | None:
	rows = frappe.get_all(
		"Payment Request",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice.name,
			"docstatus": 1,
			"status": ["in", sorted(REUSABLE_PAYMENT_REQUEST_STATUSES)],
		},
		fields=["name", "status", "payment_url", "grand_total", "outstanding_amount", "currency"],
		order_by="creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _payment_result(invoice, payment_request, *, reused: bool) -> dict[str, Any]:
	payment_url = str(payment_request.get("payment_url") or "").strip()
	if not payment_url:
		frappe.throw(
			_(
				"Online payment is not available for this invoice. "
				"Please contact the business for payment assistance."
			),
			frappe.ValidationError,
		)
	return {
		"invoice": invoice.name,
		"payment_request": payment_request.name,
		"status": payment_request.status,
		"payment_url": payment_url,
		"amount": flt(payment_request.outstanding_amount or payment_request.grand_total),
		"currency": payment_request.currency or invoice.currency,
		"reused": reused,
	}


def _create_payment_request(invoice):
	gateway = get_gateway_details(frappe._dict(company=invoice.company)) or frappe._dict()
	if not gateway.get("name") or not gateway.get("payment_gateway") or not gateway.get("payment_account"):
		frappe.throw(
			_(
				"Online payment is not configured for this company. "
				"Please contact the business for payment assistance."
			),
			frappe.ValidationError,
		)
	if str(gateway.get("payment_channel") or "").strip() == "Phone":
		frappe.throw(
			_(
				"Online redirect payment is not configured for this company. "
				"Please contact the business for payment assistance."
			),
			frappe.ValidationError,
		)

	amount = flt(get_amount(invoice, gateway.get("payment_account")))
	if amount <= 0:
		frappe.throw(_("This invoice has no outstanding amount to pay."), frappe.ValidationError)

	party_account_currency = invoice.get("party_account_currency")
	if not party_account_currency:
		party_account = get_party_account("Customer", invoice.customer, invoice.company)
		party_account_currency = get_account_currency(party_account)

	payment_request = frappe.new_doc("Payment Request")
	payment_request.update(
		{
			"payment_gateway_account": gateway.get("name"),
			"payment_gateway": gateway.get("payment_gateway"),
			"payment_account": gateway.get("payment_account"),
			"payment_channel": gateway.get("payment_channel"),
			"payment_request_type": "Inward",
			"currency": invoice.currency,
			"party_account_currency": party_account_currency,
			"grand_total": amount,
			"mode_of_payment": None,
			"email_to": frappe.session.user,
			"subject": _("Payment Request for {0}").format(invoice.name),
			"message": gateway.get("message")
			or _("Please use the secure payment link to pay this invoice."),
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice.name,
			"company": invoice.company,
			"party_type": "Customer",
			"party": invoice.customer,
			"party_name": invoice.customer_name,
			"bank_account": get_party_bank_account("Customer", invoice.customer),
			"make_sales_invoice": 0,
			"mute_email": 1,
			"cost_center": invoice.get("cost_center"),
			"project": invoice.get("project"),
		}
	)
	for dimension in get_accounting_dimensions():
		payment_request.update({dimension: invoice.get(dimension)})

	# Portal users are not granted generic Payment Request create/submit rights.
	# This narrow boundary has already re-derived customer ownership and checked
	# ERPNext website permission for the exact submitted Sales Invoice.
	payment_request.flags.ignore_permissions = True
	payment_request.flags.mute_email = True
	payment_request.insert(ignore_permissions=True)
	payment_request.submit()
	return payment_request


@frappe.whitelist()
def request_invoice_payment(invoice_name: str) -> dict[str, Any]:
	customers = _assert_customer_portal_user()
	invoice_name = str(invoice_name or "").strip()
	if not invoice_name:
		frappe.throw(_("Sales Invoice is required."), frappe.ValidationError)
	if not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.throw(_("Sales Invoice was not found."), frappe.DoesNotExistError)

	invoice = frappe.get_doc("Sales Invoice", invoice_name)
	_assert_payable_invoice(invoice, customers)
	invoice = _lock_and_reload_invoice(invoice, customers)

	existing = _existing_payment_request(invoice)
	if existing:
		return _payment_result(invoice, frappe._dict(existing), reused=True)

	payment_request = _create_payment_request(invoice)
	return _payment_result(invoice, payment_request, reused=False)
