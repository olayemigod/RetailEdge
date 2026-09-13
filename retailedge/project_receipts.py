from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_party_details

from retailedge.advanced_payments import _payment_branch_field
from retailedge.branch_context import validate_user_branch_access
from retailedge.guided_payment import get_simple_payment_mode_details

PROJECT_DOCTYPE = "Project"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"


def _assert_permission(doctype: str, ptype: str, name: str | None = None) -> None:
	if not frappe.has_permission(doctype, ptype, doc=name):
		frappe.throw(
			_("You do not have {0} permission for {1}.").format(_(ptype), _(doctype)),
			frappe.PermissionError,
		)


@frappe.whitelist(methods=["POST"])
def create_project_receipt_draft(values: dict | str | None = None) -> dict[str, Any]:
	"""Create a draft ERPNext customer receipt explicitly attributed to a Project.

	The Project is the operational context; ERPNext Payment Entry remains the cash
	and accounting source of truth. This method never submits the Payment Entry.
	"""
	_assert_permission(PAYMENT_ENTRY_DOCTYPE, "create")
	values = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	project = str(values.get("project") or "").strip()
	if not project:
		frappe.throw(_("Project is required."))
	_assert_permission(PROJECT_DOCTYPE, "read", project)
	project_doc = frappe.get_doc(PROJECT_DOCTYPE, project)
	if not project_doc.company:
		frappe.throw(_("Project {0} has no Company.").format(project))
	if not project_doc.customer:
		frappe.throw(_("Project {0} has no Customer. Assign a Customer before recording project receipts.").format(project))

	company = str(values.get("company") or project_doc.company).strip()
	if company != project_doc.company:
		frappe.throw(_("Project receipts must use the Project Company {0}.").format(project_doc.company))
	_assert_permission("Company", "read", company)

	customer = str(values.get("customer") or project_doc.customer).strip()
	if customer != project_doc.customer:
		frappe.throw(_("Project receipts must use the Project Customer {0}.").format(project_doc.customer))
	_assert_permission("Customer", "read", customer)

	branch = str(values.get("branch") or "").strip()
	branch_field = _payment_branch_field()
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)
		if not branch_field:
			frappe.throw(
				_("Payment Entry branch attribution is not available. Run bench migrate before recording a Branch-scoped Project Receipt."),
			)

	posting_date = getdate(values.get("posting_date") or nowdate())
	party_details = get_party_details(company, "Customer", customer, posting_date)
	party_account = str(party_details.get("party_account") or "")
	party_currency = str(party_details.get("party_account_currency") or "")
	company_currency = str(frappe.db.get_value("Company", company, "default_currency") or "")
	if not party_account:
		frappe.throw(_("No receivable account could be resolved for Project Customer {0}.").format(customer))
	if not company_currency or party_currency != company_currency:
		frappe.throw(_("Guided Project Receipt currently supports company-currency customer accounts only. Use full Payment Entry for multi-currency receipts."))

	mode_of_payment = str(values.get("mode_of_payment") or "").strip()
	if not mode_of_payment:
		frappe.throw(_("Mode of Payment is required."))
	mode_details = get_simple_payment_mode_details("receive-customer-payment", company, mode_of_payment)
	if str(mode_details.get("account_currency") or "") != company_currency:
		frappe.throw(_("Guided Project Receipt currently supports company-currency bank/cash accounts only."))

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))

	doc = frappe.new_doc(PAYMENT_ENTRY_DOCTYPE)
	doc.payment_type = "Receive"
	doc.company = company
	doc.posting_date = posting_date
	doc.party_type = "Customer"
	doc.party = customer
	doc.project = project
	doc.cost_center = project_doc.cost_center or None
	doc.mode_of_payment = mode_of_payment
	doc.paid_from = party_account
	doc.paid_to = mode_details["account"]
	doc.paid_amount = amount
	doc.received_amount = amount

	if branch and branch_field:
		setattr(doc, branch_field, branch)

	if mode_details.get("reference_required"):
		reference_no = str(values.get("reference_no") or "").strip()
		if not reference_no:
			frappe.throw(_("Reference No is required for this Mode of Payment."))
		doc.reference_no = reference_no
		doc.reference_date = getdate(values.get("reference_date") or posting_date)

	if values.get("remarks"):
		doc.custom_remarks = 1
		doc.remarks = str(values.get("remarks")).strip()

	# Draft only. Native ERPNext validation, review, submission and later invoice
	# reconciliation remain authoritative.
	doc.insert()
	return {
		"doctype": PAYMENT_ENTRY_DOCTYPE,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"project": project,
		"customer": customer,
		"company": company,
		"branch": getattr(doc, branch_field, "") if branch_field else "",
		"amount": flt(doc.received_amount),
		"allocation_status": "Unallocated" if not doc.get("references") else "Allocated",
		"source_of_truth": PAYMENT_ENTRY_DOCTYPE,
		"route": f"/app/payment-entry/{doc.name}",
	}
