from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime

from retailedge.operating_context import get_operating_context
from retailedge.professional_selling import _validate_stored_operational_branch
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness


SUPPORTED_DOCTYPES = {"Quotation", "Sales Order"}
_LOCK_TABLES = {
	"Quotation": "tabQuotation",
	"Sales Order": "tabSales Order",
}
MAX_ITEM_SUMMARY = 10


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _get_supported_document(doctype: str, name: str):
	doctype = _clean(doctype)
	name = _clean(name)
	if doctype not in SUPPORTED_DOCTYPES:
		frappe.throw(
			_("Standard selling completion supports only Customer Quotation and Sales Order."),
			frappe.ValidationError,
		)
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name or "(blank)"))
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to read {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)
	return doc


def _lock_supported_document(doctype: str, name: str) -> None:
	doctype = _clean(doctype)
	if doctype not in SUPPORTED_DOCTYPES:
		frappe.throw(_("Unsupported selling completion document."), frappe.ValidationError)
	table = _LOCK_TABLES[doctype]
	rows = frappe.db.sql(
		f"SELECT name FROM \`{table}\` WHERE name = %s FOR UPDATE",
		(_clean(name),),
	)
	if not rows:
		frappe.throw(_("{0} {1} no longer exists.").format(doctype, name))


def _stored_branch(doc) -> str:
	return _clean(doc.get("branch") or doc.get("retailedge_branch"))


def _validate_standard_context(doc) -> tuple[str, str]:
	company = _clean(doc.get("company"))
	if not company:
		frappe.throw(_("{0} {1} has no Company.").format(doc.doctype, doc.name))
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)

	branch = _validate_stored_operational_branch(
		company=company,
		branch=_stored_branch(doc),
		label=_("{0} {1}").format(doc.doctype, doc.name),
	)

	operating = get_operating_context() or {}
	operating_company = _clean(operating.get("company"))
	operating_branch = _clean(operating.get("branch"))
	if operating_company and operating_company != company:
		frappe.throw(
			_(
				"{0} {1} belongs to another Company. Change Operating Context before completing it."
			).format(doc.doctype, doc.name),
			frappe.PermissionError,
		)
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(
			_("{0} {1} does not belong to the current Operating Branch.").format(
				doc.doctype, doc.name
			),
			frappe.PermissionError,
		)
	return company, branch


def _standard_shape_blockers(doc) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft documents can use standard EdgeSuite completion."))
	if doc.get("amended_from"):
		blockers.append(_("Amended documents require Advanced ERPNext review."))

	status = _clean(doc.get("status"))
	if status and status != "Draft":
		blockers.append(
			_("{0} status {1} requires Advanced ERPNext review.").format(doc.doctype, status)
		)

	order_type = _clean(doc.get("order_type"))
	if order_type not in {"", "Sales"}:
		blockers.append(
			_("{0} order type {1} requires Advanced ERPNext review.").format(
				doc.doctype, order_type
			)
		)

	items = list(doc.get("items") or [])
	if not items:
		blockers.append(_("{0} must contain at least one item.").format(doc.doctype))

	if doc.doctype == "Quotation":
		if _clean(doc.get("quotation_to")) != "Customer":
			blockers.append(_("Non-Customer Quotation requires Advanced ERPNext review."))
		if not _clean(doc.get("party_name")):
			blockers.append(_("Quotation Customer is required."))
	elif doc.doctype == "Sales Order":
		if not _clean(doc.get("customer")):
			blockers.append(_("Sales Order Customer is required."))
		if cint(doc.get("is_internal_customer")):
			blockers.append(_("Internal-customer Sales Order requires Advanced ERPNext review."))
		if _clean(doc.get("represents_company")):
			blockers.append(_("Inter-company Sales Order requires Advanced ERPNext review."))
		if _clean(doc.get("inter_company_order_reference")):
			blockers.append(_("Inter-company Sales Order requires Advanced ERPNext review."))

	return blockers


def _party_value(doc) -> str:
	if doc.doctype == "Quotation":
		return _clean(doc.get("party_name"))
	return _clean(doc.get("customer"))


def _item_summary(doc) -> list[dict[str, Any]]:
	result: list[dict[str, Any]] = []
	for row in list(doc.get("items") or [])[:MAX_ITEM_SUMMARY]:
		result.append(
			{
				"item_code": _clean(row.get("item_code")),
				"item_name": _clean(row.get("item_name")),
				"qty": flt(row.get("qty")),
				"rate": flt(row.get("rate")),
				"amount": flt(row.get("amount")),
			}
		)
	return result


def _build_preview(doc) -> dict[str, Any]:
	company, branch = _validate_standard_context(doc)
	standard_blockers = _standard_shape_blockers(doc)
	workflow_readiness = get_workflow_readiness(doctype=doc.doctype, doc=doc)
	workflow_controlled = _clean(workflow_readiness.get("source")) == "frappe"

	blockers = list(standard_blockers)
	if not workflow_controlled and not frappe.has_permission(doc.doctype, "submit", doc=doc):
		blockers.append(
			_("You do not have permission to submit this {0}.").format(doc.doctype)
		)

	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or ("Draft" if cint(doc.docstatus) == 0 else ""),
		"company": company,
		"branch": branch,
		"party": _party_value(doc),
		"currency": _clean(doc.get("currency")),
		"grand_total": flt(doc.get("grand_total")),
		"item_count": len(list(doc.get("items") or [])),
		"items": _item_summary(doc),
		"blockers": blockers,
		"can_submit": bool(not blockers and not workflow_controlled and cint(doc.docstatus) == 0),
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": bool(workflow_controlled and not standard_blockers and cint(doc.docstatus) == 0),
		"persistence": "none",
		"source_of_truth": "ERPNext",
		"route": f"/app/{frappe.scrub(doc.doctype).replace('_', '-')}/{doc.name}",
	}


def _assert_expected_modified(doc, expected_modified: str | None) -> str:
	expected_modified = _clean(expected_modified)
	if not expected_modified:
		frappe.throw(
			_("The reviewed document version is required. Refresh completion review."),
			frappe.TimestampMismatchError,
		)
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid reviewed document version."), frappe.ValidationError)
	if expected != current:
		frappe.throw(
			_(
				"{0} {1} changed after completion review. Refresh before continuing."
			).format(doc.doctype, doc.name),
			frappe.TimestampMismatchError,
		)
	return expected_modified


@frappe.whitelist()
def get_standard_selling_completion_preview(doctype: str, name: str) -> dict[str, Any]:
	"""Return a persistence-free standard completion review for one Quote or Sales Order."""
	doc = _get_supported_document(doctype, name)
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def submit_standard_selling_document(
	doctype: str,
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed standard Quotation or Sales Order through native ERPNext."""
	doctype = _clean(doctype)
	name = _clean(name)
	_lock_supported_document(doctype, name)
	doc = _get_supported_document(doctype, name)
	_assert_expected_modified(doc, expected_modified)
	_validate_standard_context(doc)

	blockers = _standard_shape_blockers(doc)
	if blockers:
		frappe.throw("<br>".join(blockers))

	workflow_readiness = get_workflow_readiness(doctype=doctype, doc=doc)
	if _clean(workflow_readiness.get("source")) == "frappe":
		frappe.throw(
			_(
				"{0} is controlled by active Workflow {1}. Use the available workflow action in EdgeSuite."
			).format(doctype, workflow_readiness.get("workflow") or _("Frappe Workflow")),
			frappe.ValidationError,
		)

	if not frappe.has_permission(doctype, "submit", doc=doc):
		frappe.throw(
			_("You do not have permission to submit this {0}.").format(doctype),
			frappe.PermissionError,
		)

	# ERPNext remains authoritative for document submission and all native side effects.
	doc.submit()
	if cint(doc.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit {0} {1}.").format(doctype, name))
	doc.reload()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or "Submitted",
		"company": _clean(doc.get("company")),
		"branch": _stored_branch(doc),
		"party": _party_value(doc),
		"source_of_truth": "ERPNext native submit",
		"route": f"/app/{frappe.scrub(doc.doctype).replace('_', '-')}/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def apply_standard_selling_workflow_action(
	doctype: str,
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	"""Apply one Frappe Workflow action to a reviewed standard Quote or Sales Order."""
	doctype = _clean(doctype)
	name = _clean(name)
	action = _clean(action)
	if not action:
		frappe.throw(_("Workflow action is required."))

	_lock_supported_document(doctype, name)
	doc = _get_supported_document(doctype, name)
	expected_modified = _assert_expected_modified(doc, expected_modified)
	_validate_standard_context(doc)
	blockers = _standard_shape_blockers(doc)
	if blockers:
		frappe.throw("<br>".join(blockers))

	workflow_readiness = get_workflow_readiness(doctype=doctype, doc=doc)
	if _clean(workflow_readiness.get("source")) != "frappe":
		frappe.throw(
			_("No active Frappe Workflow owns this {0}.").format(doctype),
			frappe.ValidationError,
		)

	return apply_document_workflow_action(
		doctype=doctype,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
