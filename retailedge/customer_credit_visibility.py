from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.selling.doctype.customer.customer import (
	get_credit_limit,
	get_customer_outstanding,
	get_customer_overdue_amount,
	get_overdue_billing_threshold,
)

CREDIT_REPORT = "Customer Credit Balance"


def _assert_read(doctype: str, name: str) -> None:
	name = str(name or "").strip()
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} is not available.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _can_read_credit_report() -> bool:
	try:
		return bool(
			frappe.db.exists("Report", CREDIT_REPORT)
			and frappe.has_permission("Report", "read", doc=CREDIT_REPORT)
		)
	except Exception:
		return False


def _sales_order_bypass(customer: str, company: str) -> bool:
	return bool(
		cint(
			frappe.db.get_value(
				"Customer Credit Limit",
				{
					"parent": customer,
					"parenttype": "Customer",
					"company": company,
				},
				"bypass_credit_limit_check",
			)
		)
	)


@frappe.whitelist()
def get_customer_credit_visibility(customer: str, company: str) -> dict[str, Any]:
	"""Return read-only ERPNext customer credit context for guided selling."""
	customer = str(customer or "").strip()
	company = str(company or "").strip()
	_assert_read("Customer", customer)
	_assert_read("Company", company)

	if not _can_read_credit_report():
		frappe.throw(
			_("You do not have permission to view customer credit balances."),
			frappe.PermissionError,
		)

	customer_state = frappe.db.get_value(
		"Customer",
		customer,
		["customer_name", "customer_group", "is_frozen", "disabled"],
		as_dict=True,
	) or frappe._dict()
	bypass_sales_order_check = _sales_order_bypass(customer, company)

	credit_limit = flt(get_credit_limit(customer, company))
	outstanding = flt(
		get_customer_outstanding(
			customer,
			company,
			ignore_outstanding_sales_order=bypass_sales_order_check,
		)
	)
	overdue_threshold = flt(get_overdue_billing_threshold(customer, company))
	overdue_amount = flt(get_customer_overdue_amount(customer, company))
	overdue_enforcement_enabled = bool(
		cint(frappe.get_single_value("Accounts Settings", "enable_overdue_billing_threshold"))
	)

	has_credit_limit = credit_limit > 0
	remaining_credit = credit_limit - outstanding if has_credit_limit else None
	credit_limit_crossed = bool(has_credit_limit and outstanding > credit_limit)
	overdue_threshold_crossed = bool(
		overdue_enforcement_enabled
		and overdue_threshold > 0
		and overdue_amount > overdue_threshold
	)

	return {
		"customer": customer,
		"customer_name": str(customer_state.get("customer_name") or customer),
		"customer_group": str(customer_state.get("customer_group") or ""),
		"company": company,
		"company_currency": str(frappe.get_cached_value("Company", company, "default_currency") or ""),
		"credit_limit": credit_limit,
		"has_credit_limit": has_credit_limit,
		"outstanding_exposure": outstanding,
		"remaining_credit": remaining_credit,
		"credit_limit_crossed": credit_limit_crossed,
		"sales_order_credit_check_bypassed": bypass_sales_order_check,
		"overdue_billing_threshold": overdue_threshold,
		"overdue_amount": overdue_amount,
		"overdue_enforcement_enabled": overdue_enforcement_enabled,
		"overdue_threshold_crossed": overdue_threshold_crossed,
		"is_frozen": bool(cint(customer_state.get("is_frozen"))),
		"disabled": bool(cint(customer_state.get("disabled"))),
		"source_of_truth": "ERPNext customer credit helpers and Customer Credit Limit configuration",
		"scope": "company",
		"advisory_only": True,
		"final_enforcement": "ERPNext Sales Order / Sales Invoice submission controls",
	}
