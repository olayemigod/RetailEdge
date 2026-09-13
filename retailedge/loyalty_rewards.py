from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
	get_loyalty_program_details_with_points,
)

from retailedge.professional_selling import (
	_assert_read,
	_coerce_values,
	_permission,
	_validate_context,
)


def _assert_can_prepare_sales_invoice() -> None:
	if not _permission("Sales Invoice", "create"):
		frappe.throw(_("You do not have permission to create Sales Invoice."), frappe.PermissionError)


def _normalise_requested_points(value: Any) -> int:
	numeric = flt(value)
	if numeric <= 0 or numeric != int(numeric):
		frappe.throw(_("Loyalty Points to redeem must be a positive whole number."))
	return int(numeric)


def _resolve_customer_loyalty_status(
	*,
	customer: str,
	company: str,
	posting_date,
) -> dict[str, Any]:
	customer = str(customer or "").strip()
	company = str(company or "").strip()
	if not customer:
		frappe.throw(_("Select a Customer before checking Loyalty Points."))
	_assert_read("Customer", customer)
	_assert_read("Company", company)

	program = str(frappe.db.get_value("Customer", customer, "loyalty_program") or "").strip()
	status: dict[str, Any] = {
		"customer": customer,
		"company": company,
		"posting_date": str(getdate(posting_date or nowdate())),
		"enrolled": False,
		"loyalty_program": "",
		"tier_name": "",
		"available_points": 0,
		"conversion_factor": 0,
		"available_redemption_value": 0,
		"currency": str(frappe.db.get_value("Company", company, "default_currency") or ""),
		"from_date": None,
		"to_date": None,
	}
	if not program:
		status["message"] = _(
			"This Customer has no assigned Loyalty Program. Use the native Customer or Loyalty Program workflow to enrol them."
		)
		return status

	program_company = str(frappe.db.get_value("Loyalty Program", program, "company") or "").strip()
	if program_company != company:
		frappe.throw(_("The Customer's Loyalty Program is not valid for the selected Company."))

	details = get_loyalty_program_details_with_points(
		customer=customer,
		loyalty_program=program,
		expiry_date=status["posting_date"],
		company=company,
	)
	available_points = max(cint(details.get("loyalty_points")), 0)
	conversion_factor = max(flt(details.get("conversion_factor")), 0)
	status.update(
		{
			"enrolled": True,
			"loyalty_program": program,
			"tier_name": str(details.get("tier_name") or ""),
			"available_points": available_points,
			"conversion_factor": conversion_factor,
			"available_redemption_value": flt(available_points * conversion_factor),
			"from_date": details.get("from_date"),
			"to_date": details.get("to_date"),
			"message": _(
				"ERPNext will revalidate the current balance and final invoice value when the draft is saved."
			),
		}
	)
	return status


@frappe.whitelist()
def get_customer_loyalty_status(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_prepare_sales_invoice()
	values = _coerce_values(values)
	company, _branch, _warehouse = _validate_context(values)
	status = _resolve_customer_loyalty_status(
		customer=str(values.get("customer") or "").strip(),
		company=company,
		posting_date=values.get("posting_date") or nowdate(),
	)
	status.update(
		{
			"can_manage_programs": _permission("Loyalty Program", "read"),
			"native_route": "/app/loyalty-program",
		}
	)
	return status


def apply_loyalty_redemption_to_draft(doc, requested_points: Any) -> dict[str, Any]:
	"""Set native loyalty fields on an unsaved/submitted-free Sales Invoice draft.

	The caller saves the draft so ERPNext can derive the redemption amount,
	account and cost centre through its normal Sales Invoice validation.
	"""
	_assert_can_prepare_sales_invoice()
	if doc.doctype != "Sales Invoice" or doc.docstatus != 0:
		frappe.throw(_("Loyalty redemption can only be prepared on a draft Sales Invoice."))
	if cint(doc.get("is_return")) or cint(doc.get("is_consolidated")):
		frappe.throw(
			_(
				"Use the native ERPNext Sales Invoice workflow for loyalty on returns or consolidated invoices."
			)
		)

	points = _normalise_requested_points(requested_points)
	status = _resolve_customer_loyalty_status(
		customer=doc.customer,
		company=doc.company,
		posting_date=doc.posting_date,
	)
	if not status["enrolled"]:
		frappe.throw(_("The Customer has no assigned Loyalty Program."))
	if points > status["available_points"]:
		frappe.throw(
			_("Only {0} Loyalty Points are currently available for this Customer.").format(
				status["available_points"]
			)
		)

	doc.redeem_loyalty_points = 1
	doc.loyalty_program = status["loyalty_program"]
	doc.loyalty_points = points
	return status
