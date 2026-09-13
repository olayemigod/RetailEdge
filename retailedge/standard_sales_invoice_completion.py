from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime

from retailedge.branch_context import resolve_branch_from_warehouse
from retailedge.operating_context import get_operating_context
from retailedge.professional_selling import (
	_assert_read,
	_validate_stored_operational_branch,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness


SALES_INVOICE_DOCTYPE = "Sales Invoice"
DELIVERY_NOTE_DOCTYPE = "Delivery Note"
SALES_ORDER_DOCTYPE = "Sales Order"
_LOCK_TABLE = "tabSales Invoice"
MAX_ITEM_SUMMARY = 10


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _get_sales_invoice(name: str):
	name = _clean(name)
	if not name or not frappe.db.exists(SALES_INVOICE_DOCTYPE, name):
		frappe.throw(_("Sales Invoice {0} does not exist.").format(name or "(blank)"))
	doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, name)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to read Sales Invoice {0}.").format(name),
			frappe.PermissionError,
		)
	return doc


def _lock_sales_invoice(name: str) -> None:
	rows = frappe.db.sql(
		f"SELECT name FROM `{_LOCK_TABLE}` WHERE name = %s FOR UPDATE",
		(_clean(name),),
	)
	if not rows:
		frappe.throw(_("Sales Invoice {0} no longer exists.").format(name))


def _stored_branch(doc) -> str:
	return _clean(doc.get("branch") or doc.get("retailedge_branch"))


def _validate_invoice_context(doc) -> tuple[str, str]:
	company = _clean(doc.get("company"))
	if not company:
		frappe.throw(_("Sales Invoice {0} has no Company.").format(doc.name))
	_assert_read("Company", company)

	invoice_branch = _validate_stored_operational_branch(
		company=company,
		branch=_stored_branch(doc),
		label=_("Sales Invoice {0}").format(doc.name),
	)

	operating = get_operating_context() or {}
	operating_company = _clean(operating.get("company"))
	operating_branch = _clean(operating.get("branch"))
	if operating_company and operating_company != company:
		frappe.throw(
			_("Sales Invoice {0} belongs to another Company. Change Operating Context before completing it.").format(
				doc.name
			),
			frappe.PermissionError,
		)
	if operating_branch and invoice_branch and operating_branch != invoice_branch:
		frappe.throw(
			_("Sales Invoice {0} does not belong to the current Operating Branch.").format(doc.name),
			frappe.PermissionError,
		)
	return company, invoice_branch


def _standard_invoice_blockers(doc) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft Sales Invoices can use standard EdgeSuite completion."))
	if doc.get("amended_from"):
		blockers.append(_("Amended Sales Invoices require Advanced ERPNext review."))
	if cint(doc.get("is_return")) or _clean(doc.get("return_against")):
		blockers.append(_("Return / Credit Note completion requires Advanced ERPNext review."))
	if cint(doc.get("is_pos")):
		blockers.append(_("POS Sales Invoice completion requires Advanced ERPNext review."))
	if cint(doc.get("is_consolidated")):
		blockers.append(_("Consolidated Sales Invoice completion requires Advanced ERPNext review."))
	if (
		cint(doc.get("is_internal_customer"))
		or _clean(doc.get("represents_company"))
		or _clean(doc.get("inter_company_invoice_reference"))
	):
		blockers.append(_("Internal or inter-company Sales Invoice requires Advanced ERPNext review."))
	if not _clean(doc.get("customer")):
		blockers.append(_("Sales Invoice Customer is required."))
	if not list(doc.get("items") or []):
		blockers.append(_("Sales Invoice must contain at least one item."))

	if flt(doc.get("write_off_amount")) or flt(doc.get("base_write_off_amount")):
		blockers.append(_("Sales Invoice write-off requires Advanced ERPNext review."))
	if cint(doc.get("write_off_outstanding_amount_automatically")):
		blockers.append(_("Automatic outstanding write-off requires Advanced ERPNext review."))
	if list(doc.get("advances") or []):
		blockers.append(_("Pre-allocated advances require Advanced ERPNext review."))
	if cint(doc.get("allocate_advances_automatically")):
		blockers.append(_("Automatic advance allocation requires Advanced ERPNext review."))

	return list(dict.fromkeys(blockers))


def _reference_names(doc, fieldname: str) -> set[str]:
	return {
		_clean(row.get(fieldname))
		for row in list(doc.get("items") or [])
		if _clean(row.get(fieldname))
	}


def _validate_source_context(
	doc,
	*,
	company: str,
	invoice_branch: str,
) -> dict[str, Any]:
	blockers: list[str] = []
	delivery_notes = _reference_names(doc, "delivery_note")
	sales_orders = _reference_names(doc, "sales_order")

	source_type = ""
	source_name = ""
	if delivery_notes:
		source_type = DELIVERY_NOTE_DOCTYPE
		if len(delivery_notes) == 1:
			source_name = next(iter(delivery_notes))
		else:
			blockers.append(_("Standard Sales Invoice may reference only one Delivery Note."))
	elif sales_orders:
		source_type = SALES_ORDER_DOCTYPE
		if len(sales_orders) == 1:
			source_name = next(iter(sales_orders))
		else:
			blockers.append(_("Standard Sales Invoice may reference only one Sales Order."))

	source_branch = ""
	if source_name:
		if not frappe.db.exists(source_type, source_name):
			blockers.append(_("{0} {1} no longer exists.").format(source_type, source_name))
		else:
			source = frappe.get_doc(source_type, source_name)
			if not frappe.has_permission(source_type, "read", doc=source):
				frappe.throw(
					_("You do not have permission to read {0} {1}.").format(source_type, source_name),
					frappe.PermissionError,
				)
			if cint(source.docstatus) != 1:
				blockers.append(_("{0} {1} is not submitted.").format(source_type, source_name))

			source_company = _clean(source.get("company"))
			source_customer = _clean(source.get("customer"))
			customer = _clean(doc.get("customer"))
			if source_company != company:
				blockers.append(_("Source document Company does not match the Sales Invoice."))
			if source_customer != customer:
				blockers.append(_("Source document Customer does not match the Sales Invoice."))

			source_branch = _validate_stored_operational_branch(
				company=source_company or company,
				branch=_stored_branch(source),
				label=_("{0} {1}").format(source_type, source_name),
			)
			if source_branch and invoice_branch and source_branch != invoice_branch:
				blockers.append(_("Source document Branch does not match the Sales Invoice Branch."))

	return {
		"source_type": source_type,
		"source_name": source_name,
		"source_branch": source_branch,
		"blockers": list(dict.fromkeys(blockers)),
	}


def _validate_stock_context(
	doc,
	*,
	company: str,
	invoice_branch: str,
	source_type: str,
	source_branch: str,
) -> dict[str, Any]:
	if not cint(doc.get("update_stock")):
		return {
			"mode": "accounting_only",
			"warehouse_branch": "",
			"effective_branch": invoice_branch or source_branch,
			"blockers": [],
		}

	blockers: list[str] = []
	if source_type == DELIVERY_NOTE_DOCTYPE and cint(doc.get("update_stock")):
		blockers.append(
			_(
				"The linked Delivery Note already records fulfilment stock movement; this Sales Invoice cannot also update stock in the standard path."
			)
		)

	if list(doc.get("packed_items") or []):
		blockers.append(
			_("Product Bundle / packed-item stock posting requires Advanced ERPNext review.")
		)

	resolved_branches: set[str] = set()
	for row in list(doc.get("items") or []):
		warehouse = _clean(row.get("warehouse"))
		if not warehouse:
			blockers.append(_("Every stock-updating Sales Invoice item must have a Warehouse."))
			continue

		if (
			_clean(row.get("serial_no"))
			or _clean(row.get("batch_no"))
			or _clean(row.get("serial_and_batch_bundle"))
		):
			blockers.append(
				_("Serial/Batch controlled stock-updating Sales Invoice requires Advanced ERPNext review.")
			)

		_assert_read("Warehouse", warehouse)
		warehouse_company = _clean(
			frappe.db.get_value("Warehouse", warehouse, "company")
		)
		if warehouse_company and warehouse_company != company:
			blockers.append(
				_("Warehouse {0} does not belong to Company {1}.").format(
					warehouse, company
				)
			)
			continue

		resolved = resolve_branch_from_warehouse(warehouse, company=company)
		warehouse_branch = _clean(resolved.get("branch"))
		if not warehouse_branch:
			blockers.append(
				_("Warehouse {0} is not mapped to an operational Branch; use Advanced ERPNext review.").format(
					warehouse
				)
			)
			continue
		warehouse_branch = _validate_stored_operational_branch(
			company=company,
			branch=warehouse_branch,
			label=_("Sales Invoice Warehouse {0}").format(warehouse),
		)
		resolved_branches.add(warehouse_branch)

	if len(resolved_branches) > 1:
		blockers.append(
			_("The Sales Invoice spans Warehouses from multiple operational Branches.")
		)

	warehouse_branch = next(iter(resolved_branches), "") if len(resolved_branches) == 1 else ""
	effective_branch = invoice_branch or source_branch or warehouse_branch
	if source_branch and effective_branch and source_branch != effective_branch:
		blockers.append(_("Source document Branch does not match the stock-posting Branch."))
	if warehouse_branch and effective_branch and warehouse_branch != effective_branch:
		blockers.append(_("Warehouse Branch does not match the Sales Invoice Branch."))

	operating = get_operating_context() or {}
	operating_branch = _clean(operating.get("branch"))
	if operating_branch and effective_branch and operating_branch != effective_branch:
		frappe.throw(
			_("The Sales Invoice stock context does not match the current Operating Branch."),
			frappe.PermissionError,
		)

	return {
		"mode": "update_stock",
		"warehouse_branch": warehouse_branch,
		"effective_branch": effective_branch,
		"blockers": list(dict.fromkeys(blockers)),
	}


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
				"warehouse": _clean(row.get("warehouse")),
			}
		)
	return result


def _build_preview(doc) -> dict[str, Any]:
	company, invoice_branch = _validate_invoice_context(doc)
	blockers = _standard_invoice_blockers(doc)
	source_context = _validate_source_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
		source_type=source_context["source_type"],
		source_branch=source_context["source_branch"],
	)
	blockers.extend(stock_context["blockers"])
	blockers = list(dict.fromkeys(blockers))

	workflow_readiness = get_workflow_readiness(
		doctype=SALES_INVOICE_DOCTYPE,
		doc=doc,
	)
	workflow_controlled = _clean(workflow_readiness.get("source")) == "frappe"

	if (
		not workflow_controlled
		and not blockers
		and not frappe.has_permission(SALES_INVOICE_DOCTYPE, "submit", doc=doc)
	):
		blockers.append(_("You do not have permission to submit this Sales Invoice."))

	return {
		"doctype": SALES_INVOICE_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or ("Draft" if cint(doc.docstatus) == 0 else ""),
		"company": company,
		"branch": stock_context["effective_branch"] or invoice_branch,
		"customer": _clean(doc.get("customer")),
		"currency": _clean(doc.get("currency")),
		"grand_total": flt(doc.get("grand_total")),
		"update_stock": bool(cint(doc.get("update_stock"))),
		"completion_mode": stock_context["mode"],
		"source_type": source_context["source_type"],
		"source_name": source_context["source_name"],
		"item_count": len(list(doc.get("items") or [])),
		"items": _item_summary(doc),
		"blockers": blockers,
		"can_submit": bool(
			not blockers
			and not workflow_controlled
			and cint(doc.docstatus) == 0
		),
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": bool(
			workflow_controlled
			and not blockers
			and cint(doc.docstatus) == 0
		),
		"persistence": "none",
		"source_of_truth": "ERPNext",
		"route": f"/app/sales-invoice/{doc.name}",
	}


def _assert_expected_modified(doc, expected_modified: str | None) -> str:
	expected_modified = _clean(expected_modified)
	if not expected_modified:
		frappe.throw(
			_("The reviewed Sales Invoice version is required. Refresh completion review."),
			frappe.TimestampMismatchError,
		)
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid reviewed Sales Invoice version."), frappe.ValidationError)
	if expected != current:
		frappe.throw(
			_("Sales Invoice {0} changed after completion review. Refresh before continuing.").format(
				doc.name
			),
			frappe.TimestampMismatchError,
		)
	return expected_modified


@frappe.whitelist()
def get_standard_sales_invoice_completion_preview(name: str) -> dict[str, Any]:
	"""Return a persistence-free completion review for one standard Sales Invoice."""
	doc = _get_sales_invoice(name)
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def submit_standard_sales_invoice(
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed standard Sales Invoice through native ERPNext accounting."""
	name = _clean(name)
	_lock_sales_invoice(name)
	doc = _get_sales_invoice(name)
	_assert_expected_modified(doc, expected_modified)
	company, invoice_branch = _validate_invoice_context(doc)

	blockers = _standard_invoice_blockers(doc)
	source_context = _validate_source_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
		source_type=source_context["source_type"],
		source_branch=source_context["source_branch"],
	)
	blockers.extend(stock_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=SALES_INVOICE_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) == "frappe":
		frappe.throw(
			_(
				"Sales Invoice is controlled by active Workflow {0}. Use the available workflow action in EdgeSuite."
			).format(workflow_readiness.get("workflow") or _("Frappe Workflow")),
			frappe.ValidationError,
		)

	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "submit", doc=doc):
		frappe.throw(
			_("You do not have permission to submit this Sales Invoice."),
			frappe.PermissionError,
		)

	# ERPNext remains authoritative for GL, receivable/outstanding, tax, loyalty,
	# source billing status and Stock Ledger/valuation when update_stock is enabled.
	doc.submit()
	if cint(doc.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit Sales Invoice {0}.").format(name))
	doc.reload()
	return {
		"doctype": SALES_INVOICE_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or "Submitted",
		"company": _clean(doc.get("company")),
		"branch": _stored_branch(doc) or stock_context["effective_branch"],
		"customer": _clean(doc.get("customer")),
		"update_stock": bool(cint(doc.get("update_stock"))),
		"source_type": source_context["source_type"],
		"source_name": source_context["source_name"],
		"source_of_truth": "ERPNext native submit",
		"route": f"/app/sales-invoice/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def apply_standard_sales_invoice_workflow_action(
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	"""Apply one Frappe Workflow action to a reviewed standard Sales Invoice."""
	name = _clean(name)
	action = _clean(action)
	if not action:
		frappe.throw(_("Workflow action is required."))

	_lock_sales_invoice(name)
	doc = _get_sales_invoice(name)
	expected_modified = _assert_expected_modified(doc, expected_modified)
	company, invoice_branch = _validate_invoice_context(doc)

	blockers = _standard_invoice_blockers(doc)
	source_context = _validate_source_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
	)
	blockers.extend(source_context["blockers"])
	stock_context = _validate_stock_context(
		doc,
		company=company,
		invoice_branch=invoice_branch,
		source_type=source_context["source_type"],
		source_branch=source_context["source_branch"],
	)
	blockers.extend(stock_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=SALES_INVOICE_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) != "frappe":
		frappe.throw(
			_("No active Frappe Workflow owns this Sales Invoice."),
			frappe.ValidationError,
		)

	return apply_document_workflow_action(
		doctype=SALES_INVOICE_DOCTYPE,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
