from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate

from retailedge.guided_entry_context import resolve_branch_warehouse_selection
from retailedge.operating_context import get_operating_context
from retailedge.professional_draft_items import editable_items, update_draft_items
from retailedge.professional_selling import (
	_assert_read,
	_validate_stored_operational_branch,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness


DELIVERY_NOTE_DOCTYPE = "Delivery Note"
_LOCK_TABLE = "tabDelivery Note"
MAX_ITEM_SUMMARY = 10


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _get_delivery_note(name: str):
	name = _clean(name)
	if not name or not frappe.db.exists(DELIVERY_NOTE_DOCTYPE, name):
		frappe.throw(_("Delivery Note {0} does not exist.").format(name or "(blank)"))
	doc = frappe.get_doc(DELIVERY_NOTE_DOCTYPE, name)
	if not frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "read", doc=doc):
		frappe.throw(
			_("You do not have permission to read Delivery Note {0}.").format(name),
			frappe.PermissionError,
		)
	return doc


def _lock_delivery_note(name: str) -> None:
	rows = frappe.db.sql(
		f"SELECT name FROM `{_LOCK_TABLE}` WHERE name = %s FOR UPDATE",
		(_clean(name),),
	)
	if not rows:
		frappe.throw(_("Delivery Note {0} no longer exists.").format(name))


def _stored_branch(doc) -> str:
	return _clean(doc.get("branch") or doc.get("retailedge_branch"))


def _validate_delivery_context(doc) -> tuple[str, str]:
	company = _clean(doc.get("company"))
	if not company:
		frappe.throw(_("Delivery Note {0} has no Company.").format(doc.name))
	_assert_read("Company", company)

	branch = _validate_stored_operational_branch(
		company=company,
		branch=_stored_branch(doc),
		label=_("Delivery Note {0}").format(doc.name),
	)

	operating = get_operating_context() or {}
	operating_company = _clean(operating.get("company"))
	operating_branch = _clean(operating.get("branch"))
	if operating_company and operating_company != company:
		frappe.throw(
			_("Delivery Note {0} belongs to another Company. Change Operating Context before completing it.").format(
				doc.name
			),
			frappe.PermissionError,
		)
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(
			_("Delivery Note {0} does not belong to the current Operating Branch.").format(doc.name),
			frappe.PermissionError,
		)
	return company, branch


def _standard_delivery_blockers(doc) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft Delivery Notes can use standard EdgeSuite completion."))
	if doc.get("amended_from"):
		blockers.append(_("Amended Delivery Notes require Advanced ERPNext review."))
	if cint(doc.get("is_return")) or _clean(doc.get("return_against")):
		blockers.append(_("Delivery returns require Advanced ERPNext review."))
	if cint(doc.get("is_internal_customer")) or _clean(doc.get("represents_company")):
		blockers.append(_("Internal or inter-company delivery requires Advanced ERPNext review."))
	if not _clean(doc.get("customer")):
		blockers.append(_("Delivery Note Customer is required."))

	items = list(doc.get("items") or [])
	if not items:
		blockers.append(_("Delivery Note must contain at least one item."))

	if list(doc.get("packed_items") or []):
		blockers.append(_("Product Bundle / packed-item delivery requires Advanced ERPNext review."))

	source_orders: set[str] = set()
	for row in items:
		source_name = _clean(row.get("against_sales_order"))
		if source_name:
			source_orders.add(source_name)

		if not _clean(row.get("warehouse")):
			blockers.append(
				_("Every standard Delivery Note item must have a Stock Location.")
			)

		if (
			_clean(row.get("serial_no"))
			or _clean(row.get("batch_no"))
			or _clean(row.get("serial_and_batch_bundle"))
		):
			blockers.append(
				_("Serial/Batch controlled delivery requires Advanced ERPNext review.")
			)

	if len(source_orders) > 1:
		blockers.append(
			_("A standard Delivery Note may reference only one source Sales Order.")
		)

	return list(dict.fromkeys(blockers))


def _validate_source_and_stock_context(
	doc,
	*,
	company: str,
	branch: str,
) -> dict[str, Any]:
	blockers: list[str] = []
	items = list(doc.get("items") or [])
	source_orders = {
		_clean(row.get("against_sales_order"))
		for row in items
		if _clean(row.get("against_sales_order"))
	}
	source_name = next(iter(source_orders), "") if len(source_orders) == 1 else ""
	customer = _clean(doc.get("customer"))

	source_branch = ""
	if source_name:
		if not frappe.db.exists("Sales Order", source_name):
			blockers.append(_("Source Sales Order {0} no longer exists.").format(source_name))
		else:
			source = frappe.get_doc("Sales Order", source_name)
			if not frappe.has_permission("Sales Order", "read", doc=source):
				frappe.throw(
					_("You do not have permission to read Sales Order {0}.").format(source_name),
					frappe.PermissionError,
				)
			if cint(source.docstatus) != 1:
				blockers.append(_("Source Sales Order {0} is not submitted.").format(source_name))
			source_company = _clean(source.get("company"))
			source_customer = _clean(source.get("customer"))
			if source_company != company:
				blockers.append(_("Source Sales Order Company does not match the Delivery Note."))
			if source_customer != customer:
				blockers.append(_("Source Sales Order Customer does not match the Delivery Note."))
			source_branch = _validate_stored_operational_branch(
				company=source_company or company,
				branch=_stored_branch(source),
				label=_("Submitted Sales Order {0}").format(source_name),
			)

	resolved_branches: set[str] = set()
	for row in items:
		warehouse = _clean(row.get("warehouse"))
		if not warehouse:
			continue
		_assert_read("Warehouse", warehouse)
		warehouse_company = _clean(
			frappe.db.get_value("Warehouse", warehouse, "company")
		)
		if warehouse_company and warehouse_company != company:
			blockers.append(
				_("Stock Location {0} does not belong to Company {1}.").format(
					warehouse, company
				)
			)
			continue

		try:
			resolved = resolve_branch_warehouse_selection(
				company=company,
				branch=branch or source_branch,
				warehouse=warehouse,
				preference="sales",
				user=frappe.session.user,
			)
			warehouse_branch = _clean(resolved.get("branch"))
		except (frappe.PermissionError, frappe.ValidationError) as exc:
			blockers.append(str(exc))
			continue
		if not warehouse_branch:
			blockers.append(
				_("Stock Location {0} is not configured in an enabled Branch Setup for Company {1}.").format(
					warehouse, company
				)
			)
			continue
		warehouse_branch = _validate_stored_operational_branch(
			company=company,
			branch=warehouse_branch,
			label=_("Delivery Stock Location {0}").format(warehouse),
		)
		resolved_branches.add(warehouse_branch)

	if len(resolved_branches) > 1:
		blockers.append(
			_("The Delivery Note spans Stock Locations from multiple operational Branches.")
		)

	warehouse_branch = next(iter(resolved_branches), "") if len(resolved_branches) == 1 else ""
	effective_branch = branch or source_branch or warehouse_branch
	if source_branch and effective_branch and source_branch != effective_branch:
		blockers.append(_("The source Sales Order Branch does not match the Delivery Note Branch."))
	if warehouse_branch and effective_branch and warehouse_branch != effective_branch:
		blockers.append(_("The Stock Location Branch does not match the Delivery Note Branch."))

	operating = get_operating_context() or {}
	operating_branch = _clean(operating.get("branch"))
	if operating_branch and effective_branch and operating_branch != effective_branch:
		frappe.throw(
			_("The Delivery Note stock context does not match the current Operating Branch."),
			frappe.PermissionError,
		)

	return {
		"source_sales_order": source_name,
		"source_branch": source_branch,
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
				"warehouse": _clean(row.get("warehouse")),
				"against_sales_order": _clean(row.get("against_sales_order")),
			}
		)
	return result


def _build_preview(doc) -> dict[str, Any]:
	company, branch = _validate_delivery_context(doc)
	blockers = _standard_delivery_blockers(doc)
	stock_context = _validate_source_and_stock_context(
		doc,
		company=company,
		branch=branch,
	)
	blockers.extend(stock_context["blockers"])
	blockers = list(dict.fromkeys(blockers))

	workflow_readiness = get_workflow_readiness(
		doctype=DELIVERY_NOTE_DOCTYPE,
		doc=doc,
	)
	workflow_controlled = _clean(workflow_readiness.get("source")) == "frappe"

	if (
		not workflow_controlled
		and not blockers
		and not frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "submit", doc=doc)
	):
		blockers.append(_("You do not have permission to submit this Delivery Note."))

	return {
		"doctype": DELIVERY_NOTE_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or ("Draft" if cint(doc.docstatus) == 0 else ""),
		"company": company,
		"branch": stock_context["effective_branch"] or branch,
		"customer": _clean(doc.get("customer")),
		"currency": _clean(doc.get("currency")),
		"grand_total": flt(doc.get("grand_total")),
		"source_sales_order": stock_context["source_sales_order"],
		"item_count": len(list(doc.get("items") or [])),
		"items": _item_summary(doc),
		"editable_items": editable_items(doc),
		"posting_date": _clean(doc.get("posting_date")),
		"posting_time": _clean(doc.get("posting_time")),
		"remarks": _clean(doc.get("remarks")),
		"can_edit": bool(cint(doc.docstatus) == 0 and frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "write", doc=doc)),
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
		"route": f"/app/delivery-note/{doc.name}",
	}


def _assert_expected_modified(doc, expected_modified: str | None) -> str:
	expected_modified = _clean(expected_modified)
	if not expected_modified:
		frappe.throw(
			_("The reviewed Delivery Note version is required. Refresh completion review."),
			frappe.TimestampMismatchError,
		)
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid reviewed Delivery Note version."), frappe.ValidationError)
	if expected != current:
		frappe.throw(
			_("Delivery Note {0} changed after completion review. Refresh before continuing.").format(
				doc.name
			),
			frappe.TimestampMismatchError,
		)
	return expected_modified


@frappe.whitelist()
def get_standard_delivery_completion_preview(name: str) -> dict[str, Any]:
	"""Return a persistence-free completion review for one standard Delivery Note."""
	doc = _get_delivery_note(name)
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def update_standard_delivery_draft(
	name: str,
	values: dict | str | None = None,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Edit one Delivery Note draft while preserving source links and stock truth."""
	name = _clean(name)
	_lock_delivery_note(name)
	doc = _get_delivery_note(name)
	_assert_expected_modified(doc, expected_modified)
	company, branch = _validate_delivery_context(doc)
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only draft Delivery Notes can be edited here."))
	if not frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Delivery Note."), frappe.PermissionError)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	values = values or {}
	if not isinstance(values, dict):
		frappe.throw(_("Invalid Delivery Note draft changes."))

	posting_date = getdate(values.get("posting_date") or doc.get("posting_date"))
	doc.posting_date = posting_date
	if doc.meta.has_field("remarks"):
		doc.remarks = _clean(values.get("remarks"))

	default_warehouse = _clean(doc.get("set_warehouse"))
	if not default_warehouse:
		for row in list(doc.get("items") or []):
			if _clean(row.get("warehouse")):
				default_warehouse = _clean(row.get("warehouse"))
				break

	update_draft_items(
		doc,
		values.get("items") or editable_items(doc),
		company=company,
		branch=branch,
		customer=_clean(doc.get("customer")),
		posting_date=str(posting_date),
		default_warehouse=default_warehouse,
	)
	doc.save()
	doc.reload()
	result = _build_preview(doc)
	result["persistence"] = "draft_update"
	return result


@frappe.whitelist(methods=["POST"])
def submit_standard_delivery_note(
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one reviewed standard Delivery Note through native ERPNext stock posting."""
	name = _clean(name)
	_lock_delivery_note(name)
	doc = _get_delivery_note(name)
	_assert_expected_modified(doc, expected_modified)
	company, branch = _validate_delivery_context(doc)

	blockers = _standard_delivery_blockers(doc)
	stock_context = _validate_source_and_stock_context(
		doc,
		company=company,
		branch=branch,
	)
	blockers.extend(stock_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=DELIVERY_NOTE_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) == "frappe":
		frappe.throw(
			_(
				"Delivery Note is controlled by active Workflow {0}. Use the available workflow action in EdgeSuite."
			).format(workflow_readiness.get("workflow") or _("Frappe Workflow")),
			frappe.ValidationError,
		)

	if not frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "submit", doc=doc):
		frappe.throw(
			_("You do not have permission to submit this Delivery Note."),
			frappe.PermissionError,
		)

	# ERPNext remains authoritative for Stock Ledger, valuation, Sales Order delivery
	# quantities/status and all Delivery Note submit-side effects.
	doc.submit()
	if cint(doc.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit Delivery Note {0}.").format(name))
	doc.reload()
	return {
		"doctype": DELIVERY_NOTE_DOCTYPE,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or "Submitted",
		"company": _clean(doc.get("company")),
		"branch": _stored_branch(doc) or stock_context["effective_branch"],
		"customer": _clean(doc.get("customer")),
		"source_sales_order": stock_context["source_sales_order"],
		"source_of_truth": "ERPNext native submit",
		"route": f"/app/delivery-note/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def apply_standard_delivery_workflow_action(
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	"""Apply one Frappe Workflow action to a reviewed standard Delivery Note."""
	name = _clean(name)
	action = _clean(action)
	if not action:
		frappe.throw(_("Workflow action is required."))

	_lock_delivery_note(name)
	doc = _get_delivery_note(name)
	expected_modified = _assert_expected_modified(doc, expected_modified)
	company, branch = _validate_delivery_context(doc)

	blockers = _standard_delivery_blockers(doc)
	stock_context = _validate_source_and_stock_context(
		doc,
		company=company,
		branch=branch,
	)
	blockers.extend(stock_context["blockers"])
	if blockers:
		frappe.throw("<br>".join(list(dict.fromkeys(blockers))))

	workflow_readiness = get_workflow_readiness(
		doctype=DELIVERY_NOTE_DOCTYPE,
		doc=doc,
	)
	if _clean(workflow_readiness.get("source")) != "frappe":
		frappe.throw(
			_("No active Frappe Workflow owns this Delivery Note."),
			frappe.ValidationError,
		)

	return apply_document_workflow_action(
		doctype=DELIVERY_NOTE_DOCTYPE,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=str(expected_workflow_state or ""),
	)
