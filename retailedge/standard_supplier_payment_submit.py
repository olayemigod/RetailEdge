from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.advanced_payments import (
	PAYMENT_ENTRY_DOCTYPE,
	_company_currency,
	_invoice_branch,
	_payment_branch_field,
)
from retailedge.operating_context import (
	get_operational_branch_scope,
	resolve_operational_branch,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness

SUPPLIER_DOCTYPE = "Supplier"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
MAX_DRAFT_ROWS = 50
MAX_STANDARD_REFERENCES = 20
TOLERANCE = 0.005


def _assert_permission(doctype: str, ptype: str, doc: Any | None = None) -> None:
	if not frappe.has_permission(doctype, ptype, doc=doc):
		frappe.throw(
			_("You do not have {0} permission for {1}.").format(_(ptype), _(doctype)),
			frappe.PermissionError,
		)


def _get_payment_entry(name: str) -> Any:
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Payment Entry is required."))
	if not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, name):
		frappe.throw(_("Payment Entry {0} does not exist.").format(name))
	doc = frappe.get_doc(PAYMENT_ENTRY_DOCTYPE, name)
	_assert_permission(PAYMENT_ENTRY_DOCTYPE, "read", doc)
	return doc


def _payment_branch(doc: Any) -> str:
	field = _payment_branch_field()
	return str(getattr(doc, field, None) or "") if field else ""


def _validate_payment_branch(doc: Any) -> str:
	branch = _payment_branch(doc)
	company = str(getattr(doc, "company", "") or "").strip()
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		return str(
			resolve_operational_branch(
				company,
				branch,
				user=frappe.session.user,
			).get("branch")
			or ""
		).strip()
	if scope["restricted"]:
		frappe.throw(
			_("Payment Entry {0} has no Branch attribution for your restricted access.").format(doc.name),
			frappe.PermissionError,
		)
	return ""


def _validate_selected_context(
	doc: Any,
	branch: str,
	company: str | None = None,
	supplier: str | None = None,
	selected_branch: str | None = None,
) -> None:
	company = str(company or "").strip()
	supplier = str(supplier or "").strip()
	selected_branch = str(selected_branch or "").strip()
	if company and str(getattr(doc, "company", "") or "") != company:
		frappe.throw(_("Payment Entry does not belong to the selected Company."), frappe.PermissionError)
	if supplier and str(getattr(doc, "party", "") or "") != supplier:
		frappe.throw(_("Payment Entry does not belong to the selected Supplier."), frappe.PermissionError)
	if selected_branch and branch != selected_branch:
		frappe.throw(_("Payment Entry does not belong to the selected Branch."), frappe.PermissionError)


def _account_snapshot(account: str) -> dict[str, Any]:
	if not account:
		return {}
	row = frappe.db.get_value(
		"Account",
		account,
		["name", "company", "account_type", "account_currency"],
		as_dict=True,
	)
	return dict(row or {})


def _reference_previews(doc: Any, payment_branch: str) -> tuple[list[dict[str, Any]], list[str]]:
	"""Revalidate every standard supplier invoice allocation against current ERPNext truth."""
	blockers: list[str] = []
	rows = list(getattr(doc, "references", None) or [])
	if not rows:
		blockers.append(_("Supplier advances require Advanced ERPNext review."))
		return [], blockers
	if len(rows) > MAX_STANDARD_REFERENCES:
		blockers.append(
			_("Standard supplier settlement supports at most {0} Purchase Invoices.").format(MAX_STANDARD_REFERENCES)
		)
		return [], blockers

	company = str(getattr(doc, "company", "") or "")
	supplier = str(getattr(doc, "party", "") or "")
	company_currency = _company_currency(company)
	seen: set[str] = set()
	reference_branches: set[str] = set()
	result: list[dict[str, Any]] = []

	for index, row in enumerate(rows, start=1):
		if str(getattr(row, "reference_doctype", "") or "") != PURCHASE_INVOICE_DOCTYPE:
			blockers.append(_("Only Purchase Invoice allocations are supported by standard supplier settlement."))
			continue

		invoice_name = str(getattr(row, "reference_name", "") or "").strip()
		allocated_amount = flt(getattr(row, "allocated_amount", 0))
		if not invoice_name or allocated_amount <= 0:
			blockers.append(_("Purchase Invoice allocation on row {0} is incomplete.").format(index))
			continue
		if invoice_name in seen:
			blockers.append(_("Purchase Invoice {0} is allocated more than once.").format(invoice_name))
			continue
		seen.add(invoice_name)

		if not frappe.db.exists(PURCHASE_INVOICE_DOCTYPE, invoice_name):
			blockers.append(_("Referenced Purchase Invoice {0} no longer exists.").format(invoice_name))
			result.append({"purchase_invoice": invoice_name, "allocated_amount": allocated_amount})
			continue

		invoice = frappe.get_doc(PURCHASE_INVOICE_DOCTYPE, invoice_name)
		_assert_permission(PURCHASE_INVOICE_DOCTYPE, "read", invoice)
		invoice_branch = _invoice_branch(invoice)
		invoice_scope = get_operational_branch_scope(
			str(getattr(invoice, "company", "") or ""),
			user=frappe.session.user,
		)
		if invoice_branch:
			invoice_branch = str(
				resolve_operational_branch(
					invoice.company,
					invoice_branch,
					user=frappe.session.user,
				).get("branch")
				or ""
			).strip()
		elif invoice_scope["restricted"]:
			blockers.append(
				_("Referenced Purchase Invoice {0} has no Branch attribution for your restricted access.").format(
					invoice_name
				)
			)

		if cint(getattr(invoice, "docstatus", 0)) != 1:
			blockers.append(_("Referenced Purchase Invoice {0} is not submitted.").format(invoice_name))
		if cint(getattr(invoice, "is_return", 0)):
			blockers.append(_("Return Purchase Invoices require Advanced ERPNext review."))
		if str(getattr(invoice, "company", "") or "") != company:
			blockers.append(_("Payment Entry and Purchase Invoice {0} must belong to the same Company.").format(invoice_name))
		if str(getattr(invoice, "supplier", "") or "") != supplier:
			blockers.append(_("Payment Entry and Purchase Invoice {0} must belong to the same Supplier.").format(invoice_name))
		if invoice_branch:
			reference_branches.add(invoice_branch)
		if invoice_branch and payment_branch and invoice_branch != payment_branch:
			blockers.append(_("Payment Entry and Purchase Invoice {0} must belong to the same Branch.").format(invoice_name))

		invoice_currency = str(getattr(invoice, "currency", "") or company_currency)
		if invoice_currency != company_currency:
			blockers.append(_("Multi-currency Purchase Invoice payments require Advanced ERPNext review."))

		outstanding = flt(getattr(invoice, "outstanding_amount", 0))
		if outstanding <= 0:
			blockers.append(_("Purchase Invoice {0} no longer has a positive outstanding amount.").format(invoice_name))
		elif allocated_amount > outstanding + TOLERANCE:
			blockers.append(
				_("The draft allocation for Purchase Invoice {0} exceeds its current outstanding amount.").format(
					invoice_name
				)
			)

		result.append(
			{
				"purchase_invoice": invoice_name,
				"allocated_amount": allocated_amount,
				"invoice_outstanding_amount": outstanding,
				"branch": invoice_branch,
			}
		)

	if len(reference_branches) > 1:
		blockers.append(_("All Purchase Invoice allocations in a standard supplier settlement must belong to one Branch."))
	if reference_branches and _payment_branch_field() and not payment_branch:
		blockers.append(_("The Payment Entry must carry the Branch of its Purchase Invoice allocations."))

	return result, list(dict.fromkeys(blockers))

def _workflow_submit_blocker(workflow_readiness: dict[str, Any]) -> str:
	if str(workflow_readiness.get("source") or "") != "frappe":
		return ""
	return _(
		"Payment Entry is controlled by active Workflow {0}. Use the available workflow action in EdgeSuite."
	).format(workflow_readiness.get("workflow") or _("Payment Entry Workflow"))


def _standard_submit_blockers(
	doc: Any,
	payment_branch: str,
	workflow_readiness: dict[str, Any] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
	blockers: list[str] = []
	if cint(getattr(doc, "docstatus", 0)) != 0:
		blockers.append(_("Only draft Payment Entries can use standard EdgeSuite submission."))
	if str(getattr(doc, "payment_type", "") or "") != "Pay":
		blockers.append(_("Only Pay Payment Entries are supported by the supplier-payment workflow."))
	if str(getattr(doc, "party_type", "") or "") != SUPPLIER_DOCTYPE:
		blockers.append(_("Only Supplier Payment Entries are supported by this workflow."))
	if not str(getattr(doc, "company", "") or "") or not str(getattr(doc, "party", "") or ""):
		blockers.append(_("Payment Entry Company and Supplier are required."))

	paid_amount = flt(getattr(doc, "paid_amount", 0))
	received_amount = flt(getattr(doc, "received_amount", 0))
	if paid_amount <= 0 or received_amount <= 0:
		blockers.append(_("Payment amount must be greater than zero."))
	if not str(getattr(doc, "paid_from", "") or "") or not str(getattr(doc, "paid_to", "") or ""):
		blockers.append(_("Payment accounts are incomplete. Use Advanced ERPNext review."))

	company = str(getattr(doc, "company", "") or "")
	company_currency = _company_currency(company) if company else ""
	paid_from_currency = str(getattr(doc, "paid_from_account_currency", "") or company_currency)
	paid_to_currency = str(getattr(doc, "paid_to_account_currency", "") or company_currency)
	if not company_currency or paid_from_currency != company_currency or paid_to_currency != company_currency:
		blockers.append(_("Multi-currency Payment Entries require Advanced ERPNext review."))

	paid_from = _account_snapshot(str(getattr(doc, "paid_from", "") or ""))
	paid_to = _account_snapshot(str(getattr(doc, "paid_to", "") or ""))
	if paid_from and paid_from.get("company") != company:
		blockers.append(_("The payment account must belong to the Payment Entry Company."))
	if paid_from and paid_from.get("account_type") not in {"Bank", "Cash"}:
		blockers.append(_("Standard supplier payment requires a Bank or Cash payment account."))
	if paid_to and paid_to.get("company") != company:
		blockers.append(_("The supplier payable account must belong to the Payment Entry Company."))
	if paid_to and paid_to.get("account_type") != "Payable":
		blockers.append(_("Standard supplier payment requires the Supplier payable account."))

	if getattr(doc, "book_advance_payments_in_separate_party_account", 0):
		blockers.append(_("Separate party-account advances require Advanced ERPNext review."))
	if list(getattr(doc, "deductions", None) or []) or abs(flt(getattr(doc, "difference_amount", 0))) > TOLERANCE:
		blockers.append(_("Payments with deductions or exchange differences require Advanced ERPNext review."))

	references, reference_blockers = _reference_previews(doc, payment_branch)
	blockers.extend(reference_blockers)
	if references:
		allocated_amount = sum(flt(reference.get("allocated_amount")) for reference in references)
		if abs(paid_amount - allocated_amount) > TOLERANCE:
			blockers.append(_("Standard supplier settlement must allocate the full payment across its Purchase Invoices."))
		if abs(flt(getattr(doc, "unallocated_amount", 0))) > TOLERANCE:
			blockers.append(_("Supplier advances or unallocated amounts require Advanced ERPNext review."))

	workflow_readiness = workflow_readiness or get_workflow_readiness(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		doc=doc,
	)
	workflow_blocker = _workflow_submit_blocker(workflow_readiness)
	if workflow_blocker:
		blockers.append(workflow_blocker)
	elif not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc):
		blockers.append(_("You do not have permission to submit this Payment Entry."))
	return blockers, references


def _build_preview(
	doc: Any,
	company: str | None = None,
	supplier: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	payment_branch = _validate_payment_branch(doc)
	_validate_selected_context(doc, payment_branch, company=company, supplier=supplier, selected_branch=branch)
	workflow_readiness = get_workflow_readiness(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		doc=doc,
	)
	blockers, references = _standard_submit_blockers(
		doc,
		payment_branch,
		workflow_readiness=workflow_readiness,
	)
	workflow_blocker = _workflow_submit_blocker(workflow_readiness)
	workflow_eligible = bool(
		workflow_blocker
		and not [blocker for blocker in blockers if blocker != workflow_blocker]
	)
	paid_amount = flt(getattr(doc, "paid_amount", 0))
	allocated_amount = sum(flt(reference.get("allocated_amount")) for reference in references)
	first_reference = references[0] if len(references) == 1 else None
	return {
		"payment_entry": doc.name,
		"payment_entry_modified": str(getattr(doc, "modified", "") or ""),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": payment_branch,
		"supplier": str(getattr(doc, "party", "") or ""),
		"posting_date": str(getattr(doc, "posting_date", "") or ""),
		"mode_of_payment": str(getattr(doc, "mode_of_payment", "") or ""),
		"paid_from": str(getattr(doc, "paid_from", "") or ""),
		"paid_to": str(getattr(doc, "paid_to", "") or ""),
		"currency": _company_currency(str(getattr(doc, "company", "") or "")),
		"paid_amount": paid_amount,
		"allocated_amount": allocated_amount,
		"unallocated_amount": max(paid_amount - allocated_amount, 0),
		"reference_count": len(references),
		"references": references,
		"purchase_invoice": first_reference.get("purchase_invoice") if first_reference else "",
		"invoice_outstanding_amount": first_reference.get("invoice_outstanding_amount") if first_reference else None,
		"payment_kind": "Supplier Invoice Payment" if len(references) == 1 else "Supplier Invoice Settlement",
		"docstatus": cint(getattr(doc, "docstatus", 0)),
		"status": "Draft" if cint(getattr(doc, "docstatus", 0)) == 0 else str(getattr(doc, "status", "") or "Submitted"),
		"blockers": blockers,
		"can_submit": not blockers,
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": workflow_eligible,
		"persistence": "none",
		"source_of_truth": "ERPNext Payment Entry",
		"route": f"/app/payment-entry/{doc.name}",
	}


@frappe.whitelist()
def get_supplier_payment_submit_preview(
	payment_entry: str,
	company: str | None = None,
	supplier: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Return a read-only review of one standard draft supplier payment."""
	doc = _get_payment_entry(payment_entry)
	return _build_preview(doc, company=company, supplier=supplier, branch=branch)


@frappe.whitelist()
def list_standard_supplier_payment_drafts(
	company: str,
	supplier: str,
	branch: str | None = None,
	limit: int | str = 25,
) -> list[dict[str, Any]]:
	"""List permission-visible draft Pay/Supplier Payment Entries in the selected scope."""
	company = str(company or "").strip()
	supplier = str(supplier or "").strip()
	branch = str(branch or "").strip()
	if not company or not supplier:
		frappe.throw(_("Choose Company and Supplier before reviewing draft payments."))
	_assert_permission("Company", "read", frappe.get_doc("Company", company))
	_assert_permission(SUPPLIER_DOCTYPE, "read", frappe.get_doc(SUPPLIER_DOCTYPE, supplier))

	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		branch = str(
			resolve_operational_branch(
				company,
				branch,
				user=frappe.session.user,
			).get("branch")
			or ""
		).strip()
	elif scope["restricted"]:
		branch = str(
			resolve_operational_branch(
				company,
				"",
				user=frappe.session.user,
			).get("branch")
			or ""
		).strip()

	filters: dict[str, Any] = {
		"docstatus": 0,
		"payment_type": "Pay",
		"party_type": SUPPLIER_DOCTYPE,
		"company": company,
		"party": supplier,
	}
	branch_field = _payment_branch_field()
	if branch:
		if not branch_field:
			frappe.throw(
				_("Payment Entry branch attribution is unavailable. Run the site migration before using Branch-scoped payment submission.")
			)
		filters[branch_field] = branch

	rows = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=["name"],
		order_by="modified desc",
		limit_page_length=max(1, min(cint(limit) or 25, MAX_DRAFT_ROWS)),
	)
	return [
		_build_preview(
			_get_payment_entry(row.name),
			company=company,
			supplier=supplier,
			branch=branch or None,
		)
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def apply_standard_supplier_payment_workflow_action(
	payment_entry: str,
	action: str,
	expected_payment_entry_modified: str | None = None,
	expected_workflow_state: str | None = None,
	company: str | None = None,
	supplier: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	payment_entry = str(payment_entry or "").strip()
	action = str(action or "").strip()
	if not payment_entry or not action:
		frappe.throw(_("Payment Entry and workflow action are required."))
	if not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, payment_entry):
		frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry))

	frappe.db.sql(
		"SELECT name FROM `tabPayment Entry` WHERE name = %s FOR UPDATE",
		(payment_entry,),
	)
	doc = _get_payment_entry(payment_entry)
	payment_branch = _validate_payment_branch(doc)
	_validate_selected_context(
		doc,
		payment_branch,
		company=company,
		supplier=supplier,
		selected_branch=branch,
	)

	expected_modified = str(expected_payment_entry_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("Payment Entry {0} changed after the review. Refresh before applying the workflow action.").format(
				doc.name
			)
		)

	preview = _build_preview(
		doc,
		company=company,
		supplier=supplier,
		branch=branch,
	)
	if not preview.get("workflow_eligible"):
		frappe.throw(
			_(
				"This Payment Entry cannot use the standard EdgeSuite workflow path. Review the current blockers or use Advanced ERPNext."
			)
		)

	return apply_document_workflow_action(
		doctype=PAYMENT_ENTRY_DOCTYPE,
		name=doc.name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)


@frappe.whitelist(methods=["POST"])
def submit_standard_supplier_payment(
	payment_entry: str,
	expected_payment_entry_modified: str | None = None,
	company: str | None = None,
	supplier: str | None = None,
	branch: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed standard supplier Payment Entry through native ERPNext."""
	payment_entry = str(payment_entry or "").strip()
	if not payment_entry:
		frappe.throw(_("Payment Entry is required."))
	if not frappe.db.exists(PAYMENT_ENTRY_DOCTYPE, payment_entry):
		frappe.throw(_("Payment Entry {0} does not exist.").format(payment_entry))

	frappe.db.sql(
		"SELECT name FROM `tabPayment Entry` WHERE name = %s FOR UPDATE",
		(payment_entry,),
	)
	doc = _get_payment_entry(payment_entry)
	payment_branch = _validate_payment_branch(doc)
	_validate_selected_context(doc, payment_branch, company=company, supplier=supplier, selected_branch=branch)

	expected_modified = str(expected_payment_entry_modified or "").strip()
	current_modified = str(getattr(doc, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(_("Payment Entry {0} changed after the review. Refresh before submitting.").format(doc.name))

	blockers, references = _standard_submit_blockers(doc, payment_branch)
	if blockers:
		frappe.throw("<br>".join(blockers))

	# ERPNext remains authoritative for Payment Entry posting, GL/Payment Ledger
	# side effects, Purchase Invoice outstanding and supplier balances.
	doc.submit()
	if cint(getattr(doc, "docstatus", 0)) != 1:
		frappe.throw(_("ERPNext did not submit Payment Entry {0}.").format(doc.name))
	doc.reload()

	updated_references = []
	for reference in references:
		invoice_name = str(reference.get("purchase_invoice") or "")
		updated_references.append(
			{
				**reference,
				"invoice_outstanding_amount": (
					flt(frappe.db.get_value(PURCHASE_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"))
					if invoice_name
					else None
				),
			}
		)
	first_reference = updated_references[0] if len(updated_references) == 1 else None
	return {
		"payment_entry": doc.name,
		"docstatus": cint(getattr(doc, "docstatus", 0)),
		"status": str(getattr(doc, "status", "") or "Submitted"),
		"company": str(getattr(doc, "company", "") or ""),
		"branch": _payment_branch(doc),
		"supplier": str(getattr(doc, "party", "") or ""),
		"paid_amount": flt(getattr(doc, "paid_amount", 0)),
		"reference_count": len(updated_references),
		"references": updated_references,
		"purchase_invoice": first_reference.get("purchase_invoice") if first_reference else "",
		"invoice_outstanding_amount": first_reference.get("invoice_outstanding_amount") if first_reference else None,
		"source_of_truth": "ERPNext Payment Entry submit",
		"route": f"/app/payment-entry/{doc.name}",
	}
